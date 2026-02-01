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
    echo "Warning: GEMINI_API_KEY is not set. The optimizer will run in 'dry-run' or 'random' mode without LLM guidance."
    read -p "Do you want to continue without LLM? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# 3. Setup Python Environment
if [ -f "optimizer/requirements.txt" ]; then
    echo "Installing Python requirements..."
    pip install -r optimizer/requirements.txt
fi

# 4. Run Optimizer
echo "Starting Optimization Loop..."
# Pass arguments if any
python optimizer/main.py "$@"
