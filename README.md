# mothbox-server-scripts
Server scripts/configuration for Mothbox network

Does the following things:
1. Fetches photos from network-connected Mothboxes every night, saves them on local disc
2. Runs Mothbot_Process AI pipeline on new photos as they come in (at the end of each night)
3. Moves processed photos into cloud storage 

## To run:
* Create a user called "mb"
* Install rclone and run `rclone config` to set up the connection for photo storage
* Make sure all Mothboxes are reachable on the network, (the easiest way I've found is by using TailScale), and record them in mothbox-list.csv. Make sure that your server is properly set up to SSH into them; that the appropriate keys are set up on on both your server and the mothboxes. Edit your server's .ssh/config file so that the user on the mothboxes is "pi".
* Review the settings in mothboxServerConfig.py
* Clone this repository into /home/mb/mothbox-server-scripts

```
sudo cp /home/mb/mothbox-server-scripts/deploy/mothbox.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now mothbox.service
```

(or `sudo systemctl restart snap.docker.dockerd.service` if Docker is installed via Snap)



## Monitoring output:
1. Live output from both containers at once

```
cd /home/mb/mothbox-server-scripts
docker compose logs -f
```

To monitor just one of the containers:

```
docker compose logs -f rsync
docker compose logs -f pipeline
```

2. The log files on disk (persisted across container restarts, good for history)

```
# Rsync activity — which devices were contacted and what was transferred
tail -f /home/mb/logs/mothbox-rsync.log

# AI pipeline errors — non-zero exit codes and OOM crashes
tail -f /home/mb/logs/mothbox-ai-pipeline-errors.log
```

3. systemd journal (useful if the containers fail to start at all, or docker compose up itself crashes)

```
journalctl -u mothbox.service -f
```

4. Container resource usage (memory is the most useful one given the OOM issue — watch the pipeline container approach the 14 GB limit)
```
docker stats
```