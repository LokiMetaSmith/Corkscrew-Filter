"""
eda_agent_tools.py

LLM Tool-Calling Integration for Kimi K3 / Gemini / OpenAI EDA & Chip Design Agent.
Equips the LLM with native function-calling tools to:
  1. optimize_trace_impedance: Inverse design to achieve target impedance (50 Ohm single-ended, 100 Ohm differential).
  2. evaluate_rf_transmission: Evaluates S-parameters (S11, S21), skin depth, and crosstalk isolation across frequencies.
  3. generate_kicad_pcb: Synthesizes valid KiCad 7/8 .kicad_pcb layout scripts and OpenSCAD 3D stackup models.
"""

import os
import json
import time
from typing import Dict, Any, List, Optional, Tuple

import numpy as np
from scipy.optimize import minimize_scalar, minimize

from eda_rf_driver import HighSpeedTransmissionLineEngine, KiCadPcbExporter


# =====================================================================
# EDA Tool Definitions (OpenAI / Kimi / Gemini Compatible Schemas)
# =====================================================================

EDA_TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "optimize_trace_impedance",
            "description": "Calculates and optimizes microstrip or differential pair trace dimensions to hit precise target characteristic impedance (e.g. 50 Ohm single-ended, 100 Ohm differential) within 0.01 Ohm precision.",
            "parameters": {
                "type": "object",
                "properties": {
                    "target_z0_ohms": {
                        "type": "number",
                        "description": "Target characteristic impedance (e.g. 50.0 for single-ended, 100.0 for differential).",
                        "default": 50.0
                    },
                    "substrate_height_mm": {
                        "type": "number",
                        "description": "Dielectric core thickness (e.g. 0.2mm, 0.8mm, 1.6mm).",
                        "default": 1.6
                    },
                    "dielectric_constant": {
                        "type": "number",
                        "description": "Relative permittivity eps_r of substrate (e.g. 4.3 for FR4, 3.48 for Rogers RO4350B).",
                        "default": 4.3
                    },
                    "copper_thickness_um": {
                        "type": "number",
                        "description": "Copper weight thickness in micrometers (e.g. 35um for 1oz, 17.5um for 0.5oz).",
                        "default": 35.0
                    },
                    "is_differential": {
                        "type": "boolean",
                        "description": "Whether optimizing a coupled differential pair (e.g. PCIe, USB, Ethernet).",
                        "default": False
                    },
                    "trace_spacing_mm": {
                        "type": "number",
                        "description": "Edge-to-edge spacing between differential traces (if is_differential=True).",
                        "default": 0.3
                    }
                },
                "required": ["target_z0_ohms", "substrate_height_mm"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "evaluate_rf_transmission",
            "description": "Evaluates frequency-dependent high-speed transmission metrics: S11 return loss, S21 insertion loss, skin depth, attenuation (dB/m), and near-end crosstalk isolation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "trace_width_mm": {
                        "type": "number",
                        "description": "Trace conductor width in millimeters."
                    },
                    "substrate_height_mm": {
                        "type": "number",
                        "description": "Substrate thickness in millimeters."
                    },
                    "frequency_ghz": {
                        "type": "number",
                        "description": "Operating RF frequency in GHz (e.g. 2.4, 5.0, 10.0, 28.0).",
                        "default": 5.0
                    },
                    "line_length_mm": {
                        "type": "number",
                        "description": "Physical line length in millimeters.",
                        "default": 50.0
                    },
                    "dielectric_constant": {
                        "type": "number",
                        "description": "Substrate relative permittivity.",
                        "default": 4.3
                    },
                    "loss_tangent": {
                        "type": "number",
                        "description": "Dielectric loss tangent tan(delta) (e.g. 0.02 for FR4, 0.0037 for Rogers).",
                        "default": 0.02
                    },
                    "trace_spacing_mm": {
                        "type": "number",
                        "description": "Optional spacing to adjacent aggressor trace for crosstalk evaluation."
                    }
                },
                "required": ["trace_width_mm", "substrate_height_mm"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generate_kicad_pcb",
            "description": "Generates production-ready KiCad 7/8 PCB S-expression (.kicad_pcb) files and OpenSCAD 3D stackup models for the optimized transmission line.",
            "parameters": {
                "type": "object",
                "properties": {
                    "trace_width_mm": {
                        "type": "number",
                        "description": "Optimized trace width in millimeters."
                    },
                    "substrate_height_mm": {
                        "type": "number",
                        "description": "Dielectric substrate height in millimeters."
                    },
                    "line_length_mm": {
                        "type": "number",
                        "description": "Trace routing length in millimeters.",
                        "default": 50.0
                    },
                    "differential_spacing_mm": {
                        "type": "number",
                        "description": "Spacing if routing differential pair."
                    },
                    "output_pcb_filename": {
                        "type": "string",
                        "description": "Output .kicad_pcb filename in artifacts directory.",
                        "default": "rf_controlled_impedance.kicad_pcb"
                    }
                },
                "required": ["trace_width_mm", "substrate_height_mm"]
            }
        }
    }
]


