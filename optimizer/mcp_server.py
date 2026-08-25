"""
MCP (Model Context Protocol) Server for OpenAuto-CFD.

Exposes tools for LLMs to control, query, and drive the simulation harness,
run parameter evaluations, inspect optimization history, and execute Schema surrogate steps.
"""

import os
import sys
import json
import glob
import yaml
from typing import Dict, List, Any, Optional

# Ensure repository root is in python path
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

try:
    from mcp.server import MCPServer as FastMCP
except ImportError:
    from mcp.server.fastmcp import FastMCP

from optimizer.scad_driver import ScadDriver
from optimizer.physics_factory import PhysicsEngineFactory
from optimizer.simulation_runner import run_simulation
from optimizer.data_store import DataStore
from optimizer.llm_agent import LLMAgent

# Initialize FastMCP / MCPServer Instance
mcp = FastMCP(
    "OpenAuto-CFD",
    instructions="MCP Server providing tools for autonomous engineering, 3D parametric SCAD generation, CFD/EM simulation, and Schema surrogate optimization loops."
)


@mcp.tool()
def list_available_configs() -> List[Dict[str, Any]]:
    """
    List all available problem configuration YAML files in the codebase (e.g. configs/ directory and root).

    Returns:
        List[Dict[str, Any]]: List of configuration metadata including path, physics type, and title/description.
    """
    configs = []
    config_paths = glob.glob("configs/*.yaml") + glob.glob("configs/*.yml") + glob.glob("*.yaml")

    for path in sorted(set(config_paths)):
        try:
            with open(path, 'r') as f:
                data = yaml.safe_load(f)
            if isinstance(data, dict):
                configs.append({
                    "path": path,
                    "physics_type": data.get("physics", {}).get("type", "cfd"),
                    "scad_file": data.get("geometry", {}).get("scad_file", ""),
                    "description": data.get("optimization", {}).get("description", "")
                })
        except Exception as e:
            configs.append({"path": path, "error": str(e)})

    return configs


@mcp.tool()
def run_simulation_tool(
    config_file: str = "configs/corkscrew_config.yaml",
    params: Optional[Dict[str, Any]] = None,
    dry_run: bool = True,
    case_dir: str = "corkscrewFilter",
    output_stl: str = "corkscrew_fluid.stl",
    cpus: int = 1,
    turbulence: str = "laminar"
) -> Dict[str, Any]:
    """
    Execute a single CAD generation and physics simulation evaluation (CFD/EM/FEA) for a given set of parameters.

    Args:
        config_file (str): Path to problem configuration YAML file (default: "configs/corkscrew_config.yaml").
        params (Optional[Dict[str, Any]]): Dictionary of CAD parameters. If None, default config parameters are used.
        dry_run (bool): If True, skip actual solver execution and return mock/cached results (default: True).
        case_dir (str): OpenFOAM case directory or solver workspace (default: "corkscrewFilter").
        output_stl (str): Output STL filename for fluid domain (default: "corkscrew_fluid.stl").
        cpus (int): Number of CPU cores for parallel meshing/solving (default: 1).
        turbulence (str): Turbulence model to use (e.g. "laminar", "kOmegaSST") (default: "laminar").

    Returns:
        Dict[str, Any]: Combined results including performance metrics, visual render paths, and artifact file paths.
    """
    try:
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)
    except Exception as e:
        return {"status": "error", "message": f"Failed to load config_file '{config_file}': {str(e)}"}

    scad_file = config.get('geometry', {}).get('scad_file', 'corkscrew.scad')
    fluid_volume_module = config.get('geometry', {}).get('fluid_volume_module', 'modular_filter_assembly')

    if params is None:
        params = {}
        for param_name, param_def in config.get('geometry', {}).get('parameters', {}).items():
            if 'default' in param_def:
                params[param_name] = param_def['default']
            elif param_def.get('constant', False) and 'value' in param_def:
                params[param_name] = param_def['value']

    scad = ScadDriver(scad_file, fluid_volume_module=fluid_volume_module)
    physics_driver = PhysicsEngineFactory.get_driver(
        case_dir,
        config=config,
        num_processors=cpus
    )

    metrics, png_paths, solid_stl, fluid_stl, vtk_zip = run_simulation(
        scad=scad,
        physics_driver=physics_driver,
        params=params,
        output_stl_name=output_stl,
        dry_run=dry_run,
        params_file=None,
        turbulence=turbulence
    )

    return {
        "status": "success",
        "parameters": params,
        "metrics": metrics,
        "images": png_paths,
        "solid_stl_path": solid_stl,
        "fluid_stl_path": fluid_stl,
        "artifact_vtk_path": vtk_zip
    }


@mcp.tool()
def get_harness_status(db_path: str = "optimization_log.jsonl", top_k: int = 5) -> Dict[str, Any]:
    """
    Query the overall optimization harness history and top performing runs.

    Args:
        db_path (str): Path to JSONL data store log file (default: "optimization_log.jsonl").
        top_k (int): Number of top runs to retrieve (default: 5).

    Returns:
        Dict[str, Any]: History summary including total run count, top runs, and recent iterations.
    """
    store = DataStore(log_file=db_path)
    history = store.load_history()

    if not history:
        return {
            "total_runs": 0,
            "top_runs": [],
            "latest_run": None
        }

    top_runs = store.get_top_runs(top_k)
    latest_run = history[-1]

    return {
        "total_runs": len(history),
        "top_runs": top_runs,
        "latest_run": {
            "id": latest_run.get("id"),
            "iteration": latest_run.get("iteration"),
            "parameters": latest_run.get("parameters"),
            "metrics": latest_run.get("metrics"),
            "timestamp": latest_run.get("timestamp")
        }
    }


