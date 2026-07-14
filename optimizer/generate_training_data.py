#!/usr/bin/env python3
"""
generate_training_data.py

A solver-agnostic training harness utility to convert multi-physics simulation logs (.jsonl)
and YAML configuration files into high-quality instruction sets for LLM fine-tuning.
Supports OpenAI Chat format, Alpaca format, and Direct Preference Optimization (DPO) format,
with programmatically synthesized engineering and physics Chain-of-Thought (CoT).
"""

import os
import sys
import json
import argparse
import yaml
from typing import Dict, List, Any, Tuple

# Ensure we can import from optimizer
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from scoring import calculate_score

def load_yaml_config(filepath: str) -> Dict[str, Any]:
    """Loads and returns the YAML project configuration."""
    with open(filepath, 'r') as f:
        return yaml.safe_load(f)

def load_optimization_logs(filepath: str) -> List[Dict[str, Any]]:
    """Loads and returns all runs from the optimization log file."""
    history = []
    if not os.path.exists(filepath):
        print(f"Warning: Log file {filepath} not found.")
        return history

    with open(filepath, "r") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    history.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return history

def construct_system_prompt(config: Dict[str, Any]) -> str:
    """Constructs a solver-agnostic system prompt based on the YAML configuration."""
    opt_cfg = config.get('optimization', {})
    geom_cfg = config.get('geometry', {})

    desc = opt_cfg.get('description', 'You are an expert engineer optimizing a parametric design.')
    target = opt_cfg.get('target', 'maximize')
    objective = opt_cfg.get('objective_function', 'efficiency')
    constraints = opt_cfg.get('constraints', '')

    # Build Parameter Definition String
    param_def_str = "PARAMETERS (Your search space):\n"
    for name, info in geom_cfg.get('parameters', {}).items():
        if info.get('constant', False):
            continue
        param_def_str += f"- {name}: type {info.get('type', 'float')}"
        if 'min' in info:
            param_def_str += f", min {info['min']}"
        if 'max' in info:
            param_def_str += f", max {info['max']}"
        if 'default' in info:
            param_def_str += f", default {info['default']}"
        param_def_str += "\n"

    prompt = f"""{desc.strip()}

GOAL: {target.upper()} the objective function: {objective}

{param_def_str}
CONSTRAINTS:
{constraints.strip()}

RESPONSE FORMAT:
You must respond with valid JSON only. DO NOT include any conversational text, markdown blocks, preamble, or explanations outside the JSON object.
{{
    "reasoning": "Explain why you chose these parameters...",
    "stop_optimization": false,
    "parameters": {{
        "param_name": value,
        ...
    }}
}}"""
    return prompt.strip()

def construct_user_prompt(history: List[Dict[str, Any]], current_run: Dict[str, Any]) -> str:
    """Constructs the user prompt showing previous run history and the immediate run feedback."""
    # We serialize the history up to current_run
    history_data = []
    for run in history:
        history_data.append({
            "parameters": run.get("parameters", {}),
            "metrics": run.get("metrics", {})
        })

    history_str = json.dumps(history_data, indent=2)

    error_instruction = ""
    metrics = current_run.get("metrics", {})
    if "error" in metrics:
        last_error = metrics["error"]
        details = metrics.get("details", "No details available")
        error_instruction = f"""
CRITICAL WARNING:
The previous run FAILED with error: "{last_error}".
Details: {details}

You must adjust parameters to address and resolve this specific failure in the next iteration.
"""

    prompt = f"""HISTORY OF RUNS:
{history_str}

LATEST RUN RESULT:
Parameters: {json.dumps(current_run.get("parameters", {}), indent=2)}
Metrics: {json.dumps(metrics, indent=2)}
{error_instruction}
TASK:
Analyze the history of runs. Identify physical and geometrical trends. Propose the NEXT set of parameters to test."""
    return prompt.strip()

