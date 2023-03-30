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
1. create a collection called pyload_queue
2. just add an entry inside the collection with the following structure

```
    {
        "name": "my file to download",
        "links": [
            "0": "http://url_to_download/file.mkv",
    }
```
3. the mgr will fetch the queue delegating the download request to pyload daemon, which will then start it;
4. the stats for the download are requested to pyload and pushed to pyload_download_running/pyload_download_finished collections;