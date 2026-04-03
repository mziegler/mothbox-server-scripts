from os.path import join, expanduser



# Directories for photos
PROCESSED_PHOTOS_DIRECTORY_PATH = expanduser("~/Desktop/mothbox-photos")
NEW_UNPROCESSED_PHOTOS_DIRECTORY_PATH = expanduser("~/Desktop/mothbox-photos/new-unprocessed")
IN_PROGRESS_PHOTOS_DIRECTORY_PATH = expanduser("~/Desktop/mothbox-photos/processing-in-progress")

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