def synthesize_cot_reasoning(run_n: Dict[str, Any], run_nplus1: Dict[str, Any], config: Dict[str, Any], is_error_correction: bool) -> str:
    """Programmatically synthesizes a highly professional, physics-informed engineering Chain-of-Thought."""
    opt_cfg = config.get('optimization', {})
    objective = opt_cfg.get('objective_function', 'efficiency')
    target = opt_cfg.get('target', 'maximize')

    params_n = run_n.get("parameters", {})
    params_nplus1 = run_nplus1.get("parameters", {})
    metrics_n = run_n.get("metrics", {})
    metrics_nplus1 = run_nplus1.get("metrics", {})

    reasoning_parts = []

    # 1. Analyze previous state
    if "error" in metrics_n:
        err = metrics_n["error"]
        details = metrics_n.get("details", "")
        reasoning_parts.append(f"In the previous run, we encountered a critical error: '{err}' (details: {details}).")

        # Add solver-specific or geometry troubleshooting reasoning
        if err == "geometry_generation_failed":
            reasoning_parts.append("This indicates that the proposed parameters violated basic geometric or non-manifold boundaries, preventing OpenSCAD from rendering the STL properly.")
        elif err == "geometry_invalid_volume":
            reasoning_parts.append("The geometry generated a non-manifold shape with zero or negative volume, which prevents finding an internal point for the mesh generator (snappyHexMesh) and would cause a fatal segfault.")
        elif err == "meshing_failed":
            reasoning_parts.append("The meshing phase failed. This is typically due to extreme skewness, high non-orthogonality, or negative volume cells in highly cramped channels.")
        elif err == "solver_failed":
            reasoning_parts.append("The simulation solver failed to converge, suggesting physical instability or diverging residuals due to extreme flow velocities or geometry singularities.")
        else:
            reasoning_parts.append("This simulation error must be bypassed by carefully moving parameters back into stable physical envelopes.")
    else:
        score_n = calculate_score(metrics_n, config)[1] if "error" not in metrics_n else -1.0
        reasoning_parts.append(f"The previous run completed successfully. Let's inspect the target objective '{objective}'.")
        if objective in metrics_n:
            reasoning_parts.append(f"We achieved a value of {metrics_n[objective]} for '{objective}'.")

    # 2. Analyze parameter transitions and physics decisions
    deltas = []
    for param_name in params_nplus1:
        if param_name in params_n and params_n[param_name] != params_nplus1[param_name]:
            val_n = params_n[param_name]
            val_np1 = params_nplus1[param_name]
            deltas.append((param_name, val_n, val_np1))

    if deltas:
        reasoning_parts.append("To optimize the performance and ensure numerical stability, we adjust the following design parameters:")
        for name, v_old, v_new in deltas:
            reasoning_parts.append(f"- Modify '{name}' from {v_old} to {v_new}.")

            # Add dynamic, physically meaningful rationale based on typical parameter names
            if "radius" in name or "diameter" in name:
                if v_new > v_old:
                    reasoning_parts.append(f"  Increasing the radius/diameter widens the flow channel, reducing flow resistance (pressure drop) and resolving boundary non-orthogonality/cramping.")
                else:
                    reasoning_parts.append(f"  Decreasing the radius/diameter narrows the flow channel, which increases local velocity and centrifugal separation forces for higher efficiency.")
            elif "revolution" in name or "pitch" in name:
                if v_new > v_old:
                    reasoning_parts.append(f"  Increasing the revolutions/pitch lengthens the particle residence time, allowing more centrifugal separation cycles to capture finer particles.")
                else:
                    reasoning_parts.append(f"  Decreasing the revolutions/pitch shortens the flow path, directly reducing pressure drop and lowering boundary layer friction losses.")
            elif "slit" in name:
                reasoning_parts.append(f"  Adjusting slit dimensions helps optimize the separation threshold, balancing particle rejection and minimizing pressure drops.")
            elif "thickness" in name or "wall" in name:
                reasoning_parts.append(f"  Tuning structural walls to maintain a robust manifold shape and avoid self-intersection.")
    else:
        reasoning_parts.append("We retain the existing parameter configurations but refine local tolerances to explore the immediate neighborhood of this design space.")

    # 3. Formulate concluding engineering intent
    reasoning_parts.append("These parameter changes represent a calculated trade-off between fluid velocity, shear stress, and geometric constraints to drive the optimization closer to our design goals.")

    return " ".join(reasoning_parts)

