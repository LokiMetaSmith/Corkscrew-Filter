# LLM Fine-Tuning Training Harness Guide

To bridge the gap between foundational physics knowledge and specific, continuous-simulation design loops (such as OpenFOAM CFD, openEMS, or FEA), this project includes a robust, solver-agnostic **LLM Training Harness**.

The training harness allows you to extract past trajectories of optimization parameters and programmatically compile them into rich instruction-tuning datasets. These datasets include synthesized, physics-informed **Chain-of-Thought (CoT)** reasoning blocks that instill Specialized Parameter-Selection Intuition into any open-source or commercial model.

---

## Architecture Overview

Rather than training the model on static, isolated configurations, the harness models the optimization loop as a sequence of **State Transitions** ($Run_N \to Run_{N+1}$):

```
       [State N Prompt]
  +------------------------+
  | - History of Runs      |
  | - Last Run Parameters  |       [Fine-Tuned LLM]
  | - Last Run Metrics/Err | ------------+
  +------------------------+             |
              |                          v
              v                [Next Design Decision]
    [Synthesized Physics CoT] +-----------------------+
   "Since the previous run    | - Next Parameters     |
    failed with meshing_failed| - Stop Signal (bool)  |
    due to cramped channels,  +-----------------------+
    we widen path_radius..."
```

---

## 1. Quick Start

The training harness lives at `optimizer/generate_training_data.py`.

### Generate OpenAI Chat Format (SFT)
Export consecutive steps of successful runs or troubleshooting runs in the standard OpenAI Messages JSONL format:
```bash
python optimizer/generate_training_data.py configs/corkscrew_config.yaml \
    --log-file optimization_log.jsonl \
    --output-file sft_chat_data.jsonl \
    --format openai \
    --filter all
```

### Generate Direct Preference Optimization (DPO) Pairs
Export preferred vs. non-preferred (failed or worse performing) parameter transitions from the exact same simulation state:
```bash
python optimizer/generate_training_data.py configs/corkscrew_config.yaml \
    --log-file optimization_log.jsonl \
    --output-file dpo_data.jsonl \
    --format dpo
```

---

## 2. CLI Options Reference

| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `config_file` | `str` | *Required* | Path to the problem definition YAML file (e.g., `configs/corkscrew_config.yaml`). Specifies search parameters, bounds, optimization goals, and constraints. |
| `--log-file` | `str` | `optimization_log.jsonl` | Path to the optimization history log file. |
| `--output-file`| `str` | `training_data.jsonl` | Target output path for the exported training data. |
| `--format` | `choice`| `openai` | Target dataset format. Options: `openai` (chat messages), `alpaca` (instruction-input-output), `dpo` (chosen/rejected pairs). |
| `--filter` | `choice`| `all` | Sourcing/filtering strategy. Options:<br>• `all`: Keep all continuous steps.<br>• `success`: Keep transitions where the score improved.<br>• `error-correction`: Keep steps where $Run_N$ failed and $Run_{N+1}$ recovered/fixed it. |

---

## 3. Training Formats & Datasets

### A. OpenAI Chat Format (`--format openai`)
Ideal for supervised fine-tuning (SFT) of modern chat models (e.g., LLaMA, Qwen, Mistral) using popular libraries like Axolotl, Unsloth, or Hugging Face SFTTrainer.
```json
{
  "messages": [
    { "role": "system", "content": "...[YAML Goals & Constraints]..." },
    { "role": "user", "content": "HISTORY OF RUNS:\n... [Previous Parameters & Metrics] ...\nLATEST RUN:\n... [Preceding Step Details] ..." },
    { "role": "assistant", "content": "{\n  \"reasoning\": \"The previous run completed successfully. Let's inspect the target objective 'separation_efficiency'. Modify 'helix_path_radius_mm' from 1.8 to 2.2...\",\n  \"stop_optimization\": false,\n  \"parameters\": { \"helix_path_radius_mm\": 2.2, \"helix_profile_radius_mm\": 1.7 }\n}" }
  ]
}
```

