#!/bin/bash
# lib/utils.sh
# Shared utility functions for shell scripts

# Set colors if terminal supports it
if [ -t 1 ]; then
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    BLUE='\033[0;34m'
    NC='\033[0m' # No Color
else
    RED=''
    GREEN=''
    YELLOW=''
    BLUE=''
    NC=''
fi

print_header() {
    echo -e "${BLUE}=== $1 ===${NC}"
}

print_error() {
    echo -e "${RED}Error: $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}Warning: $1${NC}"
}

check_help() {
    # If the first argument is -h or --help, call usage function and exit
    if [[ "$1" == "-h" || "$1" == "--help" ]]; then
        if declare -f usage > /dev/null; then
            usage
            exit 0
        else
            echo "No usage information available."
            exit 1
        fi
    fi
}

check_openscad() {
    if command -v openscad &> /dev/null; then
        # echo "Found native OpenSCAD."
        return 0
    else
        return 1
    fi
}

setup_node_env() {
    if command -v node &> /dev/null; then
        # Ensure dependencies for export.js are installed if package.json exists
        if [ -f "package.json" ]; then
             if [ ! -d "node_modules" ]; then
                echo "Installing Node.js dependencies..."
                npm install > /dev/null 2>&1 || {
                    print_error "npm install failed."
                    exit 1
                }
             fi
        fi
        return 0
    else
        return 1
    fi
}

setup_python_env() {
    VENV_DIR=".venv"

    # Detect Python Executable
    PYTHON_CMD=""
    if command -v python3 &> /dev/null; then
        PYTHON_CMD="python3"
    elif command -v python &> /dev/null; then
        PYTHON_CMD="python"
    elif command -v py &> /dev/null; then
        PYTHON_CMD="py"
    else
        print_error "Python not found (tried 'python3', 'python', 'py'). Please install Python."
        exit 1
    fi
    # echo "Using Python executable: $PYTHON_CMD"

    if [ ! -d "$VENV_DIR" ]; then
        echo "Creating Python virtual environment in $VENV_DIR..."
        "$PYTHON_CMD" -m venv "$VENV_DIR"
    fi

    # Activate venv
    if [ -f "$VENV_DIR/Scripts/activate" ]; then
        # Windows (Git Bash)
        source "$VENV_DIR/Scripts/activate"
    elif [ -f "$VENV_DIR/bin/activate" ]; then
        # Unix
        source "$VENV_DIR/bin/activate"
    else
        print_error "Virtual environment activation script not found in $VENV_DIR."
        exit 1
    fi

    if [ -f "optimizer/requirements.txt" ]; then
        # echo "Checking Python requirements..."
        # Use pip to install requirements quietly, only show error on failure
        if ! pip install -r optimizer/requirements.txt > .pip_install.log 2>&1; then
            print_error "Failed to install Python requirements. See .pip_install.log for details:"
            head -n 20 .pip_install.log
            if [ $(wc -l < .pip_install.log) -gt 20 ]; then
                echo "..."
                tail -n 10 .pip_install.log
            fi
            exit 1
        fi
    fi
}