def build_transitions(logs: List[Dict[str, Any]], config: Dict[str, Any]) -> List[Tuple[List[Dict[str, Any]], Dict[str, Any], Dict[str, Any]]]:
    """
    Constructs transitions of (History, Run_N, Run_N+1).
    Ensures state sequence is strictly linear and matches physical iterations.
    """
    # Sort runs chronologically by timestamp or iteration
    sorted_runs = sorted(logs, key=lambda r: (r.get("iteration", 0), r.get("timestamp", 0.0)))

    transitions = []
    for idx in range(len(sorted_runs) - 1):
        history = sorted_runs[:idx]
        run_n = sorted_runs[idx]
        run_nplus1 = sorted_runs[idx + 1]

        # Verify both have parameters to be a valid transition
        if "parameters" in run_n and "parameters" in run_nplus1:
            transitions.append((history, run_n, run_nplus1))

    return transitions

def filter_transitions(transitions: List[Tuple[List[Dict[str, Any]], Dict[str, Any], Dict[str, Any]]],
                       filter_mode: str, config: Dict[str, Any]) -> List[Tuple[List[Dict[str, Any]], Dict[str, Any], Dict[str, Any]]]:
    """Filters transitions based on success or error-correction criteria."""
    filtered = []

    for history, run_n, run_nplus1 in transitions:
        metrics_n = run_n.get("metrics", {})
        metrics_nplus1 = run_nplus1.get("metrics", {})

        if filter_mode == "all":
            filtered.append((history, run_n, run_nplus1))

        elif filter_mode == "success":
            # Success means we successfully got metrics and improved the score
            if "error" not in metrics_n and "error" not in metrics_nplus1:
                score_n = calculate_score(metrics_n, config)[1]
                score_nplus1 = calculate_score(metrics_nplus1, config)[1]
                if score_nplus1 > score_n:
                    filtered.append((history, run_n, run_nplus1))

        elif filter_mode == "error-correction":
            # Error correction means Run N failed, and Run N+1 completed successfully (no error)
            if "error" in metrics_n and "error" not in metrics_nplus1:
                filtered.append((history, run_n, run_nplus1))

    return filtered

