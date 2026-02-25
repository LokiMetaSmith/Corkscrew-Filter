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
    print_header "Render Wireframe - Usage"
    echo "This script renders a depth-cued wireframe image from STL files."
    echo ""
    echo "Usage: ./render.sh [options] [output_image] [main_stl] [casing_stl]"
    echo ""
    echo "Options:"
    echo "  -h, --help             Show this help message and exit"
    echo ""
    echo "Arguments:"
    echo "  output_image           Path to save the PNG image."
    echo "  main_stl               Path to the primary STL file."
    echo "  casing_stl             (Optional) Path to a casing/frame STL file (rendered faintly)."
    echo ""
    echo "Examples:"
    echo "  ./render.sh output.png part.stl"
    echo "  ./render.sh output.png part.stl casing.stl"
    echo ""
    echo "Default (no args):"
    echo "  Renders 'images/temp_helical.stl' to 'images/Wireframe view of Helical Geometry.png'"
    echo "  and optionally composites 'images/temp_casing.stl'."
}

# Check for Help Flag
check_help "$1"

# Setup Python Environment
setup_python_env

# Run Renderer
python render_depth_wireframe.py "$@"
