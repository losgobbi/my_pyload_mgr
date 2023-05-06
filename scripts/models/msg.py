import json

from enum import IntEnum
from models.pyload_data import *
from datetime import datetime, timezone
from utils import parse_pyload_name
from constants import *

class MyMgrRequestType(IntEnum):
    INVALID = 0
    DOWNLOAD_REQUEST = 10
    DOWNLOAD_IN_PROGRESS = 20
    DOWNLOAD_FINISHED = 30

class MyMgrRequest():
    def __init__(self, type=MyMgrRequestType.INVALID, payload={}, snapshot_id=None):
        self.type = type
        self.payload = payload
        self.snapshot_id = snapshot_id

    def snapshot_to_request(self, snapshot):
        snap_dic = snapshot.to_dict()
        self.snapshot_id = snapshot.id
        self.payload = {
            "name": snap_dic.get('name', f'unknown_name'),
            "links" : snap_dic.get('links', []),
            "type": snap_dic.get('type', f'pyload_req'),
            "expected_size": snap_dic.get('expected_size', '0 B'),
            "progress": snap_dic.get('progress', 0),
            "last_current_size": snap_dic.get('last_current_size', '0 B'),
            "current_size": snap_dic.get('current_size', '0 B'),
            "timeout": snap_dic.get('timeout', MANUAL_TIMEOUT),
            "media_type": snap_dic.get('media_type', 'Others'),
            "filepath": snap_dic.get('filepath', ''),
            "pyload_pkg_id": snap_dic.get('pyload_pkg_id', -1)
        }

    def is_for_pyload(self):
        return self.payload["type"] == "pyload_req"

    def pyload_to_snapshot(self, pkg: PackageData, progress):
        self.snapshot_id, name, media_type = parse_pyload_name(pkg.name)
        self.payload = {
            "pyload_name": name,
            "pyload_pkg_id": pkg.pid,
            "pyload_pkg_links" : pkg.links,
            "pyload_progress": progress,
            "type": "pyload_req",
            "expected_size": 0,
            "media_type": media_type
        }

    def manual_to_snapshot(self, pkg, progress):
        self.snapshot_id = pkg.snapshot_id
        self.payload = {
            "name": pkg.payload["name"],
            "progress": progress,
            "type": "manual",
            "expected_size": pkg.payload["expected_size"],
            "last_current_size": pkg.payload["last_current_size"],
            "current_size": pkg.payload["current_size"],
            "timeout": pkg.payload["timeout"],
            "links": [],
            "media_type": pkg.payload["media_type"],
            "filepath": pkg.payload["filepath"]
        }

    def build_msg(self):
        return json.dumps(self.__dict__)