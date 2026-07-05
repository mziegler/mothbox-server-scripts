FROM python:3.11-slim

# System dependencies — run as root
RUN apt-get update && apt-get install -y --no-install-recommends \
    rsync \
    git \
    curl \
    make \
    unzip \
    libgl1 \
    libglib2.0-0 \
    libexiv2-dev \
    && rm -rf /var/lib/apt/lists/*

# Install rclone (used for S3 archive and crash-holding uploads)
RUN curl -fsSL https://rclone.org/install.sh | bash

# Create the mb user to match the server account
RUN useradd -m -s /bin/bash mb

# Switch to mb for all application-level installs so files are owned correctly
USER mb

# ---------------------------------------------------------------------------
# Install Mothbot_Process AI pipeline — pinned to the latest GitHub release
# NOTE: After cloning, verify that the paths in SCRIPT_PATHS (mothboxServerConfig.py)
# match the actual script locations in the cloned repo.
# ---------------------------------------------------------------------------
WORKDIR /home/mb/Mothbot_Process
RUN LATEST_TAG=$(curl -fsSL \
        -H "Accept: application/vnd.github.v3+json" \
        "https://api.github.com/repos/Digital-Naturalism-Laboratories/Mothbot_Process/releases/latest" \
        | grep '"tag_name"' | sed 's/.*"tag_name": "\(.*\)".*/\1/') \
    && echo "Cloning Mothbot_Process $LATEST_TAG" \
    && git clone --depth 1 --branch "$LATEST_TAG" \
        https://github.com/Digital-Naturalism-Laboratories/Mothbot_Process.git .

# make setup creates .venv-packaging with CPU-only dependencies
RUN make setup

# ---------------------------------------------------------------------------
# Install mothbox-server-scripts
# ---------------------------------------------------------------------------
WORKDIR /home/mb/mothbox-server-scripts
COPY --chown=mb:mb . .
RUN pip install --no-cache-dir -r requirements.txt

# Working directories (actual data is bind-mounted from the host at runtime)
RUN mkdir -p \
    /home/mb/mothbox-photos/new-unprocessed \
    /home/mb/mothbox-photos/processing-in-progress \
    /home/mb/mothbox-metadata \
    /home/mb/species-lists \
    /home/mb/logs

WORKDIR /home/mb/mothbox-server-scripts
ENTRYPOINT ["python3", "-m", "photoprocessing.pipeline_schedule_manager"]
