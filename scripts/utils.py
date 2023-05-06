import os
import math
import logging

from systemd.journal import JournalHandler
from constants import *

def feed_file_to_plex(disks, pkg_data, manual):
    if manual == True:
        _, filename, media_type = parse_pyload_name(pkg_data.payload["name"])
    else:
        _, filename, media_type = parse_pyload_name(pkg_data.name)
    # TODO move file to the proper storage
    # TODO check the disk usage and balance the mv operation
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