@mcp.tool()
def get_run_details(run_id: str, db_path: str = "optimization_log.jsonl") -> Dict[str, Any]:
    """
    Fetch comprehensive details for a specific run by ID.

    Args:
        run_id (str): Unique run ID or hash prefix.
        db_path (str): Path to JSONL data store log file.

    Returns:
        Dict[str, Any]: Full details of the specified run.
    """
    store = DataStore(log_file=db_path)
    history = store.load_history()

    for run in history:
        if run.get("id") == run_id or str(run.get("id", "")).startswith(run_id):
            return {"status": "success", "run": run}

    return {"status": "error", "message": f"Run ID '{run_id}' not found."}


@mcp.tool()
def get_schema_state(workspace_dir: str = "exports") -> Dict[str, Any]:
    """
    Retrieve the current physicist-style Schema surrogate state and backtest timeline log.

    Args:
        workspace_dir (str): Workspace directory containing Schema state files (default: "exports").

    Returns:
        Dict[str, Any]: Current Schema surrogate state, backtest timeline history, and notes.
    """
    from optimizer.harness.timeline import Timeline
    from optimizer.harness.notes import NotesManager
    from optimizer.harness.state import State

    timeline_path = os.path.join(workspace_dir, "timeline.jsonl")
    notes_path = os.path.join(workspace_dir, "notes.md")

    tl = Timeline(timeline_path)
    nm = NotesManager(notes_path)

    transitions = tl.load_transitions()
    notes = nm.read_notes()

    latest_state = State().to_dict()
    latest_discrepancy = None

    if transitions:
        latest_trans = transitions[-1]
        latest_state = latest_trans.get("actual_state", latest_state)

    return {
        "status": "success",
        "state": latest_state,
        "timeline_events_count": len(transitions),
        "latest_discrepancy": latest_discrepancy,
        "notes": notes
    }


@mcp.tool()
def run_schema_step(
    config_file: str = "configs/corkscrew_config.yaml",
    workspace_dir: str = "exports",
    epsilon: float = 5.0,
    dry_run: bool = True
) -> Dict[str, Any]:
    """
    Execute a single iteration of the Schema surrogate-planning harness loop.

    Synthesizes physics surrogate predictions, executes real solver validation,
    backtests discrepancy against epsilon, and updates Schema state.

    Args:
        config_file (str): Problem configuration YAML file (default: "configs/corkscrew_config.yaml").
        workspace_dir (str): Workspace directory for Schema artifacts (default: "exports").
        epsilon (float): Mismatch threshold for surrogate updates (default: 5.0).
        dry_run (bool): If True, skip actual solver execution during backtest (default: True).

    Returns:
        Dict[str, Any]: Result of the Schema step including predicted state, selected action, updated state, and discrepancy.
    """
    from optimizer.harness.engine import SchemaEngine
    from optimizer.harness.state import State, parse_solver_outputs_to_state

    try:
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)
    except Exception as e:
        return {"status": "error", "message": f"Failed to load config_file '{config_file}': {str(e)}"}

    parameter_defs = config.get('geometry', {}).get('parameters', {})
    agent = LLMAgent()

    engine = SchemaEngine(
        workspace_dir=workspace_dir,
        parameter_defs=parameter_defs,
        llm_agent=agent,
        epsilon=epsilon
    )

    # Establish initial state from parameter defaults
    initial_params = {}
    for param_name, param_def in parameter_defs.items():
        if 'default' in param_def:
            initial_params[param_name] = param_def['default']
        elif param_def.get('constant', False) and 'value' in param_def:
            initial_params[param_name] = param_def['value']

    def real_solver_func(params_to_run):
        scad_file = config.get('geometry', {}).get('scad_file', 'corkscrew.scad')
        fluid_volume_module = config.get('geometry', {}).get('fluid_volume_module', 'modular_filter_assembly')
        scad = ScadDriver(scad_file, fluid_volume_module=fluid_volume_module)
        physics_driver = PhysicsEngineFactory.get_driver("corkscrewFilter", config=config)

        metrics, _, _, _, _ = run_simulation(
            scad=scad,
            physics_driver=physics_driver,
            params=params_to_run,
            dry_run=dry_run
        )
        return metrics

    initial_metrics = real_solver_func(initial_params)
    current_state = parse_solver_outputs_to_state(initial_params, initial_metrics)

    def state_score_func(s: State) -> float:
        eff = s.fluid.get("separation_efficiency", 0.0)
        p_drop = s.fluid.get("pressure_drop", 0.0)
        return eff - (p_drop * 0.1)

    predicted_state, action, updated_state, discrepancy = engine.run_one_iteration(
        current_state=current_state,
        score_func=state_score_func,
        real_solver_func=real_solver_func
    )

    return {
        "status": "success",
        "action": action.to_dict() if hasattr(action, 'to_dict') else action,
        "discrepancy": discrepancy,
        "surrogate_updated": discrepancy > epsilon,
        "updated_state": updated_state.to_dict() if hasattr(updated_state, 'to_dict') else updated_state
    }


def main():
    """Run MCP server over stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