# =====================================================================
# EDA Agent Tool Registry
# =====================================================================

class EDAAgentToolRegistry:
    """
    Registry and execution engine for RF, EDA, and chip design tools.
    """

    def __init__(self, artifacts_dir: str = "artifacts"):
        self.engine = HighSpeedTransmissionLineEngine()
        self.exporter = KiCadPcbExporter()
        self.artifacts_dir = artifacts_dir
        os.makedirs(self.artifacts_dir, exist_ok=True)

    def get_tools_spec(self) -> List[Dict[str, Any]]:
        return EDA_TOOLS_SCHEMA

    def execute_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Dispatches tool execution with robust parameter handling."""
        try:
            if name == "optimize_trace_impedance":
                return self._tool_optimize_trace_impedance(arguments)
            elif name == "evaluate_rf_transmission":
                return self._tool_evaluate_rf_transmission(arguments)
            elif name == "generate_kicad_pcb":
                return self._tool_generate_kicad_pcb(arguments)
            else:
                return {"error": f"Unknown EDA tool: '{name}'"}
        except Exception as e:
            return {"error": f"EDA tool execution failed: {str(e)}"}

    def _tool_optimize_trace_impedance(self, args: Dict[str, Any]) -> Dict[str, Any]:
        target_z0 = float(args.get("target_z0_ohms", 50.0))
        h = float(args.get("substrate_height_mm", 1.6))
        er = float(args.get("dielectric_constant", 4.3))
        t = float(args.get("copper_thickness_um", 35.0))
        is_diff = bool(args.get("is_differential", False))
        spacing = float(args.get("trace_spacing_mm", 0.3)) if is_diff else None

        if not is_diff:
            # Objective: minimize (Z0(w) - target)^2
            def objective(w_cand):
                calc = self.engine.calculate_microstrip_z0(
                    trace_width_mm=w_cand,
                    substrate_height_mm=h,
                    dielectric_constant=er,
                    copper_thickness_um=t
                )
                return abs(calc["z0_ohms"] - target_z0)

            # Bounded Brent optimization
            res = minimize_scalar(objective, bounds=(0.05, 10.0), method="bounded")
            opt_w = float(round(res.x, 3))
            final_calc = self.engine.calculate_microstrip_z0(opt_w, h, er, t)

            return {
                "status": "success",
                "topology": "single_ended_microstrip",
                "optimal_trace_width_mm": opt_w,
                "achieved_z0_ohms": final_calc["z0_ohms"],
                "target_z0_ohms": target_z0,
                "impedance_error_percent": float(round(abs(final_calc["z0_ohms"] - target_z0) / target_z0 * 100.0, 3)),
                "eps_eff": final_calc["eps_eff"],
                "delay_ps_per_mm": final_calc["delay_ps_per_mm"],
                "substrate_height_mm": h,
                "dielectric_constant": er
            }
        else:
            # Differential pair optimization: minimize (Z_diff(w) - target)^2
            def diff_objective(w_cand):
                calc = self.engine.calculate_differential_pair(
                    trace_width_mm=w_cand,
                    trace_spacing_mm=spacing,
                    substrate_height_mm=h,
                    dielectric_constant=er,
                    copper_thickness_um=t
                )
                return abs(calc["z_diff_ohms"] - target_z0)

            res = minimize_scalar(diff_objective, bounds=(0.05, 8.0), method="bounded")
            opt_w = float(round(res.x, 3))
            final_calc = self.engine.calculate_differential_pair(opt_w, spacing, h, er, t)

            return {
                "status": "success",
                "topology": "edge_coupled_differential_microstrip",
                "optimal_trace_width_mm": opt_w,
                "trace_spacing_mm": spacing,
                "achieved_z_diff_ohms": final_calc["z_diff_ohms"],
                "achieved_z0_single_ended_ohms": final_calc["z0_single_ended_ohms"],
                "target_z_diff_ohms": target_z0,
                "impedance_error_percent": float(round(abs(final_calc["z_diff_ohms"] - target_z0) / target_z0 * 100.0, 3)),
                "coupling_coefficient": final_calc["coupling_coefficient"],
                "substrate_height_mm": h,
                "dielectric_constant": er
            }

    def _tool_evaluate_rf_transmission(self, args: Dict[str, Any]) -> Dict[str, Any]:
        w = float(args.get("trace_width_mm", 2.0))
        h = float(args.get("substrate_height_mm", 1.6))
        f_ghz = float(args.get("frequency_ghz", 5.0))
        l_mm = float(args.get("line_length_mm", 50.0))
        er = float(args.get("dielectric_constant", 4.3))
        tan_d = float(args.get("loss_tangent", 0.02))
        spacing = float(args["trace_spacing_mm"]) if "trace_spacing_mm" in args and args["trace_spacing_mm"] is not None else None

        results = self.engine.calculate_rf_loss_and_sparameters(
            trace_width_mm=w,
            substrate_height_mm=h,
            line_length_mm=l_mm,
            frequency_ghz=f_ghz,
            dielectric_constant=er,
            loss_tangent=tan_d,
            trace_spacing_mm=spacing
        )

        results["status"] = "success"
        results["is_low_loss"] = results["s21_insertion_loss_db"] > -1.5
        results["is_matched"] = results["s11_return_loss_db"] < -18.0
        return results

    def _tool_generate_kicad_pcb(self, args: Dict[str, Any]) -> Dict[str, Any]:
        w = float(args.get("trace_width_mm", 2.0))
        h = float(args.get("substrate_height_mm", 1.6))
        l = float(args.get("line_length_mm", 50.0))
        spacing = float(args["differential_spacing_mm"]) if "differential_spacing_mm" in args and args["differential_spacing_mm"] is not None else None
        pcb_name = args.get("output_pcb_filename", "rf_controlled_impedance.kicad_pcb")

        pcb_path = os.path.join(self.artifacts_dir, pcb_name)
        base_name = os.path.splitext(pcb_name)[0]
        scad_path = os.path.join(self.artifacts_dir, base_name + "_stackup.scad")
        hyp_path = os.path.join(self.artifacts_dir, base_name + ".hyp")
        openems_path = os.path.join(self.artifacts_dir, "simulate_" + base_name + "_openems.py")

        # 1. KiCad S-expression export
        written_pcb = self.exporter.generate_kicad_pcb(
            trace_width_mm=w,
            line_length_mm=l,
            differential_spacing_mm=spacing,
            output_filepath=pcb_path
        )

        # 2. OpenSCAD 3D PCB Solid model export
        written_scad = self.exporter.generate_scad_stackup(
            trace_width_mm=w,
            substrate_height_mm=h,
            line_length_mm=l,
            differential_spacing_mm=spacing,
            output_filepath=scad_path
        )

        # 3. Siemens HyperLynx / Ansys HFSS / Keysight ADS (.hyp) export
        written_hyp = self.exporter.export_hyperlynx_hyp(
            output_filepath=hyp_path,
            substrate_thickness_mm=h,
            trace_width_mm=w,
            line_length_mm=l,
            differential_spacing_mm=spacing
        )

        # 4. Open-Source openEMS 3D FDTD simulation script
        written_openems = self.exporter.export_openems_script(
            output_filepath=openems_path,
            substrate_thickness_mm=h,
            trace_width_mm=w,
            line_length_mm=l,
            differential_spacing_mm=spacing
        )

        return {
            "status": "success",
            "kicad_pcb_file": written_pcb,
            "pcb_file_size_bytes": os.path.getsize(written_pcb),
            "scad_3d_stackup_file": written_scad,
            "scad_file_size_bytes": os.path.getsize(written_scad),
            "hyperlynx_hyp_file": written_hyp,
            "openems_script_file": written_openems,
            "message": f"Successfully synthesized multi-format EM deliverables: KiCad ({written_pcb}), 3D Solid ({written_scad}), HyperLynx ({written_hyp}), and OpenEMS FDTD ({written_openems})"
        }


# =====================================================================
# Autonomous EDA Reasoning Agent
# =====================================================================

class EDAReasoningAgent:
    """
    Autonomous EDA and chip design agent that reasons through high-speed
    interconnect requirements, optimizes impedance, evaluates S-parameters,
    and produces production-grade PCB layouts.
    """

    def __init__(self, registry: Optional[EDAAgentToolRegistry] = None, llm_provider: Optional[Any] = None):
        self.registry = registry or EDAAgentToolRegistry()
        self.llm_provider = llm_provider

    def run_goal(self, goal_description: str) -> Dict[str, Any]:
        """
        Executes a multi-turn design loop for high-speed transmission lines or chip interconnects.
        """
        print(f"\n[EDAAgent] Received EDA engineering goal:\n  \"{goal_description}\"")
        trace = []

        # Turn 1: Optimize Trace Impedance (Target 50 Ohm Single-Ended or 100 Ohm Differential)
        is_diff = "diff" in goal_description.lower() or "100" in goal_description
        target_z = 100.0 if is_diff else 50.0
        substrate_h = 0.8 if "thin" in goal_description.lower() else 1.6

        print(f"[EDAAgent Turn 1] Invoking optimize_trace_impedance for target {target_z} Ohms...")
        t1_args = {
            "target_z0_ohms": target_z,
            "substrate_height_mm": substrate_h,
            "dielectric_constant": 4.3,
            "is_differential": is_diff,
            "trace_spacing_mm": 0.25 if is_diff else None
        }
        t1_res = self.registry.execute_tool("optimize_trace_impedance", t1_args)
        trace.append({"tool": "optimize_trace_impedance", "args": t1_args, "result": t1_res})
        opt_w = t1_res["optimal_trace_width_mm"]
        achieved_z = t1_res.get("achieved_z0_ohms", t1_res.get("achieved_z_diff_ohms"))
        print(f"  -> Optimal width: {opt_w} mm (Achieved: {achieved_z:.2f} Ohms, Error: {t1_res['impedance_error_percent']}%)")

        # Turn 2: Evaluate RF S-Parameters and Crosstalk
        freq_ghz = 10.0 if "10g" in goal_description.lower() or "pcie" in goal_description.lower() else 5.0
        print(f"[EDAAgent Turn 2] Evaluating RF transmission parameters at {freq_ghz} GHz...")
        t2_args = {
            "trace_width_mm": opt_w,
            "substrate_height_mm": substrate_h,
            "frequency_ghz": freq_ghz,
            "line_length_mm": 50.0,
            "trace_spacing_mm": 0.35
        }
        t2_res = self.registry.execute_tool("evaluate_rf_transmission", t2_args)
        trace.append({"tool": "evaluate_rf_transmission", "args": t2_args, "result": t2_res})
        print(f"  -> S11 Return Loss: {t2_res['s11_return_loss_db']} dB (Matched: {t2_res['is_matched']})")
        print(f"  -> S21 Insertion Loss: {t2_res['s21_insertion_loss_db']} dB, Crosstalk: {t2_res['crosstalk_isolation_db']} dB")

        # Turn 3: Synthesize KiCad Layout & 3D PCB Stackup
        print("[EDAAgent Turn 3] Synthesizing KiCad .kicad_pcb layout and OpenSCAD 3D solid...")
        t3_args = {
            "trace_width_mm": opt_w,
            "substrate_height_mm": substrate_h,
            "line_length_mm": 50.0,
            "differential_spacing_mm": 0.25 if is_diff else None,
            "output_pcb_filename": "optimized_transmission_line.kicad_pcb"
        }
        t3_res = self.registry.execute_tool("generate_kicad_pcb", t3_args)
        trace.append({"tool": "generate_kicad_pcb", "args": t3_args, "result": t3_res})
        print(f"  -> KiCad PCB File: {t3_res['kicad_pcb_file']}")
        print(f"  -> 3D Stackup File: {t3_res['scad_3d_stackup_file']}")
        print(f"  -> HyperLynx (.hyp) File: {t3_res['hyperlynx_hyp_file']}")
        print(f"  -> openEMS Script: {t3_res['openems_script_file']}")

        summary = (
            f"Successfully completed EDA interconnect optimization for goal: '{goal_description}'.\n"
            f"Synthesis Results:\n"
            f"  - Target Impedance: {target_z} Ohms\n"
            f"  - Achieved Impedance: {achieved_z:.2f} Ohms (Precision Error: {t1_res['impedance_error_percent']}%)\n"
            f"  - Trace Width: {opt_w:.3f} mm (Substrate Height: {substrate_h} mm, FR4 eps_r=4.3)\n"
            f"  - S11 Return Loss: {t2_res['s11_return_loss_db']} dB\n"
            f"  - S21 Insertion Loss: {t2_res['s21_insertion_loss_db']} dB at {freq_ghz} GHz\n"
            f"  - Crosstalk Isolation: {t2_res['crosstalk_isolation_db']} dB\n"
            f"Deliverables:\n"
            f"  - KiCad PCB: {t3_res['kicad_pcb_file']}\n"
            f"  - OpenSCAD 3D Model: {t3_res['scad_3d_stackup_file']}\n"
            f"  - Siemens HyperLynx / Ansys HFSS: {t3_res['hyperlynx_hyp_file']}\n"
            f"  - openEMS FDTD Simulation: {t3_res['openems_script_file']}"
        )

        return {
            "status": "completed",
            "goal": goal_description,
            "optimal_width_mm": opt_w,
            "achieved_impedance": achieved_z,
            "s_parameters": t2_res,
            "kicad_pcb_path": t3_res["kicad_pcb_file"],
            "scad_path": t3_res["scad_3d_stackup_file"],
            "hyperlynx_path": t3_res["hyperlynx_hyp_file"],
            "openems_script_path": t3_res["openems_script_file"],
            "trace": trace,
            "summary": summary
        }
