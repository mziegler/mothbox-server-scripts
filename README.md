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
* Make sure all Mothboxes are reachable on the network, (the easiest way I've found is by using TailScale). For each Mothbox, run `rclone config` to set up a remote (e.g. an SFTP remote named `mothbox-<mothboxName>`) that can reach `pi@<mothbox's host or IP>`, then record the device in mothbox-list.csv, including the rclone remote's name in the `rcloneRemote` column — `mothbox_photo_pull.py` uses that column to know where to pull photos from. Also fill in `friendlyName` (a human-readable display name shown on the public livestream page) and, optionally, `description` (a short blurb shown under the device's name).
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

* Install the logrotate config, so the log files in `~/logs` don't grow unbounded:

```
sudo cp /home/mb/mothbox-server-scripts/deploy/mothbox.logrotate /etc/logrotate.d/mothbox
```

  This rotates `mothbox-photo-pull.log` and `mothbox-ai-pipeline-errors.log`
  weekly or once either passes 10 MB (whichever comes first), keeping 8
  compressed backups of each. No app restart or signal is needed — both
  `mothbox_photo_pull.py` and `run_AI_pipeline.py` reopen their log file by
  path on every write, so they pick up the freshly-rotated file
  automatically. Most Debian/Ubuntu systems already run `logrotate` daily
  via cron/systemd timer, so this takes effect without any further setup.



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

The livestream page is split into a static frontend and a small piece of
dynamic data, rather than a server-generated page:

* **`livestream/static/`** — the frontend (`index.html`, `style.css`,
  `app.js`), hand-written and committed to this repo. It's never generated
  or touched by Python; edit these files directly to change the page's
  look, the "About" text/links, or add images.
* **`mothboxes.json`** — the only dynamic input, written by
  `livestream.py` every `PHOTO_PULL_POLL_INTERVAL_SECONDS` (see
  `mothbox_photo_pull.py`'s main loop). It lists each device's friendly
  name, latest photo, and a computed schedule/outage status. `app.js`
  fetches this file on load and re-fetches it every
  `LIVESTREAM_REFRESH_SECONDS` to keep the page current without a full
  page reload.
* `mothbox_photo_pull.py` also still copies each device's newest synced
  photo to `~/mothbox-photos/latest/<mothboxName>.jpg` after every pull
  (see `livestream.py`).

The `livestream` service in `docker-compose.yml` mounts both pieces into
one nginx container (no image build required, stock `nginx:alpine`),
serving `livestream/static/` at the docroot and
`~/mothbox-photos/latest` (photos + `mothboxes.json`) under `/data`:

```
docroot (/)   <- ./livestream/static (index.html, style.css, app.js)
/data/*.jpg   <- ~/mothbox-photos/latest/*.jpg
/data/mothboxes.json <- ~/mothbox-photos/latest/mothboxes.json
```

`livestream/static/data/` is a committed empty directory (kept via
`.gitkeep`) that exists purely so Docker has an existing mountpoint to
bind the second volume onto — the first volume mounts `livestream/static`
read-only, and Docker can't auto-create a mountpoint inside a read-only
bind at container start. Don't delete this empty folder.

**Mothbox on/off schedule**: each device's expected power state is
computed from `MOTHBOX_ON_HOURS` in `mothboxServerConfig.py` — an
explicit set of hours (0–23, local `CAMERA_TIMEZONE`) when the hardware
is powered on. This defaults to the current alternating 6pm–5am Peru-time
schedule, but is a plain editable set, so other deployments with a
different schedule (continuous overnight run, a different offset, etc.)
just need to edit that one line. Hours outside the set are treated as
"off"; a device is only flagged with a possible power outage / technical
problem warning if its latest photo is older than `LIVESTREAM_STALE_MINUTES`
while it's expected to be on.

**To turn this off entirely**, set `LIVESTREAM_ENABLED = False` in
`mothboxServerConfig.py`. `mothbox_photo_pull.py` then stops updating latest
photos, and `mothboxes.json` is replaced with `{"enabled": false}`, which
`app.js` renders as a "disabled" notice — so even if the `livestream`
container is left running, it won't keep serving stale photos. No other
files need to change.

This is intentionally *not* meant to be exposed to the public directly —
put a CDN cache in front of it so viewer traffic never hits this VM:

1. Open port 8080 to the internet (firewall rule on the VM / Hetzner
   Cloud firewall).
2. In Cloudflare, add an **A record** for a subdomain (e.g.
   `livestream.yourdomain.com`) pointing at the VM's IP, with the orange
   cloud (proxy) turned **on**.
3. Cloudflare's free plan already caches `.jpg`/`.png` by file extension
   and respects the per-path `Cache-Control` headers set in
   `livestream/nginx.conf` (20s for photos, 10s for `mothboxes.json`, 5
   minutes for the static `index.html`/`style.css`/`app.js`) — no paid
   plan needed. Note that by default the free plan only caches by file
   extension, so `mothboxes.json` isn't cached at Cloudflare's edge at all
   unless you've added the Page Rule below — if you have, its `max-age=10`
   still applies, but it's an extra hop of caching worth knowing about.
   Optionally add a free **Page Rule**
   (`livestream.yourdomain.com/*` → Cache Level: Cache Everything) so
   every path is cached at the edge, not just images by extension;
   origin `Cache-Control` headers still govern each file's TTL.
4. SSL: easiest is Cloudflare's **Flexible** SSL mode (visitors get
   HTTPS from Cloudflare; the VM keeps serving plain HTTP on 8080).

With this in place, Cloudflare's edge absorbs public traffic — the VM
only sees roughly one request per device per cache TTL, regardless of
viewer count.