#!/bin/bash
set -e

# Load Utility Functions
if [ -f "lib/utils.sh" ]; then
    source lib/utils.sh
else
    echo "Error: lib/utils.sh not found."
    exit 1
fi

# Function to print usage
usage() {
    print_header "Physics Calculation - Usage"
    echo "This script calculates and displays relevant physics parameters (Reynolds, Dean, Stokes numbers)"
    echo "based on predefined geometry and fluid properties."
    echo ""
    echo "Usage: ./physics.sh [options]"
    echo ""
    echo "Options:"
    echo "  -h, --help             Show this help message and exit"
    echo ""
    echo "Description:"
    echo "  The script runs 'calculate_physics.py' which uses hardcoded parameters"
    echo "  (e.g., 3/4 inch tube, air properties) to estimate flow regimes."
}

# Check for Help Flag
check_help "$1"

# Setup Python Environment
setup_python_env

# Run Physics Calculation
python calculate_physics.py
