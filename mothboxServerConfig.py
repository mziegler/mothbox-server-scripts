from os.path import join, expanduser



# Directories for photos
PROCESSED_PHOTOS_DIRECTORY_PATH = expanduser("~/mothbox-photos/processed")
NEW_UNPROCESSED_PHOTOS_DIRECTORY_PATH = expanduser("~/mothbox-photos/new-unprocessed")
IN_PROGRESS_PHOTOS_DIRECTORY_PATH = expanduser("~/mothbox-photos/processing-in-progress")

# Metadata folder path
# METADATA_CSV_FILE_PATH = expanduser("~/mothbox-metadata/Manu-Mothbox-Net_deployment-metadata.csv")
METADATA_CSV_FILE_PATH = expanduser("~/mothbox-metadata/Manu-Mothbox_combined-metadata.csv")

# Species list path
SPECIES_LIST_PATH = expanduser("~/species-lists/GBIF_Manu_March2026_species_cleaned.csv")

# Level of taxonomic identification to run in the ID step of the pipeline 
# (e.g. 3 for order, 4 for family, 5 for genus, 6 for species)
IDENTIFICATION_RANK = 3



# Logs
PHOTO_PULL_LOG_PATH = expanduser("~/logs/mothbox-photo-pull.log")
AI_PIPELINE_ERROR_LOG = expanduser("~/logs/mothbox-ai-pipeline-errors.log")


# Paths for Mothbot AI processing scripts
class SCRIPT_PATHS:
    MOTHBOT_PROCESS_PYTHON_EXECUTABLE = expanduser("~/Mothbot_Process/.venv-packaging/bin/python")

    MOTHBOT_SCRIPTS_PATH = expanduser("~/Mothbot_Process")
    MOTHBOT_DETECT_SCRIPT_PATH = expanduser(join(MOTHBOT_SCRIPTS_PATH, "pipeline/detect.py"))
    MOTHBOT_ID_SCRIPT_PATH = expanduser(join(MOTHBOT_SCRIPTS_PATH, "pipeline/identify.py"))
    MOTHBOT_INSERTMETADATA_SCRIPT_PATH = expanduser(join(MOTHBOT_SCRIPTS_PATH, "pipeline/insert_metadata.py"))
    MOTHBOT_CLUSTER_SCRIPT_PATH = expanduser(join(MOTHBOT_SCRIPTS_PATH, "pipeline/cluster.py"))
    MOTHBOT_INSERTEXIF_SCRIPT_PATH = expanduser(join(MOTHBOT_SCRIPTS_PATH, "pipeline/insert_exif.py"))

DETECT_YOLO_MODEL_PATH = expanduser("~/Mothbot_Process/trained_models/MBD-0-2.pt")
DETECT_YOLO_IMG_SIZE = 1600




# Mark raw photos for deletion?
MARK_RAW_PHOTOS_FOR_DELETION = True
KEEP_ONE_OUT_OF_EVERY_N_PHOTOS = 10 # Must not be zero or it won't mark any
MATCHING_SUFFIXES_FOR_DELETION = {'.jpg', '.jpeg', '.png', '.dng'} # Only consider files with these suffixes for marking for deletion. This is mainly to avoid deleting the JSON files or other data.


# S3 / Object Storage (Hetzner)
S3_REMOTE = "hetzner-s3"   # name of the rclone remote configured on this machine
S3_BUCKET = "manu-mothbox"
S3_KEY_PREFIX = "manu-net-deployments/" # base folder for data uploaded to the S3 bucket

# Maximum virtual memory each Mothbot_Process subprocess may use.
# If a step exceeds this, it is killed (returncode < 0) and the daily folder
# is moved to S3 holding-crashing/ for later retry.
PIPELINE_MEMORY_LIMIT_BYTES = 12 * 1024 ** 3  # 12 GB

# How long the pipeline daemon sleeps between checks when there are no folders to process.
PIPELINE_IDLE_SLEEP_SECONDS = 30 * 60  # 30 minutes

# Photo-pull schedule
# IANA timezone name for the deployment site. Used by mothbox_photo_pull.py to
# determine whether the current time is inside the nightly collection window.
CAMERA_TIMEZONE = "America/Lima"   # UTC-5, no DST

