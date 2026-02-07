#!/bin/bash
set -e

echo "=== Corkscrew Filter Optimization Startup ==="

# 1. Check Dependencies
if ! command -v openscad &> /dev/null; then
    if ! command -v node &> /dev/null; then
        echo "Error: Neither 'openscad' nor 'node' found. Please install one of them."
        exit 1
    else
        echo "Native OpenSCAD not found, will use Node.js fallback (openscad-wasm)."
        # Ensure dependencies for export.js are installed
        if [ ! -d "node_modules" ]; then
            echo "Installing Node.js dependencies..."
            npm install
        fi
    fi
else
    echo "Found native OpenSCAD."
fi

# 2. Check API Key
if [ -z "$GEMINI_API_KEY" ]; then
    if [[ "$*" == *"--no-llm"* ]] || [ "$NON_INTERACTIVE" == "1" ]; then
        echo "Warning: GEMINI_API_KEY is not set. Proceeding in dry-run/random mode (prompt suppressed)."
    else
        echo "Warning: GEMINI_API_KEY is not set. The optimizer will run in 'dry-run' or 'random' mode without LLM guidance."
        read -p "Do you want to continue without LLM? (y/n) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
fi

# 3. Setup Python Environment
VENV_DIR=".venv"

# Detect Python Executable
PYTHON_CMD=""
if command -v python &> /dev/null; then
    PYTHON_CMD="python"
elif command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v py &> /dev/null; then
    PYTHON_CMD="py"
else
    echo "Error: Python not found (tried 'python', 'python3', 'py'). Please install Python."
    exit 1
fi
echo "Using Python executable: $PYTHON_CMD"

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
    echo "Error: Virtual environment activation script not found in $VENV_DIR."
    exit 1
fi

if [ -f "optimizer/requirements.txt" ]; then
    echo "Installing/Updating Python requirements..."
    pip install -r optimizer/requirements.txt
fi

# 4. Run Optimizer
echo "Starting Optimization Loop..."
# Pass arguments if any
python optimizer/main.py "$@"
