import json
import firebase_admin
import os
import logging

from time import sleep
from firebase_admin import credentials
from firebase_admin import firestore
from models.msg import *
from utils import *
from constants import *

dir_path = os.path.dirname(os.path.realpath(__file__))

cred = credentials.Certificate(f'{dir_path}/../configs/serviceAccountKey.json')
firebase_admin.initialize_app(cred)
db = firestore.client()

def get_storage_paths():
    storages = db.collection(u'storages').get()
    disks = []
    for storage_doc in storages:
        snap_dic = storage_doc.to_dict()
        name = snap_dic.get('name', f'unknown_name')
        path = snap_dic.get('path', f'unknown_path')
        storage_data = { "name" : name, "path" : path}
        disks.append(storage_data)

    mylogger(f'current disks {disks}')
    return disks

def document_remove_from_stage(stage, id):
    db.collection(stage).document(id).delete()

def document_add_stage(stage, data):
    db.collection(stage).add(document_data=data.payload, document_id=data.snapshot_id)

def document_ref(stage, id):
    return db.collection(stage).document(id).get()

def handle_to_cloud_requests(data):
    req = json.loads(data)
    msg = MyMgrRequest(**req)
    if msg.type == MyMgrRequestType.DOWNLOAD_IN_PROGRESS:
        dwn_ref = db.collection('download_running').document(msg.snapshot_id)
        dwn_ref.update(msg.payload)
    elif msg.type == MyMgrRequestType.DOWNLOAD_FINISHED:
        dwn_ref = db.collection('download_running').document(msg.snapshot_id)
        msg = MyMgrRequest(**req)
        document_add_stage('download_finished', MyMgrRequest(type=msg.type, payload=dwn_ref.get().to_dict(), snapshot_id=msg.snapshot_id))
        dwn_ref = db.collection('download_finished').document(msg.snapshot_id)
        dwn_ref.update(msg.payload)
        document_remove_from_stage('download_running', msg.snapshot_id)
    elif msg.type == MyMgrRequestType.DOWNLOAD_REQUESTED:
        dwn_ref = db.collection('download_running').document(msg.snapshot_id)
        dwn_ref.update(msg.payload)

    return msg

### monitor queue from firebase and notify pyload queue
def monitor_download_queue(q_pyload, q_cloud, q_manual):
    while True:
        try:
            to_cloud_data = q_cloud.get(True, timeout=CLOUD_MONITOR_TIME)
            handle_to_cloud_requests(to_cloud_data)
            continue
        except Exception:
            pass

        current_queue = db.collection(u'request_queue').get()
        is_new_req = True if len(current_queue) > 0 else False
        if is_new_req == False:
            current_queue = db.collection(u'download_running').get()

        for doc in current_queue:
            msg_type = MyMgrRequestType.DOWNLOAD_REQUEST if is_new_req else MyMgrRequestType.DOWNLOAD_MONITOR
            req = MyMgrRequest(msg_type)
            req.snapshot_to_request(doc)

            mylogger(req)
            if req.is_for_pyload() == True:
                q_pyload.put(req.build_msg())
            else:
                q_manual.put(req.build_msg())

            if is_new_req == True:
                document_add_stage('download_running', req)
                document_remove_from_stage('request_queue', doc.id)

        sleep(CLOUD_MONITOR_TIME)