# Nightly collection window (local time at the deployment site).
# The photo-pull daemon runs every PHOTO_PULL_POLL_INTERVAL_SECONDS during
# [COLLECTION_START_HOUR, COLLECTION_END_HOUR).
COLLECTION_START_HOUR = 18   # 6 PM
COLLECTION_END_HOUR   = 6    # 6 AM (next morning)
PHOTO_PULL_POLL_INTERVAL_SECONDS = 20

# Skip files on the Mothbox that were last modified more recently than this.
# The camera writes each photo incrementally, so a file that's still being
# written keeps growing after rclone has already stat'd it -- pulling it
# mid-write produces a "corrupted on transfer: sizes differ" error. Kept
# short so the livestream stays close to real-time; if it's ever too short
# for a particular file, that's harmless -- rclone just logs the same error
# and picks the file up on the next poll instead.
PHOTO_PULL_MIN_FILE_AGE = "10s"

# Hard ceiling on how long a single device's rclone pull may run per poll.
# Mothboxes lose connectivity (or power off) on their own schedule, and when
# that happens mid-transfer, rclone's own --timeout doesn't reliably notice --
# an SFTP connection can sit at 0 B/s indefinitely without erroring. This
# subprocess-level timeout is the real backstop. If it fires, the transfer is
# simply retried on the next poll: rclone move never deletes a source file
# until it's confirmed to have copied successfully, so nothing is lost.
PHOTO_PULL_TRANSFER_TIMEOUT_SECONDS = 10 * 60  # 10 minutes

# How long a daily folder must be unmodified (no photo-pull writes) before the
# pipeline is allowed to move it to in-progress.  This prevents the race
# condition where the pipeline moves a folder while the photo-pull daemon is
# still writing to it.  During the collection window it writes every
# PHOTO_PULL_POLL_INTERVAL_SECONDS, so the folder is never idle.  After the
# Mothbox shuts off, photos stop arriving and the folder goes quiet — the
# pipeline waits this long before processing it.
FOLDER_MIN_IDLE_MINUTES = 65


# Public "latest photo" livestream feature.
# After each photo pull, mothbox_photo_pull.py copies the newest synced photo
# for each device here (see livestream.py). Served publicly by the 'livestream'
# nginx container (docker-compose.yml), meant to sit behind a CDN cache
# (e.g. Cloudflare) so public traffic never hits this VM directly.
#
# Set to False to turn the feature off: livestream.py stops updating latest
# photos/dashboard, and instead writes a static "disabled" notice, so the
# nginx container (if still running) doesn't keep serving stale photos.
LIVESTREAM_ENABLED = True

LATEST_PHOTOS_DIRECTORY_PATH = expanduser("~/mothbox-photos/latest")
LATEST_PHOTO_EXTENSIONS = {'.jpg', '.jpeg', '.png'}

# How often the dashboard reloads images and the cache TTL images are served with.
# Keep in sync with DEFAULT_REFRESH_MS in livestream/static/app.js and the
# max-age values set in livestream/nginx.conf.
LIVESTREAM_REFRESH_SECONDS = 20

# Hours (0-23, in CAMERA_TIMEZONE local time) during which the Mothbox hardware
# is expected to be powered on. Edit this to match your own deployment's power
# schedule -- any pattern works (alternating, continuous overnight, a different
# offset, etc). Hours not in this set are simply "off", which also naturally
# covers hours outside the nightly window entirely, with no special-casing.
MOTHBOX_ON_HOURS = {18, 20, 22, 0, 2, 4}

# How old (in minutes) a device's latest photo can be, while the device is
# expected to be on, before the livestream dashboard flags a possible power
# outage or technical problem. Generous slack for rclone retries and the
# PHOTO_PULL_TRANSFER_TIMEOUT_SECONDS above before crying wolf.
LIVESTREAM_STALE_MINUTES = 10

# Minutes of slack after a device's scheduled on-transition (see
# MOTHBOX_ON_HOURS) before a stale photo is flagged as a possible outage.
# The hardware takes a couple of minutes to boot and connect after power-on,
# during which the newest photo on file is still the last one from its
# previous on-cycle -- long enough to trip LIVESTREAM_STALE_MINUTES on its
# own, which would otherwise misreport a normal boot-up as an outage.
LIVESTREAM_BOOT_GRACE_MINUTES = 7
