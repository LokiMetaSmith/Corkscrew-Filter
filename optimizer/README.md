# AI-Driven Design Optimization

This directory contains a suite of tools to automate the design optimization of the Thirsty Corkscrew filter using Generative AI. The system iterates through design parameters, generates 3D geometry, runs CFD simulations to evaluate performance, and uses a Large Language Model (LLM) to suggest improvements.

## Overview

The optimization loop consists of the following steps:
1.  **Parameter Selection**: The system starts with an initial set of parameters or takes suggestions from the LLM.
2.  **Geometry Generation**: `scad_driver.py` uses OpenSCAD to generate an STL file from the parameters.
3.  **CFD Simulation**: `foam_driver.py` prepares and runs an OpenFOAM simulation on the generated geometry. It calculates metrics like pressure drop and residuals.
4.  **Analysis & Suggestion**: `llm_agent.py` sends the simulation results to the Gemini LLM, which analyzes the data and proposes new parameters to test.
5.  **Iteration**: The process repeats for a specified number of iterations.

## Prerequisites

To run the optimization script, you need the following installed and configured:

*   **Python 3.x**: With the required packages installed (`pip install -r requirements.txt` if available, or install `google-generativeai`).
*   **OpenSCAD**: Available in your system PATH.
*   **OpenFOAM**: Installed and sourced (e.g., `simpleFoam`, `blockMesh`, `snappyHexMesh` should be executable).
*   **Google Gemini API Key**: An API key for Google's Generative AI. Set this as an environment variable: `export GEMINI_API_KEY="your_api_key"`.

## Usage

Run the main optimization script from the root of the repository or the `optimizer` directory (adjust paths accordingly):

```bash
python optimizer/main.py --iterations 5 --scad-file corkscrew.scad --case-dir corkscrewFilter
```

### Arguments

*   `--iterations`: Number of optimization cycles to run (default: 5).
*   `--scad-file`: Path to the OpenSCAD model file. **Note:** The script defaults to `corkscrew filter.scad`, but you should typically use `corkscrew.scad` (or your specific model file).
*   `--case-dir`: Path to the OpenFOAM case directory (default: `corkscrewFilter`).
*   `--output-stl`: Name of the generated STL file (default: `corkscrew_fluid.stl`).
*   `--dry-run`: Use this flag to simulate the process without running actual OpenSCAD or OpenFOAM commands (useful for testing the logic).

## File Descriptions

*   **`main.py`**: The central controller script that manages the optimization loop.
*   **`llm_agent.py`**: Interacts with the Google Gemini API to analyze simulation history and suggest new parameters.
*   **`foam_driver.py`**: Handles OpenFOAM case preparation, meshing, solving, and results extraction.
*   **`scad_driver.py`**: Wraps OpenSCAD command-line tools to generate STL files from parameter sets.
*   **`data_store.py`**: Manages the persistent storage of optimization results in `optimization_log.jsonl`.

## Data Storage

Results are stored in `optimization_log.jsonl`, a JSON Lines file where each line is a self-contained JSON object representing a single optimization run. This format allows for efficient append-only logging and easier merging of results from distributed runs.

Each entry contains:
*   `id`: Unique UUID for the run.
*   `timestamp`: UTC timestamp.
*   `status`: Status of the run (e.g., "completed").
*   `git_commit`: The git commit hash at the time of execution.
*   `parameters`: The input parameters used.
*   `metrics`: The output metrics from the simulation.
