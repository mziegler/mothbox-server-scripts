# mothbox-server-scripts
Server scripts/configuration for Mothbox network

Does the following things:
1. Fetches photos from network-connected Mothboxes every night, saves them on local disc
2. Runs Mothbot_Process AI pipeline on new photos as they come in (at the end of each night)
3. Moves processed photos into cloud storage
4. Serves each device's latest photo publicly, for a "livestream" dashboard

## To run:
* Create a user called "mb"
* Install rclone and run `rclone config` to set up the connection for photo storage
* Make sure all Mothboxes are reachable on the network, (the easiest way I've found is by using TailScale). For each Mothbox, run `rclone config` to set up a remote (e.g. an SFTP remote named `mothbox-<mothboxName>`) that can reach `pi@<hostOrIP>`, then record the device in mothbox-list.csv, including the rclone remote's name in the `rcloneRemote` column — `mothbox_photo_pull.py` uses that column to know where to pull photos from.
* Review the settings in mothboxServerConfig.py
* Clone this repository into /home/mb/mothbox-server-scripts
* Create `~/mothbox-photos/latest` owned by `mb` *before* the containers first
  start: `mkdir -p ~/mothbox-photos/latest`. The `livestream` container bind-mounts
  this path, and if it doesn't exist yet, Docker (running as root) auto-creates it
  as root — which then blocks the `photo-pull` container's non-root `mb` user from
  writing the dashboard/photos into it.

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
docker compose logs -f photo-pull
docker compose logs -f pipeline
```

2. The log files on disk (persisted across container restarts, good for history)

```
# Photo-pull activity — which devices were contacted and what was transferred
tail -f /home/mb/logs/mothbox-photo-pull.log

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

## Public livestream

`mothbox_photo_pull.py` copies each device's newest synced photo to
`~/mothbox-photos/latest/<mothboxName>.jpg` after every pull (see
`livestream.py`), and writes a static dashboard (`index.html`) listing all
devices from `mothbox-list.csv`. The `livestream` service in
`docker-compose.yml` serves that folder over plain HTTP on port 8080 (no
image build required, stock `nginx:alpine`).

**To turn this off entirely**, set `LIVESTREAM_ENABLED = False` in
`mothboxServerConfig.py`. `mothbox_photo_pull.py` then stops updating latest
photos, and the dashboard is replaced with a static "disabled" notice —
so even if the `livestream` container is left running, it won't keep
serving stale photos. No other files need to change.

This is intentionally *not* meant to be exposed to the public directly —
put a CDN cache in front of it so viewer traffic never hits this VM:

1. Open port 8080 to the internet (firewall rule on the VM / Hetzner
   Cloud firewall).
2. In Cloudflare, add an **A record** for a subdomain (e.g.
   `livestream.yourdomain.com`) pointing at the VM's IP, with the orange
   cloud (proxy) turned **on**.
3. Cloudflare's free plan already caches `.jpg`/`.png` by file extension
   and respects the `Cache-Control: max-age=60` header set in
   `livestream/nginx.conf` — no paid plan needed. Optionally add a free
   **Page Rule** (`livestream.yourdomain.com/*` → Cache Level: Cache
   Everything, Edge Cache TTL: 1 minute) so the dashboard HTML is cached
   too, not just the images.
4. SSL: easiest is Cloudflare's **Flexible** SSL mode (visitors get
   HTTPS from Cloudflare; the VM keeps serving plain HTTP on 8080).

With this in place, Cloudflare's edge absorbs public traffic — the VM
only sees roughly one request per device per cache TTL, regardless of
viewer count.