def generate_dpo_pairs(transitions: List[Tuple[List[Dict[str, Any]], Dict[str, Any], Dict[str, Any]]],
                       config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Generates DPO (Direct Preference Optimization) chosen/rejected response pairs for State N.
    Uses actual forward trajectories to find better and worse outcomes from the same state.
    """
    dpo_samples = []

    # We iterate through each simulation state N (represented by history 0...N and result of Run N)
    for idx, (history, run_n, run_nplus1) in enumerate(transitions):
        # We need a preferred next step (chosen) and a suboptimal next step (rejected)
        # Case 1: If run_nplus1 was successful (improved or fixed error), we use it as Chosen.
        # We find a Rejected candidate by searching other next runs, or programmatically synthesizing a rejected parameter set.
        metrics_nplus1 = run_nplus1.get("metrics", {})
        score_nplus1 = calculate_score(metrics_nplus1, config)[1] if "error" not in metrics_nplus1 else -1e9

        chosen_params = run_nplus1.get("parameters", {})
        chosen_reasoning = synthesize_cot_reasoning(run_n, run_nplus1, config, is_error_correction=("error" in run_n.get("metrics", {})))

        # Look for a suboptimal run at the same or similar stage, or synthesize a rejected run
        rejected_params = None
        rejected_reasoning = ""

        # Look ahead in the remaining transitions to see if there is any run that performed worse or failed
        for _, _, future_run in transitions[idx+1:]:
            future_metrics = future_run.get("metrics", {})
            if "error" in future_metrics:
                rejected_params = future_run.get("parameters", {})
                rejected_reasoning = f"We will adjust parameters to explore the space, even if we risk mesh failures or non-manifold shapes."
                break
            else:
                future_score = calculate_score(future_metrics, config)[1]
                if future_score < score_nplus1:
                    rejected_params = future_run.get("parameters", {})
                    rejected_reasoning = f"Let's try adjusting the parameters in a way that may increase pressure drop or reduce centrifugal separation efficiency."
                    break

        # Fallback: if no worse run was found, synthesize one by perturbing parameters to violate a constraint
        if not rejected_params:
            rejected_params = chosen_params.copy()
            # Perturb to make it bad (e.g., set radii equal to violate constraints)
            if "helix_profile_radius_mm" in rejected_params and "helix_path_radius_mm" in rejected_params:
                rejected_params["helix_profile_radius_mm"] = rejected_params["helix_path_radius_mm"]
            elif "vortex_finder_diameter" in rejected_params:
                rejected_params["vortex_finder_diameter"] = rejected_params.get("cyclone_diameter", 30) + 10

            rejected_reasoning = "We will set the parameters without considering geometric constraints, which may cause self-intersection or mesh failure."

        system_prompt = construct_system_prompt(config)
        user_prompt = construct_user_prompt(history, run_n)

        chosen_response = {
            "reasoning": chosen_reasoning,
            "stop_optimization": False,
            "parameters": chosen_params
        }

        rejected_response = {
            "reasoning": rejected_reasoning,
            "stop_optimization": False,
            "parameters": rejected_params
        }

        dpo_samples.append({
            "prompt": f"<|system|>\n{system_prompt}\n<|user|>\n{user_prompt}",
            "chosen": json.dumps(chosen_response, indent=2),
            "rejected": json.dumps(rejected_response, indent=2)
        })

    return dpo_samples

def export_data(transitions: List[Tuple[List[Dict[str, Any]], Dict[str, Any], Dict[str, Any]]],
                format_type: str, config: Dict[str, Any], output_path: str):
    """Exports the transitions to the requested dataset format."""
    system_prompt = construct_system_prompt(config)

    exported_count = 0
    with open(output_path, 'w') as f:
        if format_type == "dpo":
            dpo_pairs = generate_dpo_pairs(transitions, config)
            for pair in dpo_pairs:
                f.write(json.dumps(pair) + "\n")
                exported_count += 1
        else:
            for history, run_n, run_nplus1 in transitions:
                user_prompt = construct_user_prompt(history, run_n)

                # Synthesize Chain-of-Thought for the target assistant output
                is_err_corr = "error" in run_n.get("metrics", {})
                cot = synthesize_cot_reasoning(run_n, run_nplus1, config, is_error_correction=is_err_corr)

                assistant_response = {
                    "reasoning": cot,
                    "stop_optimization": False,
                    "parameters": run_nplus1.get("parameters", {})
                }
                assistant_str = json.dumps(assistant_response, indent=2)

                if format_type == "openai":
                    sample = {
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                            {"role": "assistant", "content": assistant_str}
                        ]
                    }
                elif format_type == "alpaca":
                    sample = {
                        "instruction": system_prompt,
                        "input": user_prompt,
                        "output": assistant_str
                    }
                else:
                    raise ValueError(f"Unknown export format: {format_type}")

                f.write(json.dumps(sample) + "\n")
                exported_count += 1

    print(f"Successfully exported {exported_count} training examples to {output_path} in {format_type.upper()} format.")

def main():
    parser = argparse.ArgumentParser(description="Solver-Agnostic Training Harness for LLM Fine-Tuning")
    parser.add_argument("config_file", type=str, help="Path to the problem definition YAML file")
    parser.add_argument("--log-file", type=str, default="optimization_log.jsonl", help="Path to the optimization log file")
    parser.add_argument("--output-file", type=str, default="training_data.jsonl", help="Path to write the exported training data")
    parser.add_argument("--format", type=str, default="openai", choices=["openai", "alpaca", "dpo"], help="Target dataset format")
    parser.add_argument("--filter", type=str, default="all", choices=["all", "success", "error-correction"], help="Transition filtering mode")

    args = parser.parse_args()

    # 1. Load config and log files
    try:
        config = load_yaml_config(args.config_file)
        print(f"Loaded configuration from {args.config_file}")
    except Exception as e:
        print(f"Error loading configuration: {e}")
        sys.exit(1)

    logs = load_optimization_logs(args.log_file)
    print(f"Loaded {len(logs)} simulation logs from {args.log_file}")

    if len(logs) < 2:
        print("Error: At least 2 simulation logs are required to construct transition steps.")
        sys.exit(1)

    # 2. Build and filter transitions
    transitions = build_transitions(logs, config)
    print(f"Constructed {len(transitions)} transition steps.")

    filtered = filter_transitions(transitions, args.filter, config)
    print(f"Filtered to {len(filtered)} transitions using mode '{args.filter}'.")

    if not filtered:
        print("Warning: No transitions matched the specified filter criteria. Export aborted.")
        sys.exit(1)

    # 3. Export to target format
    try:
        export_data(filtered, args.format, config, args.output_file)
    except Exception as e:
        print(f"Error during dataset export: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
