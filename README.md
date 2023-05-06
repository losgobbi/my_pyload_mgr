# Pyload Mgr

I'm trying to work on a solution for my home Plex server running on my Raspberry Pi. I want to be able to request downloads for it remotely and also keep track of each download's status. In the future, I intend to use an Android app to control and monitor those requests. Other solutions are focused for torrents, which is not my case.

![Architecture](architecture.png?raw=true "Architecture")

# Dependencies
- python3-systemd for logging through journal.

# Installation
1. install pyload according to the official [documentation](https://github.com/pyload/pyload/wiki/Step-by-Step-Installation-(RaspberryPi)).
2. be sure to add an entry for the systemd integration.
3. add the misc/my_py_mgr.service to the systemd services path, adjusting the User and ExecStart variables.
4. create a simple project inside firebase (web app) and download the credentials.
5. replace serviceAccountKey.json with the proper credentials.

# How it works
1. create a collection called request_queue
2. just add an entry inside the collection with the following structure

```
// for pyload requests
    {
        "name": "my file to download",
        "links": [
            "0": "http://url_to_download/file.mkv",
        "media_type": "<type>"
    }

// for manual requests
    {
        "name": "my file to download",
        "type": "manual",
        "expected_size": "xx GB",
        "media_type": "<type>"
    }
```
3. the mgr will fetch the queue delegating the download request to pyload daemon or to a monitor thread, which will then monitor the download;
4. the stats for the download are pushed to download_running/download_finished collections;