import os
import math
import logging
import glob

from systemd.journal import JournalHandler
from constants import *

def feed_file_to_plex(disks, pkg_data):
    filename = pkg_data.payload["name"]
    media_type = pkg_data.payload["media_type"]
    # TODO move file to the proper storage
    print(f'Need to feed plex server at the proper folder file:"{filename}" type "{media_type}"')

def parse_pyload_name(pyload_package_name):
    try:
        snapshot_id, name, media_type = pyload_package_name.split(".")
        return snapshot_id, name, media_type
    except:
        raise Exception('Invalid format for pyload name')

def size_2string(size_bytes):
   if size_bytes == 0:
       return "0B"
   size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
   i = int(math.floor(math.log(size_bytes, 1024)))
   p = math.pow(1024, i)
   s = round(size_bytes / p, 2)
   return "%s %s" % (s, size_name[i])

def string_2size(fmt_size):
    size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
    size, unit = fmt_size.split(" ")
    i = size_name.index(unit)
    return float(size) * (math.pow(1024, i))

def mylogger(*args):
    if DEVELOPMENT_MODE == True:
        print(*args)
    else:
        log = logging.getLogger('mgr_pyload')
        log.debug(*args)

def read_manual_file(path):
    try:
        filepath = glob.glob(path)
        if len(filepath) > 1:
            raise Exception("Wildcard matched more than one name")
        if len(filepath) == 0:
            return [True, 0]

        stat = os.stat(filepath[0])
        size = size_2string(stat.st_size)
        return [False, size]
    except Exception as e:
        raise e