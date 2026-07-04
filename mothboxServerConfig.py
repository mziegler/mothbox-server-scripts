from os.path import join, expanduser



# Directories for photos
PROCESSED_PHOTOS_DIRECTORY_PATH = expanduser("~/mothbox-photos")
NEW_UNPROCESSED_PHOTOS_DIRECTORY_PATH = expanduser("~/mothbox-photos/new-unprocessed")
IN_PROGRESS_PHOTOS_DIRECTORY_PATH = expanduser("~/mothbox-photos/processing-in-progress")

# Metadata folder path
# METADATA_CSV_FILE_PATH = expanduser("~/mothbox-metadata/Manu-Mothbox-Net_deployment-metadata.csv")
METADATA_CSV_FILE_PATH = expanduser("~/mothbox-metadata/Manu-Mothbox-Testing-Metadata.csv")

# Species list path
SPECIES_LIST_PATH = expanduser("~/species-lists/GBIF_Manu_March2026_species_cleaned.csv")

# Level of taxonomic identification to run in the ID step of the pipeline 
# (e.g. 3 for order, 4 for family, 5 for genus, 6 for species)
IDENTIFICATION_RANK = 3



# Logs
RSYNC_LOG_PATH = expanduser("~/mothbox-rsync.log")
AI_PIPELINE_ERROR_LOG = expanduser("~/mothbox-ai-pipeline-errors.log")


# Paths for Mothbot AI processing scripts
class SCRIPT_PATHS:
    MOTHBOT_PROCESS_PYTHON_EXECUTABLE = expanduser("~/Mothbot_Process/.venv-packaging/bin/python")

    MOTHBOT_SCRIPTS_PATH = expanduser("~/Mothbot_Process")
    MOTHBOT_DETECT_SCRIPT_PATH = expanduser(join(MOTHBOT_SCRIPTS_PATH, "pipeline/detect.py"))
    MOTHBOT_ID_SCRIPT_PATH = expanduser(join(MOTHBOT_SCRIPTS_PATH, "pipeline/identify.py"))
    MOTHBOT_INSERTMETADATA_SCRIPT_PATH = expanduser(join(MOTHBOT_SCRIPTS_PATH, "pipeline/insert_metadata.py"))
    MOTHBOT_CLUSTER_SCRIPT_PATH = expanduser(join(MOTHBOT_SCRIPTS_PATH, "pipeline/cluster.py"))
    MOTHBOT_INSERTEXIF_SCRIPT_PATH = expanduser(join(MOTHBOT_SCRIPTS_PATH, "pipeline/insert_exif.py"))

DETECT_YOLO_MODEL_PATH = expanduser("~/Mothbot_Process/trained_models/yolo11m_4500_imgsz1600_b1_2024-01-18.pt")
DETECT_YOLO_IMG_SIZE = 1600




# Mark raw photos for deletion?
MARK_RAW_PHOTOS_FOR_DELETION = True
KEEP_ONE_OUT_OF_EVERY_N_PHOTOS = 10 # Must not be zero or it won't mark any
MATCHING_SUFFIXES_FOR_DELETION = {'.jpg', '.jpeg', '.png', '.dng'} # Only consider files with these suffixes for marking for deletion. This is mainly to avoid deleting the JSON files or other data.


# S3 / Object Storage (Hetzner)
S3_REMOTE = "hetzner-s3"   # name of the rclone remote configured on this machine
S3_BUCKET = "manu-net-data"

# Maximum virtual memory each Mothbot_Process subprocess may use.
# If a step exceeds this, it is killed (returncode < 0) and the daily folder
# is moved to S3 holding-crashing/ for later retry.
PIPELINE_MEMORY_LIMIT_BYTES = 12 * 1024 ** 3  # 12 GB