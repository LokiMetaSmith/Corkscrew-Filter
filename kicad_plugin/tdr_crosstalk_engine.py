"""
tdr_crosstalk_engine.py

Time-Domain Reflectometry (TDR) and Coupled Microstrip Crosstalk (NEXT / FEXT)
Physical Simulation Engine for High-Speed EDA and RF Layout Analysis.
"""

import math
from typing import Dict, List, Any, Optional
try:
    from .eda_rf_driver import HighSpeedTransmissionLineEngine
except (ImportError, ValueError):
    from eda_rf_driver import HighSpeedTransmissionLineEngine


class TDRCrosstalkEngine:
    """
    Simulates:
    1. Time-Domain Reflectometry (TDR) step pulse response along physical PCB interconnects.
    2. Spatial impedance profile Z(x) pinpointing connector launches, trace segments, vias, and pads.
    3. Coupled microstrip Near-End Crosstalk (NEXT) and Far-End Crosstalk (FEXT) in frequency domain.
    """

    C_0 = 2.99792458e8  # m/s in vacuum
    C_MM_PS = 0.299792458  # mm/ps in vacuum

    def __init__(self, tline_engine: Optional[HighSpeedTransmissionLineEngine] = None):
        self.tline_engine = tline_engine or HighSpeedTransmissionLineEngine()

    def simulate_tdr_profile(
        self,
        trace_width_mm: float,
        substrate_height_mm: float,
        total_length_mm: float = 35.0,
        dielectric_constant: float = 2.1,
        copper_thickness_um: float = 35.0,
        rise_time_ps: float = 25.0,
        z_ref_ohms: float = 50.0,
        include_connector: bool = True,
        include_via: bool = True
    ) -> Dict[str, Any]:
        """
        Computes TDR step response and instantaneous impedance Z(x) vs physical distance (mm).
        """
        w = max(0.1, float(trace_width_mm))
        h = max(0.1, float(substrate_height_mm))
        er = max(1.0, float(dielectric_constant))
        length = max(5.0, float(total_length_mm))

        z_res = self.tline_engine.calculate_microstrip_z0(w, h, er, copper_thickness_um)
        z0 = z_res["z0_ohms"]
        eps_eff = z_res.get("eps_eff", er)

        vp_mm_ps = self.C_MM_PS / math.sqrt(max(1.0, eps_eff))

        x_launch_end = min(3.0, length * 0.1)
        x_via = length * 0.65 if include_via else None
        x_pad = length

        z_launch_dip = max(25.0, z_ref_ohms - 6.5) if include_connector else z_ref_ohms
        z_via_spike = z0 + 18.0 if include_via else z0
        z_pad_load = z_ref_ohms

        discontinuities = [
            {"name": "Source Port (SMA/JST)", "x_mm": 0.0, "z_ohms": z_ref_ohms, "type": "port"},
            {"name": "Connector Launch Dip", "x_mm": round(x_launch_end, 2), "z_ohms": round(z_launch_dip, 2), "type": "capacitive"},
            {"name": "Microstrip Plateau", "x_mm": round(length * 0.35, 2), "z_ohms": round(z0, 2), "type": "trace"},
        ]
        if include_via and x_via is not None:
            discontinuities.append(
                {"name": "Via Barrel Transition", "x_mm": round(x_via, 2), "z_ohms": round(z_via_spike, 2), "type": "inductive"}
            )
        discontinuities.append(
            {"name": "IC Package Pad (Termination)", "x_mm": round(x_pad, 2), "z_ohms": round(z_pad_load, 2), "type": "pad"}
        )

        num_points = 120
        dx = length / (num_points - 1)
        distance_mm = []
        z_tdr_ohms = []
        gamma_list = []
        v_refl_mv = []

        v_step_mv = 500.0
        sigma_x = max(0.4, (vp_mm_ps * rise_time_ps) / 2.355)

        for i in range(num_points):
            x = i * dx
            distance_mm.append(round(x, 3))

            f_launch = 0.5 * (1.0 + math.erf((x - 0.8) / sigma_x)) - 0.5 * (1.0 + math.erf((x - x_launch_end) / sigma_x))
            f_trace = 0.5 * (1.0 + math.erf((x - x_launch_end) / sigma_x))
            f_via = 0.0
            if include_via and x_via is not None:
                f_via = math.exp(-0.5 * ((x - x_via) / (sigma_x * 0.8)) ** 2)
            f_pad = 0.5 * (1.0 + math.erf((x - (x_pad - 1.5)) / sigma_x))

            z_profile = (
                z_ref_ohms * (1.0 - f_trace)
                + z_launch_dip * f_launch
                + z0 * f_trace * (1.0 - f_pad)
                + (z_via_spike - z0) * f_via
                + z_pad_load * f_pad
            )
            z_profile = max(10.0, min(300.0, z_profile))
            z_tdr_ohms.append(round(z_profile, 2))

            rho = (z_profile - z_ref_ohms) / (z_profile + z_ref_ohms)
            gamma_list.append(round(rho, 4))
            v_refl_mv.append(round(v_step_mv * rho, 2))

        time_ps = [round((2.0 * x) / vp_mm_ps, 1) for x in distance_mm]

        return {
            "trace_width_mm": w,
            "total_length_mm": length,
            "z0_ohms": round(z0, 2),
            "propagation_velocity_mm_ps": round(vp_mm_ps, 4),
            "rise_time_ps": rise_time_ps,
            "distance_mm": distance_mm,
            "time_ps": time_ps,
            "z_tdr_ohms": z_tdr_ohms,
            "gamma_profile": gamma_list,
            "v_refl_mv": v_refl_mv,
            "discontinuities": discontinuities,
            "z_min_ohms": round(min(z_tdr_ohms), 2),
            "z_max_ohms": round(max(z_tdr_ohms), 2)
        }

    def simulate_crosstalk_spectra(
        self,
        trace_width_mm: float,
        trace_spacing_mm: float,
        substrate_height_mm: float,
        line_length_mm: float = 35.0,
        dielectric_constant: float = 2.1,
        copper_thickness_um: float = 35.0
    ) -> Dict[str, Any]:
        """
        Computes Near-End Crosstalk (NEXT) and Far-End Crosstalk (FEXT) in frequency domain (0.5 to 30 GHz).
        """
        w = max(0.1, float(trace_width_mm))
        s = max(0.1, float(trace_spacing_mm))
        h = max(0.1, float(substrate_height_mm))
        er = max(1.0, float(dielectric_constant))
        length_mm = max(5.0, float(line_length_mm))

        diff_res = self.tline_engine.calculate_differential_pair(
            trace_width_mm=w,
            trace_spacing_mm=s,
            substrate_height_mm=h,
            dielectric_constant=er,
            copper_thickness_um=copper_thickness_um
        )

        z0 = diff_res["z0_single_ended_ohms"]
        z_odd = diff_res["z_odd_ohms"]
        z_even = diff_res["z_even_ohms"]
        eps_eff = diff_res.get("eps_eff", er)

        vp_m_s = self.C_0 / math.sqrt(max(1.0, eps_eff))
        td_sec = (length_mm * 1e-3) / vp_m_s

        k_next = max(0.001, (z_even - z_odd) / max(1.0, (z_even + z_odd)))
        k_fext = k_next * 0.42

        frequencies_ghz = [round(0.5 + i * (29.5 / 59.0), 2) for i in range(60)]
        next_db = []
        fext_db = []

        for f_ghz in frequencies_ghz:
            f_hz = f_ghz * 1e9
            theta = 2.0 * math.pi * f_hz * td_sec

            v_next_ratio = k_next * math.sin(theta)
            next_val_db = 20.0 * math.log10(max(1e-5, abs(v_next_ratio)))
            next_val_db = max(-75.0, min(-3.0, next_val_db))
            next_db.append(round(next_val_db, 2))

            v_fext_ratio = k_fext * theta * 0.5
            fext_val_db = 20.0 * math.log10(max(1e-5, abs(v_fext_ratio)))
            fext_val_db = max(-85.0, min(-6.0, fext_val_db))
            fext_db.append(round(fext_val_db, 2))

        return {
            "trace_width_mm": w,
            "trace_spacing_mm": s,
            "line_length_mm": length_mm,
            "z0_ohms": round(z0, 2),
            "z_odd_ohms": z_odd,
            "z_even_ohms": z_even,
            "coupling_coefficient": round(k_next, 4),
            "frequencies_ghz": frequencies_ghz,
            "next_db": next_db,
            "fext_db": fext_db,
            "peak_next_db": round(max(next_db), 2),
            "peak_fext_db": round(max(fext_db), 2),
            "isolation_status": "EXCELLENT (< -40dB)" if max(next_db) < -40.0 else ("GOOD (< -30dB)" if max(next_db) < -30.0 else "WARNING (> -30dB)")
        }
