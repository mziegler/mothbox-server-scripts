import os
import resource
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
    PIPELINE_MEMORY_LIMIT_BYTES,
)

from photoprocessing.mark_raw_photos_for_deletion import mark_raw_photos_for_deletion


class PipelineCrashError(RuntimeError):
    """Raised when a pipeline subprocess is killed by a signal (e.g. OOM)."""
    pass


def _apply_memory_limit():
    """Preexec function: cap the child process's virtual address space."""
    resource.setrlimit(
        resource.RLIMIT_AS,
        (PIPELINE_MEMORY_LIMIT_BYTES, PIPELINE_MEMORY_LIMIT_BYTES),
    )


def _run_step(cmd, step_name):
    """Run a pipeline subprocess with memory limit and unified error handling.

    Raises PipelineCrashError if the process was killed by a signal (returncode < 0),
    which indicates an OOM or other hard crash.  Non-zero exits that are not
    signal-kills are logged but do not abort the pipeline.
    """
    with open(AI_PIPELINE_ERROR_LOG, "a") as error_log:
        result = subprocess.run(cmd, stderr=error_log, preexec_fn=_apply_memory_limit)
        if result.returncode < 0:
            msg = (
                f"{datetime.datetime.now()}: {step_name} killed by signal "
                f"{-result.returncode} (OOM or crash)\n"
                f"-------------------------------------------------------\n"
            )
            error_log.write(msg)
            raise PipelineCrashError(msg.strip())
        elif result.returncode != 0:
            error_log.write(
                f"{datetime.datetime.now()}: Error running {step_name} "
                f"(exit {result.returncode})\n"
                f"-------------------------------------------------------\n"
            )
            print(f"Error running {step_name}, check log")


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
    _run_step(cmd, "detect")


def run_id(daily_folder, chosenrank=IDENTIFICATION_RANK, overwrite_bot=False):
    """Pipeline step 2: identify insects in the clipped insect-detection images."""
    cmd = [
        SCRIPT_PATHS.MOTHBOT_PROCESS_PYTHON_EXECUTABLE,
        SCRIPT_PATHS.MOTHBOT_ID_SCRIPT_PATH,
        "--input_path", daily_folder,
        "--taxa_csv", SPECIES_LIST_PATH,
        "--rank", str(chosenrank),
        "--ID_Hum", "1",
        "--ID_Bot", "1",
        "--overwrite_prev_bot_ID", str(int(overwrite_bot)),
    ]
    _run_step(cmd, "identify")


def run_insertmetadata(daily_folder, metadatafile=METADATA_CSV_FILE_PATH):
    """Pipeline step 3: insert metadata from the deployment CSV file into the JSON file for each image."""
    cmd = [
        SCRIPT_PATHS.MOTHBOT_PROCESS_PYTHON_EXECUTABLE,
        SCRIPT_PATHS.MOTHBOT_INSERTMETADATA_SCRIPT_PATH,
        "--input_path", daily_folder,
        "--metadata", str(metadatafile),
    ]
    _run_step(cmd, "insert_metadata")


def run_cluster(daily_folder):
    """Pipeline step 4: perceptual clustering"""
    cmd = [
        SCRIPT_PATHS.MOTHBOT_PROCESS_PYTHON_EXECUTABLE,
        SCRIPT_PATHS.MOTHBOT_CLUSTER_SCRIPT_PATH,
        "--input_path", daily_folder,
        "--ID_Hum", "1",
        "--ID_Bot", "1",
    ]
    _run_step(cmd, "cluster")


def run_insertEXIF(daily_folder):
    """Pipeline step 5: insert metadata into the image files themselves."""
    cmd = [
        SCRIPT_PATHS.MOTHBOT_PROCESS_PYTHON_EXECUTABLE,
        SCRIPT_PATHS.MOTHBOT_INSERTEXIF_SCRIPT_PATH,
        "--input_path", daily_folder,
        "--ID_Hum", "1",
        "--ID_Bot", "1",
    ]
    _run_step(cmd, "insert_exif")


def run_full_AI_pipeline(daily_folder, overwrite_bot=False, metadatafile=METADATA_CSV_FILE_PATH):
    """Run the full pipeline for a given daily folder.

    Raises PipelineCrashError if any step is killed by a signal.
    """
    run_detect(daily_folder, overwrite_bot=overwrite_bot)
    run_cluster(daily_folder)
    run_id(daily_folder, overwrite_bot=overwrite_bot)
    run_insertmetadata(daily_folder, metadatafile=metadatafile)
    run_insertEXIF(daily_folder)

    if MARK_RAW_PHOTOS_FOR_DELETION:
        mark_raw_photos_for_deletion(daily_folder)