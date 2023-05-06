import requests
import json

from models.pyload_data import *
from models.pyload_enum import *
from constants import *

def login(user, password):
    payload = {"username": user, "password": password}
    return requests.post("{}{}".format(PYLOAD_API_URL, "login"), data=payload)

def get_queue(cookie):
    response = requests.get("{}{}".format(PYLOAD_API_URL, "getQueue"), 
                            cookies=cookie)
    return response.json()

def get_download_info(cookie):
    downloads = []
    response = requests.get("{}{}".format(PYLOAD_API_URL, "statusDownloads"), 
                            cookies=cookie)
    status = json.loads(response.text)
    for st in status:
        downloads.append(DownloadInfo(**st))
    return downloads

def get_package_data(cookie, id):
    response = requests.get("{}{}".format(PYLOAD_API_URL, "getPackageData"), 
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
        pkg_data = get_package_data(cookie, i['pid'])
        print_package(pkg_data)

def add_package(cookie, name, links):
    payload = {"name": name, "links": links}    
    payload_json = {k: json.dumps(v) for k, v in payload.items()}
    response = requests.get("{}{}".format(PYLOAD_API_URL, "addPackage"), 
                        cookies=cookie,
                        params=payload_json)
    return response