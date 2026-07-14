import os
import json
import yaml
import pytest
from optimizer.generate_training_data import (
    load_yaml_config,
    load_optimization_logs,
    construct_system_prompt,
    construct_user_prompt,
    synthesize_cot_reasoning,
    build_transitions,
    filter_transitions,
    generate_dpo_pairs,
    export_data
)

@pytest.fixture
def sample_config_and_logs(tmp_path):
    # Create sample config
    config_dict = {
        "project_name": "Test_Project",
        "geometry": {
            "parameters": {
                "helix_path_radius_mm": {"type": "float", "min": 1.0, "max": 5.0, "default": 2.0},
                "helix_profile_radius_mm": {"type": "float", "min": 1.0, "max": 5.0, "default": 1.8},
                "constant_param": {"type": "float", "constant": True, "value": 32.0}
            }
        },
        "optimization": {
            "description": "Expert engineer test optimizer.",
            "target": "maximize",
            "objective_function": "efficiency",
            "constraints": "- Keep profile radius smaller than path radius."
        }
    }

    config_file = tmp_path / "test_config.yaml"
    with open(config_file, "w") as f:
        yaml.safe_dump(config_dict, f)

    # Create mock log files
    log_file = tmp_path / "test_logs.jsonl"
    runs = [
        {
            "id": "run-1",
            "iteration": 0,
            "timestamp": 100.0,
            "status": "completed",
            "parameters": {"helix_path_radius_mm": 2.0, "helix_profile_radius_mm": 1.8},
            "metrics": {"efficiency": 80.0, "delta_p": 1.2}
        },
        {
            "id": "run-2",
            "iteration": 1,
            "timestamp": 200.0,
            "status": "completed",
            "parameters": {"helix_path_radius_mm": 2.2, "helix_profile_radius_mm": 1.7},
            "metrics": {"efficiency": 85.0, "delta_p": 1.0}
        },
        {
            "id": "run-3",
            "iteration": 2,
            "timestamp": 300.0,
            "status": "completed",
            "parameters": {"helix_path_radius_mm": 2.1, "helix_profile_radius_mm": 2.1},
            "metrics": {"error": "meshing_failed", "details": "Negative volume cells detected."}
        },
        {
            "id": "run-4",
            "iteration": 3,
            "timestamp": 400.0,
            "status": "completed",
            "parameters": {"helix_path_radius_mm": 2.5, "helix_profile_radius_mm": 1.5},
            "metrics": {"efficiency": 92.0, "delta_p": 0.8}
        }
    ]

    with open(log_file, "w") as f:
        for run in runs:
            f.write(json.dumps(run) + "\n")

    return str(config_file), str(log_file), config_dict, runs

def test_load_yaml_config(sample_config_and_logs):
    config_file, _, expected_dict, _ = sample_config_and_logs
    config = load_yaml_config(config_file)
    assert config["project_name"] == "Test_Project"
    assert config["optimization"]["objective_function"] == "efficiency"

def test_load_optimization_logs(sample_config_and_logs):
    _, log_file, _, expected_runs = sample_config_and_logs
    logs = load_optimization_logs(log_file)
    assert len(logs) == 4
    assert logs[0]["id"] == "run-1"
    assert logs[3]["parameters"]["helix_path_radius_mm"] == 2.5

def test_construct_prompts(sample_config_and_logs):
    _, _, config_dict, expected_runs = sample_config_and_logs
    sys_prompt = construct_system_prompt(config_dict)
    assert "Expert engineer test optimizer." in sys_prompt
    assert "helix_path_radius_mm" in sys_prompt
    assert "constant_param" not in sys_prompt  # constant parameter should be excluded

    user_prompt = construct_user_prompt(expected_runs[:1], expected_runs[1])
    assert "HISTORY OF RUNS:" in user_prompt
    assert "helix_path_radius_mm" in user_prompt
    assert "80.0" in user_prompt  # Check that metrics of run-1 are in history

def test_synthesize_cot_reasoning(sample_config_and_logs):
    _, _, config_dict, expected_runs = sample_config_and_logs
    # Successful transition (run-1 -> run-2)
    cot = synthesize_cot_reasoning(expected_runs[0], expected_runs[1], config_dict, is_error_correction=False)
    assert "The previous run completed successfully" in cot
    assert "helix_path_radius_mm" in cot
    assert "helix_profile_radius_mm" in cot

    # Error correction transition (run-3 -> run-4)
    cot_err = synthesize_cot_reasoning(expected_runs[2], expected_runs[3], config_dict, is_error_correction=True)
    assert "meshing_failed" in cot_err
    assert "The meshing phase failed" in cot_err

def test_build_and_filter_transitions(sample_config_and_logs):
    _, _, config_dict, expected_runs = sample_config_and_logs
    transitions = build_transitions(expected_runs, config_dict)
    # 4 runs -> 3 transitions (run-1->run-2, run-2->run-3, run-3->run-4)
    assert len(transitions) == 3

    # Success filter
    # run-1 (score ~80) -> run-2 (score ~85) is success
    # run-2 -> run-3 is error
    # run-3 -> run-4 is error correction (run-3 has error, so calculate_score of run-3 is -1)
    success_trans = filter_transitions(transitions, "success", config_dict)
    assert len(success_trans) >= 1

    # Error-correction filter
    # run-3 (failed with meshing_failed) -> run-4 (success with 92 efficiency)
    err_trans = filter_transitions(transitions, "error-correction", config_dict)
    assert len(err_trans) == 1
    assert err_trans[0][1]["id"] == "run-3"
    assert err_trans[0][2]["id"] == "run-4"

def test_generate_dpo_pairs(sample_config_and_logs):
    _, _, config_dict, expected_runs = sample_config_and_logs
    transitions = build_transitions(expected_runs, config_dict)
    dpo_pairs = generate_dpo_pairs(transitions, config_dict)
    assert len(dpo_pairs) == 3
    for pair in dpo_pairs:
        assert "prompt" in pair
        assert "chosen" in pair
        assert "rejected" in pair
        chosen_data = json.loads(pair["chosen"])
        rejected_data = json.loads(pair["rejected"])
        assert "parameters" in chosen_data
        assert "parameters" in rejected_data

def test_export_data(sample_config_and_logs, tmp_path):
    _, _, config_dict, expected_runs = sample_config_and_logs
    transitions = build_transitions(expected_runs, config_dict)

    # Export OpenAI format
    openai_out = tmp_path / "openai.jsonl"
    export_data(transitions, "openai", config_dict, str(openai_out))
    assert os.path.exists(openai_out)
    with open(openai_out) as f:
        lines = f.readlines()
        assert len(lines) == 3
        first_sample = json.loads(lines[0])
        assert "messages" in first_sample
        assert len(first_sample["messages"]) == 3

    # Export Alpaca format
    alpaca_out = tmp_path / "alpaca.jsonl"
    export_data(transitions, "alpaca", config_dict, str(alpaca_out))
    assert os.path.exists(alpaca_out)
    with open(alpaca_out) as f:
        lines = f.readlines()
        assert len(lines) == 3
        first_sample = json.loads(lines[0])
        assert "instruction" in first_sample
        assert "input" in first_sample
        assert "output" in first_sample

    # Export DPO format
    dpo_out = tmp_path / "dpo.jsonl"
    export_data(transitions, "dpo", config_dict, str(dpo_out))
    assert os.path.exists(dpo_out)
    with open(dpo_out) as f:
        lines = f.readlines()
        assert len(lines) == 3
        first_sample = json.loads(lines[0])
        assert "prompt" in first_sample
        assert "chosen" in first_sample
        assert "rejected" in first_sample
