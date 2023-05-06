import threading
import requests
import json
import time
import os
import glob
import logging

from pyload_wrapper_api import *
from py_cloud import monitor_download_queue, get_storage_paths
from utils import *
from queue import Queue
from models.msg import *
from datetime import datetime, timezone
from constants import *

def parse_requests(data):
    req = json.loads(data)
    msg = MyMgrRequest(**req)
    return msg

def sync_cloud(req_type, pkgData, progress, manual=False):
    req = MyMgrRequest(req_type)
    try:
        if manual == False:
            req.pyload_to_snapshot(pkgData, progress)
        else:
            req.manual_to_snapshot(pkgData, progress)
        q_cloud.put(req.build_msg())
    except Exception as e:
        # pyload browser usage may not respect the name convention
        pass

### monitor requests from message queue and trigger pyload downloads
def monitor_pyload(q_pyload, q_cloud):
    active_downloads = []
    while True:
        try:
            data = q_pyload.get()
            request = parse_requests(data)
            if request.type == MyMgrRequestType.DOWNLOAD_REQUEST:
                add_api = False
                if request.payload["pyload_pkg_id"] != -1:
                    pkgData = get_package_data(response.cookies, request.payload["pyload_pkg_id"])
                    if len(pkgData.links) > 0:
                        status = pkgData.links[0]["status"]
                        if status == DownloadStatus.DOWNLOADING:
                            mylogger(f'{request.snapshot_id} already running at pyload, pkgData {pkgData.links}')
                            add_api = False
                        elif status != DownloadStatus.FINISHED:
                            request.payload["links"] = []
                            request.payload["links"].append(pkgData.links[0]["url"])
                            add_api = True

                ## add to pyload
                if add_api == True:
                    download_name = \
                        request.snapshot_id + "." + \
                        request.payload["name"].replace(" ", "_") + "." + \
                        request.payload["media_type"]
                    mylogger(f'new request, call API for {request.snapshot_id} - {request.payload} download_name {download_name}')
                    add_package(response.cookies, download_name, request.payload["links"])
                    time.sleep(2)
        except Exception as e:
            pass

        mylogger(f'check for downloads...{response.cookies}')
        downloads = get_download_info(response.cookies)
        for dwn in downloads:
            mylogger(f'Download active: Id: "{dwn.package_id}" Name:"{dwn.name}" Size:{dwn.format_size} Progress:{dwn.percent}')
            pkgData = get_package_data(response.cookies, dwn.package_id)
            if dwn.package_id not in active_downloads:
                active_downloads.append(dwn.package_id)

            status = get_package_status(pkgData)
            if status == DownloadStatus.FINISHED:
                mylogger("Finished!")
            elif status == DownloadStatus.DOWNLOADING:
                mylogger(f'Downloading progress:{dwn.percent}')
                sync_cloud(MyMgrRequestType.DOWNLOAD_IN_PROGRESS, pkgData, dwn.percent)
            elif status == DownloadStatus.ABORTED or \
                    status == DownloadStatus.FAILED or \
                    status == DownloadStatus.OFFLINE or \
                    status == DownloadStatus.TEMPOFFLINE or \
                    status == DownloadStatus.UNKNOWN:
                mylogger(f'Ops, download not running? status {status}')
            
        # no more downloads, get the final status
        if len(downloads) == 0 and len(active_downloads) > 0:
            for pkgid in active_downloads:
                pkgData = get_package_data(response.cookies, pkgid)
                status = get_package_status(pkgData)
                mylogger(f'Finished package id:{pkgid} status:{status}')
                progress = -1
                if status == DownloadStatus.FINISHED:
                    progress = 100
                    feed_file_to_plex(disks, pkgData, False)
                sync_cloud(MyMgrRequestType.DOWNLOAD_FINISHED, pkgData, progress)
            active_downloads = []

#### monitor download at the file system
def monitor_manual_dwn(q_cloud, q_manual):
    while True:
        try:
            data = q_manual.get()
            req = parse_requests(data)
        except Exception:
            pass

        filename = req.payload["name"]
        expected_size = req.payload["expected_size"]
        not_found = False
        # it is easier to handle as strings
        last_current_size = "0 B"
        current_size = "0 B"
        try:
            filepath = glob.glob(f'/home/gobbi/Downloads/chromium/{filename}*')
            if len(filepath) > 1:
                raise Exception("Wildcard matched more than one name")
            if len(filepath) == 0:
                not_found = True
            else:
                req.payload["filepath"] = filepath[0]
                stat = os.stat(filepath[0])
                current_size = size_2string(stat.st_size)
        except Exception as e:
            continue

        if current_size != "0 B":
            last_current_size = req.payload["current_size"]
        else:
            last_current_size = req.payload["last_current_size"]

        req.payload["current_size"] = current_size
        req.payload["last_current_size"] = last_current_size

        # handle states
        if req.payload["timeout"] == 0:
            mylogger(f'Download monitor timeout {req.payload}')
            sync_cloud(MyMgrRequestType.DOWNLOAD_FINISHED, req, req.payload["progress"], True)
        elif current_size == last_current_size:
            # not touched for a while
            req.payload["timeout"] = req.payload["timeout"] - CLOUD_MONITOR_TIME
            sync_cloud(MyMgrRequestType.DOWNLOAD_IN_PROGRESS, req, req.payload["progress"], True)
        elif expected_size == current_size:
            mylogger(f'Download monitor finished {req.payload}')
            sync_cloud(MyMgrRequestType.DOWNLOAD_FINISHED, req, 100, True)
            feed_file_to_plex(disks, req, False)
        elif not_found == True:
            req.payload["timeout"] = req.payload["timeout"] - CLOUD_MONITOR_TIME
            sync_cloud(MyMgrRequestType.DOWNLOAD_IN_PROGRESS, req, req.payload["progress"], True)
        else:
            current = string_2size(current_size)
            expected = string_2size(expected_size)
            percent = (current*100)/expected
            req.payload["timeout"] = MANUAL_TIMEOUT
            sync_cloud(MyMgrRequestType.DOWNLOAD_IN_PROGRESS, req, percent, True)

response = login("pyload", "pyload")

mylogger("Starting my pyLoad mgr...")
q_pyload = Queue()
q_cloud = Queue()
q_manual = Queue()

disks = get_storage_paths()
log = logging.getLogger('mgr_pyload')
log.addHandler(JournalHandler())
log.setLevel(logging.DEBUG)

backend_monitor = threading.Thread(target=monitor_download_queue, args=(q_pyload, q_cloud, q_manual))
backend_monitor.start()

pyload_monitor = threading.Thread(target=monitor_pyload, args=(q_pyload, q_cloud))
pyload_monitor.start()

manual_monitor = threading.Thread(target=monitor_manual_dwn, args=(q_cloud, q_manual))
manual_monitor.start()

pyload_monitor.join()
