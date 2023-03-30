import threading
import requests
import json
import time
import logging

from systemd.journal import JournalHandler
from models.pyload_data import *
from models.pyload_enum import *
from py_cloud import monitor_download_queue
from queue import Queue
from models.msg import *

pyload_ip = "192.168.1.88:8000"
api_url = f'http://{pyload_ip}/api/'

def login(user, password):
    payload = {"username": user, "password": password}
    return requests.post("{}{}".format(api_url, "login"), data=payload)

def get_queue(cookie):
    response = requests.get("{}{}".format(api_url, "getQueue"), 
                            cookies=cookie)
    return response.json()

def get_download_info(cookie):
    downloads = []
    response = requests.get("{}{}".format(api_url, "statusDownloads"), 
                            cookies=cookie)
    status = json.loads(response.text)
    for st in status:
        downloads.append(DownloadInfo(**st))
    return downloads

def get_package_data(cookie, id):
    response = requests.get("{}{}".format(api_url, "getPackageData"), 
                            cookies=cookie,
                            params={"package_id": id})
    status = json.loads(response.text)
    return PackageData(**status)

def print_package(pkg):
    print(f'\tId:{pkg.pid} Name:"{pkg.name}"')
    for link in pkg.links:
        print(f'\t\tLink Name:"{link["name"]}')
        print(f'\t\tSize:{link["format_size"]} Plugin: "{link["plugin"]}"')
        print(f'\t\tLink URL:{link["url"]}')
        print(f'\t\tStatus:{link["status"]} StatusMsg:{link["statusmsg"]}')

# only one link supported
def get_package_status(pkg):
    return pkg.links[0]["status"]

def print_queue(cookie):
    queue = get_queue(cookie)
    print("--> Queue:")
    for i in queue:
        pkgData = get_package_data(cookie, i['pid'])
        print_package(pkgData)

def add_package(cookie, name, links):
    payload = {"name": name, "links": links}    
    payloadJSON = {k: json.dumps(v) for k, v in payload.items()}
    response = requests.get("{}{}".format(api_url, "addPackage"), 
                        cookies=cookie,
                        params=payloadJSON)
    return response

def handle_requests(data):
    req = json.loads(data)
    msg = MyMgrRequest(**req)
    if msg.type == MyMgrRequestType.DOWNLOAD_REQUEST:
        log.info(f'new request, call API for {msg}')
        download_name = msg.snapshot_id + "." + msg.payload["name"].replace(" ", "_")
        add_package(response.cookies, download_name, msg.payload["links"])

def sync_cloud(req_type, pkgData, progress):
    req = MyMgrRequest(req_type)
    try:
        req.pyload_to_snapshot(pkgData, progress)
        q_cloud.put(req.build_msg())
    except Exception:
        # pyload browser usage may not respect the name convention
        pass
        
### monitor requests from message queue and trigger pyload downloads
PYLOAD_MONITOR_TIME = 60
def monitor_pyload(q_pyload, q_cloud):
    active_downloads = []
    while True:
        log.debug("trying to get from pyload queue")
        try:
            data = q_pyload.get_nowait()
            handle_requests(data)
        except Exception:
            pass

        downloads = get_download_info(response.cookies)
        for dwn in downloads:
            log.debug(f'Download active: Name:"{dwn.name}" Size:{dwn.format_size} Progress:{dwn.percent}')
            pkgData = get_package_data(response.cookies, dwn.package_id)
            if dwn.package_id not in active_downloads:
                active_downloads.append(dwn.package_id)

            status = get_package_status(pkgData)
            if status == DownloadStatus.FINISHED:
                log.debug("Finished!")
            elif status == DownloadStatus.DOWNLOADING:
                log.debug(f'Downloading {dwn.percent}')
                sync_cloud(MyMgrRequestType.DOWNLOAD_IN_PROGRESS, pkgData, dwn.percent)
            elif status == DownloadStatus.ABORTED or \
                    status == DownloadStatus.FAILED or \
                    status == DownloadStatus.OFFLINE or \
                    status == DownloadStatus.TEMPOFFLINE or \
                    status == DownloadStatus.UNKNOWN:
                log.debug("Ops, download failed!")
            
        # no more downloads, get the final status
        if len(downloads) == 0 and len(active_downloads) > 0:
            for pkgid in active_downloads:
                pkgData = get_package_data(response.cookies, pkgid)
                status = get_package_status(pkgData)
                log.debug(f'Finished package: {pkgid} final status: {status}')
                progress = -1
                if status == DownloadStatus.FINISHED:
                    progress = 100
                sync_cloud(MyMgrRequestType.DOWNLOAD_FINISHED, pkgData, progress)
            active_downloads = []

        time.sleep(PYLOAD_MONITOR_TIME)

response = login("pyload", "pyload")

log = logging.getLogger('mgr_pyload')
log.addHandler(JournalHandler())
log.setLevel(logging.DEBUG)
log.info("Starting my pyLoad mgr...")
q_pyload = Queue()
q_cloud = Queue()

backend_monitor = threading.Thread(target=monitor_download_queue, args=(q_pyload, q_cloud))
backend_monitor.start()

pyload_monitor = threading.Thread(target=monitor_pyload, args=(q_pyload, q_cloud))
pyload_monitor.start()
pyload_monitor.join()
