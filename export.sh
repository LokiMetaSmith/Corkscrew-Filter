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
    print_header "Export Utility - Usage"
    echo "This script wraps export.js to generate STL and PNG files from OpenSCAD models."
    echo ""
    echo "Usage: ./export.sh [options] [input_file]"
    echo ""
    echo "Options:"
    echo "  -o <output_file>       Specify output filename (e.g., output.stl)"
    echo "  --png                  Generate PNG images (requires -o)"
    echo "  --params <file>        Path to a SCAD parameter file to override defaults"
    echo "  -D <var>=<val>         Override OpenSCAD variable"
    echo "  -h, --help             Show this help message and exit"
    echo ""
    echo "Examples:"
    echo "  ./export.sh -o output.stl corkscrew.scad"
    echo "  ./export.sh -o output.stl --png -D height=50 corkscrew.scad"
    echo "  ./export.sh --params my_params.scad -o output.stl corkscrew.scad"
}

# Check for Help Flag
check_help "$1"

# Setup Node Environment
if ! setup_node_env; then
    print_error "Node.js environment setup failed. Node.js is required for export."
    exit 1
fi

# Run Export Script
node export.js "$@"
