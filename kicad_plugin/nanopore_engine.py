"""
nanopore_engine.py

Nanopore Electrophysiology and Transimpedance Amplifier (TIA) Simulation Engine.
Models ionic baseline currents, molecular translocation blockade events, and analog frontend noise.
Directly aligns with amplifier.kicad_pcb (H1 nanopore holder, LMP7721, LTC6268, R1=1M, C1=2pF).
"""

import math
import random
from typing import Dict, List, Any, Optional


class NanoporeElectrophysiologyEngine:
    """
    Simulates:
    1. Open-channel ionic baseline current I_0 in electrolyte (1M KCl).
    2. Transimpedance amplifier feedback network (R_f = 1M, C_f = 2pF) frequency response and bandwidth.
    3. Noise spectrum: Johnson-Nyquist, shot noise, op-amp voltage noise amplification, and 1/f flicker.
    4. Stochastic single-molecule DNA/analyte translocation events (blockade depth and dwell time).
    """

    K_B = 1.380649e-23   # Boltzmann constant (J/K)
    Q_E = 1.60217663e-19  # Elementary charge (C)
    T_KELVIN = 295.15    # Room temperature 22 deg C (K)
    KCL_CONDUCTIVITY_1M = 10.5  # S/m for 1M KCl at 22C

    def __init__(
        self,
        default_feedback_r_ohms: float = 1.0e6,  # R1 = 1M
        default_feedback_c_farads: float = 2.0e-12, # C1 = 2pF
        opamp_en_nv_rt_hz: float = 6.5,          # LMP7721 input voltage noise (6.5 nV/rtHz)
        opamp_in_fa_rt_hz: float = 1.5           # LMP7721 input current noise (1.5 fA/rtHz)
    ):
        self.rf = default_feedback_r_ohms
        self.cf = default_feedback_c_farads
        self.en = opamp_en_nv_rt_hz * 1e-9
        self.in_noise = opamp_in_fa_rt_hz * 1e-15

    def calculate_open_pore_current(
        self,
        pore_diameter_nm: float = 4.0,
        pore_length_nm: float = 10.0,
        bias_voltage_mv: float = 100.0,
        electrolyte_conductivity_s_m: float = KCL_CONDUCTIVITY_1M
    ) -> Dict[str, float]:
        """
        Calculates open-channel conductance and baseline current using Hall & Hille pore formula.
        G_pore = kappa * [ (4 * l_pore) / (pi * d_pore^2) + 1 / d_pore ]^(-1)
        """
        d = max(0.5, float(pore_diameter_nm)) * 1e-9  # meters
        l = max(1.0, float(pore_length_nm)) * 1e-9    # meters
        v_bias = float(bias_voltage_mv) * 1e-3         # Volts
        kappa = float(electrolyte_conductivity_s_m)

        # Channel resistance + access resistance on both openings
        r_channel = (4.0 * l) / (math.pi * (d ** 2))
        r_access = 1.0 / d
        r_total = (r_channel + r_access) / kappa  # Ohms
        g_pore_siemens = 1.0 / r_total
        g_pore_ns = g_pore_siemens * 1e9

        i_base_a = v_bias * g_pore_siemens
        i_base_na = i_base_a * 1e9

        return {
            "pore_diameter_nm": float(pore_diameter_nm),
            "pore_length_nm": float(pore_length_nm),
            "bias_voltage_mv": float(bias_voltage_mv),
            "pore_resistance_gohm": round(r_total * 1e-9, 3),
            "pore_conductance_ns": round(g_pore_ns, 2),
            "baseline_current_na": round(i_base_na, 3)
        }

    def calculate_analog_frontend_noise(
        self,
        baseline_current_na: float = 2.50,
        total_input_cap_pf: float = 15.0 # Membrane cap + electrode + opamp input
    ) -> Dict[str, float]:
        """
        Computes the noise spectral density and total integrated RMS noise (in pA).
        """
        i_base_a = abs(baseline_current_na) * 1e-9
        c_tot = total_input_cap_pf * 1e-12

        # 1. Thermal Johnson noise of feedback resistor: S_th = 4 * k_B * T / R_f
        s_th = (4.0 * self.K_B * self.T_KELVIN) / self.rf

        # 2. Shot noise of pore current: S_shot = 2 * q * I_0
        s_shot = 2.0 * self.Q_E * i_base_a

        # 3. Cutoff frequency of transimpedance amplifier: f_c = 1 / (2 * pi * R_f * C_f)
        fc_hz = 1.0 / (2.0 * math.pi * self.rf * self.cf)
        fc_khz = fc_hz * 1e-3

        # 4. Integrated RMS current noise over TIA bandwidth
        # Resistor + shot noise integrated: S_white * (pi/2 * fc)
        rms_white_a = math.sqrt((s_th + s_shot) * (math.pi / 2.0 * fc_hz))
        # Voltage noise amplification integrated: (4/3) * pi^2 * en^2 * C_tot^2 * fc^3
        rms_v_a = math.sqrt((4.0 / 3.0) * (math.pi ** 2) * (self.en ** 2) * (c_tot ** 2) * (fc_hz ** 3))
        
        rms_total_a = math.sqrt(rms_white_a ** 2 + rms_v_a ** 2)
        rms_total_pa = rms_total_a * 1e12

        return {
            "tia_bandwidth_khz": round(fc_khz, 1),
            "thermal_noise_density_fa_rt_hz": round(math.sqrt(s_th) * 1e15, 1),
            "shot_noise_density_fa_rt_hz": round(math.sqrt(s_shot) * 1e15, 1),
            "rms_noise_pa": round(rms_total_pa, 2),
            "feedback_resistor_mohm": round(self.rf * 1e-6, 2),
            "feedback_cap_pf": round(self.cf * 1e12, 2)
        }

    def simulate_translocation_stream(
        self,
        pore_diameter_nm: float = 4.0,
        pore_length_nm: float = 10.0,
        bias_voltage_mv: float = 100.0,
        duration_ms: float = 2.0,
        sample_rate_khz: float = 500.0,
        target_event_rate_hz: float = 3000.0,
        blockade_fraction_mean: float = 0.78,
        dwell_time_us_mean: float = 75.0
    ) -> Dict[str, Any]:
        """
        Generates continuous synthetic electrophysiology current time-series i(t) with:
        - Baseline ionic current
        - Band-limited analog frontend Gaussian noise
        - Real single-molecule translocation blockade events shaped by TIA filter response
        """
        base_res = self.calculate_open_pore_current(pore_diameter_nm, pore_length_nm, bias_voltage_mv)
        i0_na = base_res["baseline_current_na"]

        noise_res = self.calculate_analog_frontend_noise(i0_na)
        rms_noise_na = noise_res["rms_noise_pa"] * 1e-3
        fc_khz = noise_res["tia_bandwidth_khz"]

        dt_us = 1000.0 / sample_rate_khz
        total_us = duration_ms * 1000.0
        n_samples = int(total_us / dt_us)

        time_us = [round(i * dt_us, 1) for i in range(n_samples)]
        current_na = [i0_na] * n_samples

        # Generate translocation events using Poisson arrival process
        expected_events = int((total_us * 1e-6) * target_event_rate_hz)
        num_events = max(1, min(12, int(random.gauss(expected_events, math.sqrt(max(1, expected_events))))))

        events_meta = []
        occupied_spans = []

        for ev_idx in range(num_events):
            dwell_us = max(25.0, random.gauss(dwell_time_us_mean, 20.0))
            block_frac = max(0.4, min(0.92, random.gauss(blockade_fraction_mean, 0.05)))
            delta_i_na = i0_na * block_frac

            # Random start time avoiding overlap
            t_start = random.uniform(50.0, max(60.0, total_us - dwell_us - 50.0))
            overlap = any(abs(t_start - prev[0]) < (dwell_us + prev[1] + 30.0) for prev in occupied_spans)
            if overlap:
                continue

            occupied_spans.append((t_start, dwell_us))
            t_end = t_start + dwell_us

            events_meta.append({
                "id": ev_idx + 1,
                "start_us": round(t_start, 1),
                "dwell_us": round(dwell_us, 1),
                "blockade_depth_pct": round(block_frac * 100.0, 1),
                "residual_current_na": round(i0_na - delta_i_na, 3)
            })

            # Apply filtered blockade pulse to time-series
            # Convolve pulse edges with analog TIA rise-time tau = 1 / (2 * pi * fc)
            tau_rise_us = (1.0 / (2.0 * math.pi * fc_khz * 1000.0)) * 1e6

            for idx, t in enumerate(time_us):
                if t_start - 3 * tau_rise_us <= t <= t_end + 3 * tau_rise_us:
                    # Filtered leading and trailing edges
                    trans_in = 0.5 * (1.0 + math.erf((t - t_start) / (tau_rise_us * 1.8)))
                    trans_out = 0.5 * (1.0 + math.erf((t - t_end) / (tau_rise_us * 1.8)))
                    pulse_shape = trans_in - trans_out
                    current_na[idx] -= delta_i_na * max(0.0, min(1.0, pulse_shape))

        # Add Gaussian band-limited noise to each sample
        for idx in range(n_samples):
            current_na[idx] = round(current_na[idx] + random.gauss(0.0, rms_noise_na), 4)

        # Calculate Signal-to-Noise Ratio (SNR)
        mean_delta_i = i0_na * blockade_fraction_mean
        snr_linear = mean_delta_i / max(1e-6, rms_noise_na)
        snr_db = round(20.0 * math.log10(max(1.0, snr_linear)), 1)

        return {
            "baseline_current_na": i0_na,
            "rms_noise_pa": noise_res["rms_noise_pa"],
            "tia_bandwidth_khz": fc_khz,
            "snr_db": snr_db,
            "events_detected": len(events_meta),
            "mean_dwell_us": round(sum(e["dwell_us"] for e in events_meta) / max(1, len(events_meta)), 1) if events_meta else 0.0,
            "events": events_meta,
            "time_us": time_us,
            "current_na": current_na
        }
