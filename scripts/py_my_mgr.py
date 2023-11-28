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
from models.pyload_data import *

### update stats at cloud during download states
def sync_cloud(reqType, snapshot_id=None, pkg: PackageData=None, progress=0, manual=False):
    msg = MyMgrRequest(reqType)
    try:
        if manual == False:
            msg.snapshot_id = snapshot_id
            msg.auto_to_snapshot(pkg, progress)
        else:
            msg.manual_to_snapshot(pkg, progress)
        q_cloud.put(msg.build_msg())
    except Exception as e:
        pass

    time.sleep(1)

def handle_manual_from_cloud_requests(data):
    # manual is dummy, just return msg
    req = json.loads(data)
    msg = MyMgrRequest(**req)
    return msg

def handle_auto_from_cloud_requests(data):
    req = json.loads(data)
    msg = MyMgrRequest(**req)
    mylogger(f'new msg {msg.type} paylod {msg.payload}')
    if msg.type == MyMgrRequestType.DOWNLOAD_REQUEST:
        pyload_download_request(msg)
    elif msg.type == MyMgrRequestType.DOWNLOAD_MONITOR:
        pass

    return msg

def pyload_download_request(request):
    pkgid = add_package(response.cookies, request.snapshot_id, request.payload["links"])
    mylogger(f'new request, call API for {request.snapshot_id} - {request.payload}, pkgid {pkgid}')
    time.sleep(2)

    request.payload["pyload_pkg_id"] = pkgid
    req = MyMgrRequest(MyMgrRequestType.DOWNLOAD_REQUESTED, request.payload, request.snapshot_id)
    q_cloud.put(req.build_msg())

### monitor requests from message queue and trigger pyload downloads
def monitor_auto_dwn(q_pyload, q_cloud):
    active_downloads = []
    while True:
        try:
            from_cloud_data = q_pyload.get()
            reqMsg = handle_auto_from_cloud_requests(from_cloud_data)
        except Exception as e:
            continue

        snapid = reqMsg.payload["pyload_pkg_id"]
        mylogger(f'checking for download... {snapid}')
        if reqMsg.is_for_pyload == False:
            mylogger("manual dwn into the wrong queue")
            continue
        if snapid == -1:
            continue

        pkgData = get_package_data(response.cookies, snapid)
        dwn = get_download_info(response.cookies, snapid)
        progress = -1
        if dwn != None:
            progress = dwn.percent

        mylogger(f'Download active: PackageId: "{snapid}" Name:"{reqMsg.payload["name"]}" Progress:{progress}')
        status = get_package_status(pkgData)
        if status == DownloadStatus.FINISHED:
            mylogger("Finished!")
            sync_cloud(MyMgrRequestType.DOWNLOAD_FINISHED, snapshot_id=reqMsg.snapshot_id, pkg=pkgData, progress=100)
        elif status == DownloadStatus.DOWNLOADING:
            mylogger(f'Downloading progress:{progress}')
            sync_cloud(MyMgrRequestType.DOWNLOAD_IN_PROGRESS, snapshot_id=reqMsg.snapshot_id, pkg=pkgData, progress=progress)
        elif status == DownloadStatus.ABORTED or \
             status == DownloadStatus.FAILED or \
             status == DownloadStatus.OFFLINE or \
             status == DownloadStatus.TEMPOFFLINE or \
             status == DownloadStatus.UNKNOWN:
                mylogger(f'Ops, download not running? status {status}')
                sync_cloud(MyMgrRequestType.DOWNLOAD_FINISHED, snapshot_id=reqMsg.snapshot_id, pkg=pkgData, progress=-1)
        else:
            mylogger(f'Unknown status? {status}')

#### monitor download at the file system
def monitor_manual_dwn(q_cloud, q_manual):
    while True:
        try:
            from_cloud_data = q_manual.get()
            pkgData = handle_manual_from_cloud_requests(from_cloud_data)
        except Exception:
            pass

        filename = pkgData.payload["name"]
        expected_size = pkgData.payload["expected_size"]

        # it is easier to handle as strings
        last_current_size = "0 B"
        current_size = "0 B"
        try:
            not_found, current_size = read_manual_file(f'/home/gobbi/Downloads/chromium/{filename}*')
        except Exception as e:
            continue

        if current_size != "0 B":
            last_current_size = pkgData.payload["current_size"]
        else:
            last_current_size = pkgData.payload["last_current_size"]
        pkgData.payload["current_size"] = current_size
        pkgData.payload["last_current_size"] = last_current_size

        # handle states
        progress = pkgData.payload["progress"]
        if pkgData.payload["timeout"] == 0:
            mylogger(f'Download monitor timeout {pkgData.payload}')
            sync_cloud(MyMgrRequestType.DOWNLOAD_FINISHED, pkg=pkgData, progress=progress, manual=True)
        elif current_size == last_current_size or not_found == True or expected_size != current_size:
            mylogger(f'Download size not changing {pkgData.payload}')
            pkgData.payload["timeout"] = pkgData.payload["timeout"] - CLOUD_MONITOR_TIME
            sync_cloud(MyMgrRequestType.DOWNLOAD_IN_PROGRESS, pkg=pkgData, progress=progress, manual=True)
        elif expected_size == current_size:
            mylogger(f'Download monitor finished {pkgData.payload}')
            sync_cloud(MyMgrRequestType.DOWNLOAD_FINISHED, pkg=pkgData, progress=100, manual=True)
            feed_file_to_plex(disks, pkgData)
        else:
            current = string_2size(current_size)
            expected = string_2size(expected_size)
            percent = (current*100)/expected
            pkgData.payload["timeout"] = MANUAL_TIMEOUT
            sync_cloud(MyMgrRequestType.DOWNLOAD_IN_PROGRESS, pkg=pkgData, progress=percent, manual=True)

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

pyload_monitor = threading.Thread(target=monitor_auto_dwn, args=(q_pyload, q_cloud))
pyload_monitor.start()

manual_monitor = threading.Thread(target=monitor_manual_dwn, args=(q_cloud, q_manual))
manual_monitor.start()

pyload_monitor.join()
