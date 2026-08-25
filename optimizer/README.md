# AI-Driven Design Optimization

This directory contains a suite of tools to automate the design optimization of the Corkscrew Filter filter using Generative AI. The system iterates through design parameters, generates 3D geometry, runs CFD simulations to evaluate performance, and uses a Large Language Model (LLM) to suggest improvements.

## Overview

The optimization loop consists of the following steps:
1.  **Parameter Selection**: The system starts with an initial set of parameters or takes suggestions from the LLM.
2.  **Geometry Generation**: `scad_driver.py` uses OpenSCAD to generate an STL file from the parameters.
3.  **CFD Simulation**: `foam_driver.py` prepares and runs an OpenFOAM simulation on the generated geometry. It calculates metrics like pressure drop and residuals.
4.  **Analysis & Suggestion**: `llm_agent.py` sends the simulation results to the Gemini LLM, which analyzes the data and proposes new parameters to test.
5.  **Iteration**: The process repeats for a specified number of iterations.

## How the AI Agent Works

The `LLMAgent` (using Google Gemini) is designed to function as an autonomous engineer. Instead of treating the optimization as a black-box numerical search (like Genetic Algorithms), it reasons through the problem using physics and engineering constraints.

### Inputs
The Agent receives a rich context for every iteration:
*   **Design History**: A JSON log of all previous runs, including parameters used and the resulting metrics.
*   **Simulation Metrics**: Key performance indicators from OpenFOAM, such as **Pressure Drop** (energy cost) and **Particle Residuals** (simulation convergence).
*   **Visual Feedback**: 3D renderings (screenshots) of the generated STL. This allows the model to "see" geometrical errors (e.g., walls that are too thin, disconnected helices) that purely numerical data would miss.
*   **Physics Constraints**: A system prompt that explicitly defines the governing equations (e.g., Centrifugal Force $$F = mv^2/r$$) and design goals.

### Chain-of-Thought Reasoning
The agent is instructed to output its response in a structured JSON format that includes a `reasoning` field. It must:
1.  **Analyze Trends**: Look at the history (e.g., "Increasing pitch last time reduced pressure drop but hurt efficiency").
2.  **Apply Physics**: Relate the trends to theory (e.g., "To recover efficiency without increasing pressure, we should increase the helix radius to boost centrifugal force while keeping the pitch constant").
3.  **Propose Parameters**: Only after this reasoning step does it generate the numerical parameters for the next run.

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
*   `--cpus`: Set the number of CPUs (cores) to use for parallel meshing and solving in OpenFOAM (default: 1). Use this flag to speed up OpenFOAM processing significantly on multi-core machines.

## File Descriptions

*   **`main.py`**: The central controller script that manages the optimization loop.
*   **`llm_agent.py`**: Interacts with the Google Gemini API to analyze simulation history and suggest new parameters.
*   **`foam_driver.py`**: Handles OpenFOAM case preparation, meshing, solving, and results extraction.
*   **`scad_driver.py`**: Wraps OpenSCAD command-line tools to generate STL files from parameter sets.
*   **`data_store.py`**: Manages the persistent storage of optimization results in `optimization_log.jsonl`.
*   **`constraints.py`**: Central definitions for optimization goals and parameter constraints.
*   **`mcp_server.py`**: Model Context Protocol (MCP) server providing standard stdio tool execution for external LLMs.

## Model Context Protocol (MCP) Server

The MCP server (`optimizer/mcp_server.py`) exposes high-level tools for external LLM agents to direct the harness:

### Exposed MCP Capabilities

#### Tools (`@mcp.tool`)
1. `list_available_configs`: Discovers all YAML problem definition files in the codebase.
2. `run_simulation_tool`: Triggers OpenSCAD geometry generation and CFD/EM/FEA simulations with specific parameters.
3. `get_harness_status`: Queries optimization history, total runs, and top-performing parameter sets.
4. `get_run_details`: Fetches full details, metrics, and artifact paths for a specific run ID.
5. `get_schema_state`: Retrieves the current Schema surrogate state, timeline discrepancy log, and notes.
6. `run_schema_step`: Executes an iteration of the physicist-style Schema surrogate planning loop.
7. `validate_parameters_tool`: Performs pre-flight constraint validation on proposed CAD parameter sets.
8. `suggest_parameters_tool`: Invokes the internal AI agent / Optuna optimizer to propose candidate parameters.
9. `generate_training_dataset_tool`: Formats historical simulation logs into OpenAI, Alpaca, or DPO fine-tuning datasets with synthesized CoT reasoning.

#### Resources (`@mcp.resource`)
* `config://corkscrew_config.yaml`: Read standard Corkscrew Filter CFD configuration YAML.
* `log://latest`: Read the latest simulation run record from the optimization log.
* `schema://notes`: Read physicist notes (`notes.md`) recorded during Schema surrogate iterations.

#### Prompts (`@mcp.prompt`)
* `analyze_simulation_results`: Generates structured prompt guiding an LLM on analyzing simulation metrics and recommending parameter mutations.
* `schema_surrogate_reasoning`: Generates prompt template for mechanism discovery and surrogate updates when state discrepancy occurs.

### Launching the MCP Server
```bash
PYTHONPATH=optimizer python3 -m optimizer.mcp_server
```

## Data Storage

Results are stored in `optimization_log.jsonl`, a JSON Lines file where each line is a self-contained JSON object representing a single optimization run. This format allows for efficient append-only logging and easier merging of results from distributed runs.

Each entry contains:
*   `id`: Unique UUID for the run.
*   `timestamp`: UTC timestamp.
*   `status`: Status of the run (e.g., "completed").
*   `git_commit`: The git commit hash at the time of execution.
*   `parameters`: The input parameters used.
*   `metrics`: The output metrics from the simulation.
