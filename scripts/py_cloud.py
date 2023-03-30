import json
import firebase_admin
import os
import logging

from systemd.journal import JournalHandler
from time import sleep
from firebase_admin import credentials
from firebase_admin import firestore
from models.msg import *

dir_path = os.path.dirname(os.path.realpath(__file__))

cred = credentials.Certificate(f'{dir_path}/../configs/serviceAccountKey.json')
firebase_admin.initialize_app(cred)
db = firestore.client()

def document_remove_from_stage(stage, id):
    db.collection(stage).document(id).delete()

def document_update_stage(stage, data):
    db.collection(stage).add(document_data=data.payload, document_id=data.snapshot_id)

def handle_requests(data):
    req = json.loads(data)
    msg = MyMgrRequest(**req)
    if msg.type == MyMgrRequestType.DOWNLOAD_IN_PROGRESS:
        dwn_ref = db.collection('pyload_download_running').document(msg.snapshot_id)
        dwn_ref.set(msg.payload)
    elif msg.type == MyMgrRequestType.DOWNLOAD_FINISHED:
        document_update_stage('pyload_download_finished', msg)
        document_remove_from_stage('pyload_download_running', msg.snapshot_id)

### monitor queue from firebase and notify pyload queue
CLOUD_MONITOR_TIME = 120
def monitor_download_queue(q_pyload, q_cloud):
    while True:
        log.debug("trying to get from q_cloud queue")
        try:
            data = q_cloud.get_nowait()
            handle_requests(data)
        except Exception:
            pass
    
        ## TODO fresh start, check pyload_download_running if this is 
        ## still running at pyload. if isn't, move to failed with some reason
        queue = db.collection(u'pyload_queue').get()
        for doc in queue:
            req = MyMgrRequest(MyMgrRequestType.DOWNLOAD_REQUEST)
            req.snapshot_to_pyload(doc)
            q_pyload.put(req.build_msg())

            document_update_stage('pyload_download_running', req)
            document_remove_from_stage('pyload_queue', doc.id)

        sleep(CLOUD_MONITOR_TIME)

log = logging.getLogger('mgr_cloud')
log.addHandler(JournalHandler())
log.setLevel(logging.DEBUG)