### B. Alpaca Format (`--format alpaca`)
Widely used for instruct-tuning foundational models.
```json
{
  "instruction": "... [System Prompt / YAML Guidelines] ...",
  "input": "... [History & Preceding Run Metrics] ...",
  "output": "{\n  \"reasoning\": \"... [Physics Chain-of-Thought] ...\",\n  \"parameters\": { ... }\n}"
}
```

### C. Direct Preference Optimization (`--format dpo`)
An extremely powerful format to teach models to **avoid unstable physics and prioritize manifold geometries** by showing a preferred versus a rejected action from the same state.
```json
{
  "prompt": "<|system|>\n... [Constraints] ...\n<|user|>\n... [History & Last Run Result] ...",
  "chosen": "{\n  \"reasoning\": \"... [Physics reasoning to resolve the error] ...\",\n  \"parameters\": { \"helix_path_radius_mm\": 2.5, \"helix_profile_radius_mm\": 1.5 }\n}",
  "rejected": "{\n  \"reasoning\": \"We will set parameters without considering geometric constraints...\",\n  \"parameters\": { \"helix_profile_radius_mm\": 2.5, \"helix_path_radius_mm\": 2.5 }\n}"
}
```

---

## 4. How the Physics Reasoning Engine Works

To keep the model from overfitting to raw numbers, the harness programmatically synthesizes a **physics-informed engineering Chain-of-Thought (CoT)**:

1. **State Diagnostics**: If the previous run crashed (e.g., `geometry_invalid_volume` or `meshing_failed`), it automatically synthesizes reasoning targeting that specific error:
   - *Example*: `"The geometry generated a non-manifold shape with zero or negative volume... to resolve boundary non-orthogonality/cramping, we will increase helix_path_radius_mm..."*
2. **Delta Analysis**: It identifies which parameters changed between step $N$ and step $N+1$ and explains the fluid dynamics / EM trade-offs associated with those changes:
   - *Radius decrease*: Explained as narrowing the channel to increase local flow velocities and boost centrifugal separation forces.
   - *Pitch/Revolutions increase*: Explained as lengthening particle residence time for additional centrifugal separation cycles.
3. **Intent Formulation**: It articulates a final engineering trade-off balance statement so that the fine-tuned model learns "the why" behind the adjustments.

---

## 5. Fine-Tuning Recipe (Axolotl / Hugging Face)

Once you've exported your datasets, you can launch a local fine-tuning job.

### Sample SFT Configuration (Axolotl `config.yml` snippet)
```yaml
base_model: Qwen/Qwen2.5-14B-Instruct
model_type: AutoModelForCausalLM
tokenizer_type: AutoTokenizer

datasets:
  - path: sft_chat_data.jsonl
    type: sharegpt  # compatible with openai chat format
    conversation: qwen-2.5

chat_template: qwen_2_5
output_dir: ./fine_tuned_physics_model

sequence_len: 4096
adapter: lora
lora_r: 16
lora_alpha: 32
lora_dropout: 0.05
lora_target_modules:
  - q_proj
  - k_proj
  - v_proj
  - o_proj
  - gate_proj
  - up_proj
  - down_proj

gradient_accumulation_steps: 4
micro_batch_size: 2
num_epochs: 3
learning_rate: 0.0002
optimizer: adamw_torch
lr_scheduler: cosine
```

Launch Axolotl:
```bash
accelerate launch -m axolotl.cli.train config.yml
```

---

## 6. Testing Your Fine-Tuned Model

After training, export your model weights and place them on your local Nomad, Docker, or local machine. You can activate the model in your optimization loop by pointing to it via environment variables:

```bash
# Configure the optimizer script to utilize your local/custom Ollama or OpenAI compatible model:
export OLLAMA_HOST="http://localhost:11434"
export OLLAMA_MODEL="fine_tuned_physics_model:latest"

# Run the design loop to evaluate the new model's performance!
python optimizer/main.py configs/corkscrew_config.yaml \
    --iterations 10 \
    --case-dir corkscrewFilter
```
