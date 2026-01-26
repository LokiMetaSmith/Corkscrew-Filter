# Use the official OpenFOAM image as the base
FROM opencfd/openfoam-default:2406

# Switch to root to install dependencies
USER root

# Install system dependencies
# OpenSCAD for geometry generation
# Python3 and pip for the orchestrator script
RUN apt-get update && apt-get install -y \
    openscad \
    python3 \
    python3-pip \
    python3-venv \
    && rm -rf /var/lib/apt/lists/*

# Set up a python virtual environment (optional, but good practice)
ENV VIRTUAL_ENV=/opt/venv
RUN python3 -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Install Python dependencies
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Create a working directory
WORKDIR /app

# The user 'openfoam' is the default in the base image, but we might need to fix permissions
# depending on how volumes are mounted. For now, we stay as root or switch back to openfoam.
# Staying as root simplifies permission issues in containers often, but...
# Let's switch to the openfoam user if possible, but we need to ensure they can write.
# For this tool, running as root inside the container is often easiest for CI/CD like tasks.
# But let's try to be nice.
RUN chown -R openfoam:openfoam /app

USER openfoam

# Copy the optimizer scripts (when building the image)
# COPY . /app
# Or we assume the volume is mounted at runtime.

# Entry point
CMD ["python3", "optimizer/main.py"]
