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

def document_update_stage(stage, data):
    db.collection(stage).add(document_data=data.payload, document_id=data.snapshot_id)

def handle_requests(data):
    req = json.loads(data)
    msg = MyMgrRequest(**req)
    if msg.type == MyMgrRequestType.DOWNLOAD_IN_PROGRESS:
        dwn_ref = db.collection('download_running').document(msg.snapshot_id)
        dwn_ref.set(msg.payload)
    elif msg.type == MyMgrRequestType.DOWNLOAD_FINISHED:
        document_update_stage('download_finished', msg)
        document_remove_from_stage('download_running', msg.snapshot_id)

### monitor queue from firebase and notify pyload queue
def monitor_download_queue(q_pyload, q_cloud, q_manual):
    while True:
        try:
            data = q_cloud.get(True, timeout=CLOUD_MONITOR_TIME)
            handle_requests(data)
            continue
        except Exception:
            pass
    
        queue = db.collection(u'request_queue').get()
        new_req = False
        if len(queue) > 0:
            new_req = True
        else:
            queue = db.collection(u'download_running').get()

        for doc in queue:
            req = MyMgrRequest(MyMgrRequestType.DOWNLOAD_REQUEST)
            req.snapshot_to_request(doc)

            if req.is_for_pyload() == True:
                q_pyload.put(req.build_msg())
            else:
                mylogger(req)
                q_manual.put(req.build_msg())

            if new_req == True:
                document_update_stage('download_running', req)
                document_remove_from_stage('request_queue', doc.id)
