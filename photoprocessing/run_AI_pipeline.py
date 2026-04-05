import os
import subprocess
import datetime

from mothboxServerConfig import (
    SCRIPT_PATHS,
    DETECT_YOLO_MODEL_PATH,
    DETECT_YOLO_IMG_SIZE,
    AI_PIPELINE_ERROR_LOG,
    SPECIES_LIST_PATH,
    IDENTIFICATION_RANK,
    METADATA_CSV_FILE_PATH,
    MARK_RAW_PHOTOS_FOR_DELETION,
)

from photoprocessing.mark_raw_photos_for_deletion import mark_raw_photos_for_deletion



def run_detect(daily_folder, overwrite_bot=False):
    """Pipeline step 1: detect insects from big mothbox image"""

    cmd = [
        SCRIPT_PATHS.MOTHBOT_PROCESS_PYTHON_EXECUTABLE,
        SCRIPT_PATHS.MOTHBOT_DETECT_SCRIPT_PATH,
        "--input_path", daily_folder,
        "--yolo_model", DETECT_YOLO_MODEL_PATH,
        "--imgsz", str(DETECT_YOLO_IMG_SIZE),
        "--overwrite_prev_bot_detections", str(int(overwrite_bot)),
    ]

    with open(AI_PIPELINE_ERROR_LOG, "a") as error_log:
        result = subprocess.run(cmd, stderr=error_log)
        if result.returncode != 0:
            error_log.write(f"{datetime.datetime.now()}: Error running detect script\n")
            error_log.write('-------------------------------------------------------\n')
            print(f"Error running detect script, check log")



def run_id(daily_folder, chosenrank=IDENTIFICATION_RANK, overwrite_bot=False):
    """Pipeline step 2: identify insects in the clipped insect-detection images."""
   # uv run Mothbot_ID.py --input_path /home/mb/Desktop/mothbox-photos/fluidRobin/photos/fluidRobin_2026-03-30 --taxa_csv /home/mb/species-lists/GBIF_Manu_March2026_species_cleaned.csv --rank 3 --overwrite_prev_bot_ID 1

    cmd = [
            SCRIPT_PATHS.MOTHBOT_PROCESS_PYTHON_EXECUTABLE,
            SCRIPT_PATHS.MOTHBOT_ID_SCRIPT_PATH,
            "--input_path", daily_folder,
            "--taxa_csv", SPECIES_LIST_PATH,
            "--rank", str(chosenrank),
            "--ID_Hum", "1",
            "--ID_Bot", "1",
            "--overwrite_prev_bot_ID",str(int(overwrite_bot))
    ]   
           
    with open(AI_PIPELINE_ERROR_LOG, "a") as error_log:
        result = subprocess.run(cmd, stderr=error_log)
        if result.returncode != 0:
            error_log.write(f"{datetime.datetime.now()}: Error running ID script\n")
            error_log.write('-------------------------------------------------------\n')
            print(f"Error running ID script, check log")



def run_insertmetadata(daily_folder, metadatafile=METADATA_CSV_FILE_PATH):
    """Pipeline step 3: insert metadata from the deployment CSV file into the JSON file for each image."""
   # uv run Mothbot_InsertMetadata.py
            
    cmd = [
        SCRIPT_PATHS.MOTHBOT_PROCESS_PYTHON_EXECUTABLE,
        SCRIPT_PATHS.MOTHBOT_INSERTMETADATA_SCRIPT_PATH,
        "--input_path", daily_folder,
        "--metadata", str(metadatafile),
    ]

    with open(AI_PIPELINE_ERROR_LOG, "a") as error_log:
        result = subprocess.run(cmd, stderr=error_log)
        if result.returncode != 0:
            error_log.write(f"{datetime.datetime.now()}: Error running InsertMetadata script\n")
            error_log.write('-------------------------------------------------------\n')
            print(f"Error running InsertMetadata script, check log")



def run_cluster(daily_folder):
    """Pipeline step 4: perceptual clustering"""
    cmd = [
        SCRIPT_PATHS.MOTHBOT_PROCESS_PYTHON_EXECUTABLE,
        SCRIPT_PATHS.MOTHBOT_CLUSTER_SCRIPT_PATH,
        "--input_path", daily_folder,
        "--ID_Hum", "1",
        "--ID_Bot", "1",
    ]

    with open(AI_PIPELINE_ERROR_LOG, "a") as error_log:
        result = subprocess.run(cmd, stderr=error_log)
        if result.returncode != 0:
            error_log.write(f"{datetime.datetime.now()}: Error running Cluster script\n")
            error_log.write('-------------------------------------------------------\n')
            print(f"Error running Cluster script, check log")


def run_insertEXIF(daily_folder):
    """Pipeline step 5: insert metadata into the image files themselves."""
    cmd = [
        SCRIPT_PATHS.MOTHBOT_PROCESS_PYTHON_EXECUTABLE,
        SCRIPT_PATHS.MOTHBOT_INSERTEXIF_SCRIPT_PATH,
        "--input_path", daily_folder,
        "--ID_Hum", "1",
        "--ID_Bot", "1",
    ]

    with open(AI_PIPELINE_ERROR_LOG, "a") as error_log:
        result = subprocess.run(cmd, stderr=error_log)
        if result.returncode != 0:
            error_log.write(f"{datetime.datetime.now()}: Error running InsertEXIF script\n")
            error_log.write('-------------------------------------------------------\n')
            print(f"Error running InsertEXIF script, check log")



def run_full_AI_pipeline(daily_folder, overwrite_bot=False, metadatafile=METADATA_CSV_FILE_PATH):
    """Run the full pipeline for a given daily folder, with error logging."""
    run_detect(daily_folder, overwrite_bot=overwrite_bot)
    run_id(daily_folder, overwrite_bot=overwrite_bot)
    run_insertmetadata(daily_folder, metadatafile=metadatafile)
    run_cluster(daily_folder)
    run_insertEXIF(daily_folder)

    if MARK_RAW_PHOTOS_FOR_DELETION:
        mark_raw_photos_for_deletion(daily_folder)