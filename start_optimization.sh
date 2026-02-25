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
    print_header "Start Optimization - Usage"
    echo "This script initializes the environment and starts the optimization loop."
    echo ""
    echo "Usage: ./start_optimization.sh [options]"
    echo ""
    echo "Options:"
    echo "  --iterations <N>       Number of iterations to run (default: 5)"
    echo "  --scad-file <path>     Path to the SCAD file (default: corkscrew.scad)"
    echo "  --case-dir <path>      Path to OpenFOAM case directory (default: corkscrewFilter)"
    echo "  --output-stl <name>    Output STL filename (default: corkscrew_fluid.stl)"
    echo "  --dry-run              Skip actual OpenFOAM execution (mocks everything)"
    echo "  --skip-cfd             Generate geometry but skip CFD simulation"
    echo "  --reuse-mesh           Reuse existing mesh (skips geometry generation and meshing)"
    echo "  --container-engine <E> Force specific container engine (auto, podman, docker)"
    echo "  --cpus <N>             Number of CPUs to use for parallel execution (default: 1)"
    echo "  --no-llm               Disable LLM guidance (use random parameters)"
    echo "  --batch-size <N>       Number of parameter sets to generate per LLM call (default: 5)"
    echo "  --no-cleanup           Disable cleanup of artifacts for non-top runs"
    echo "  --verbose, -v          Enable verbose output"
    echo "  --params-file <file>   Path to a SCAD parameter file to override defaults"
    echo "  -h, --help             Show this help message and exit"
    echo ""
    echo "Example:"
    echo "  ./start_optimization.sh --iterations 10 --cpus 4 --verbose"
}

# Check for Help Flag
check_help "$1"

print_header "Corkscrew Filter Optimization Startup"

# 1. Check Dependencies (OpenSCAD, Node, Python)
if check_openscad; then
    echo "Found native OpenSCAD."
    HAS_OPENSCAD=true
else
    HAS_OPENSCAD=false
fi

# Try to setup node (and install deps if present)
if setup_node_env; then
    HAS_NODE=true
else
    HAS_NODE=false
fi

# Check for OpenSCAD or Node requirement
if [ "$HAS_OPENSCAD" = false ] && [ "$HAS_NODE" = false ]; then
    print_error "Neither 'openscad' nor 'node' found. Please install one of them."
    exit 1
fi

if [ "$HAS_NODE" = false ]; then
     print_warning "Node.js not found. Visualization (PNG) generation will be disabled."
fi

# 2. Check API Key
if [ -z "$GEMINI_API_KEY" ] && [ -z "$OPENAI_API_KEY" ] && [ -z "$OPENAI_BASE_URL" ]; then
    if [[ "$*" == *"--no-llm"* ]] || [ "$NON_INTERACTIVE" == "1" ]; then
        print_warning "No LLM API Key found. Proceeding in dry-run/random mode."
    else
        print_warning "No LLM API Key found (GEMINI_API_KEY, OPENAI_API_KEY, or OPENAI_BASE_URL)."
        echo "The optimizer will run in 'dry-run' or 'random' mode without LLM guidance."
        read -p "Do you want to continue without LLM? (y/n) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
fi

# 3. Setup Python Environment
setup_python_env

# 4. Run Optimizer
print_header "Starting Optimization Loop"
python optimizer/main.py "$@"
