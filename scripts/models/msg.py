import json

from enum import IntEnum
from models.pyload_data import *

class MyMgrRequestType(IntEnum):
    INVALID = 0
    DOWNLOAD_REQUEST = 1
    DOWNLOAD_IN_PROGRESS = 2
    DOWNLOAD_FINISHED = 3

class MyMgrRequest():
    def __init__(self, type=MyMgrRequestType.INVALID, payload={}, snapshot_id=None):
        self.type = type
        self.payload = payload
        self.snapshot_id = snapshot_id

    def snapshot_to_pyload(self, snapshot):
        snap_dic = snapshot.to_dict()
        self.snapshot_id = snapshot.id
        self.payload = {
            "name": snap_dic.get('name', f'unknown_name'),
            "links" : snap_dic.get('links', [])
        }

    def pyload_to_snapshot(self, pkg: PackageData, progress):
        full_name = pkg.name.split(".")
        if len(full_name) != 2:
            raise Exception("Invalid format")
        self.snapshot_id = pkg.name.split(".")[0]
        name = pkg.name.split(".")[1]
        self.payload = {
            "pyload_name": name,
            "pyload_pkg_id": pkg.pid,
            "pyload_pkg_links" : pkg.links,
            "pyload_progress": progress
        }

    def build_msg(self):
        return json.dumps(self.__dict__)