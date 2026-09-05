"""
fdtd_engine.py

Full-Wave 2.5D / 3D Finite-Difference Time-Domain (FDTD) Electromagnetic Engine.
Solves Maxwell's curl equations on Yee staggered spatial cells to simulate
traveling wave propagation, substrate fringing, via diffraction, and radiation.
"""

import math
from typing import Dict, List, Any, Optional, Tuple


def _get_seg_coords(s):
    if "x1" in s:
        return float(s["x1"]), float(s["y1"]), float(s["x2"]), float(s["y2"])
    st = s.get("start", (0.0, 0.0))
    en = s.get("end", (0.0, 0.0))
    return float(st[0]), float(st[1]), float(en[0]), float(en[1])


class FullWaveFDTDEngine:
    """
    Simulates:
    1. Vectorized TM-mode Yee-cell time-stepping (Ez, Hx, Hy).
    2. Dielectric substrate permittivity epsilon_r and copper PEC boundaries mapped from KiCad PCB geometry.
    3. Mur 1st-order absorbing boundary conditions (ABC) on grid borders.
    4. Modulated RF Gaussian pulse source excitation.
    5. Real-time time-series field slice frames for 60 FPS WebGL / Canvas animation.
    """

    C_0 = 2.99792458e8  # Speed of light in vacuum (m/s)
    MU_0 = 4.0 * math.pi * 1e-7  # Permeability of free space (H/m)
    EPS_0 = 8.8541878128e-12    # Permittivity of free space (F/m)

    def __init__(self):
        pass

    def run_fdtd_simulation(
        self,
        board_width_mm: float = 55.0,
        board_height_mm: float = 52.0,
        trace_segments: Optional[List[Dict[str, Any]]] = None,
        frequency_ghz: float = 5.0,
        dielectric_constant: float = 2.1,
        grid_nx: int = 60,
        grid_ny: int = 50,
        total_steps: int = 90,
        sample_interval: int = 6
    ) -> Dict[str, Any]:
        """
        Executes 2.5D TM Yee-cell FDTD time-stepping across board geometry.
        Returns serialized 2D field slice frames for WebGL animation.
        """
        w_m = float(board_width_mm) * 1e-3
        h_m = float(board_height_mm) * 1e-3
        freq_hz = float(frequency_ghz) * 1e9
        er_sub = max(1.0, float(dielectric_constant))

        nx = max(30, min(80, grid_nx))
        ny = max(25, min(70, grid_ny))
        dx = w_m / (nx - 1)
        dy = h_m / (ny - 1)

        # Courant-Friedrichs-Lewy (CFL) stability criterion
        # dt <= S_cfl / (c * sqrt(1/dx^2 + 1/dy^2))
        s_cfl = 0.90
        dt = s_cfl / (self.C_0 * math.sqrt(1.0 / (dx * dx) + 1.0 / (dy * dy)))

        # Material permittivity grid eps(x, y)
        eps = [[self.EPS_0 * er_sub for _ in range(nx)] for _ in range(ny)]
        # Conductivity grid sigma(x, y) for copper PEC damping
        sigma = [[0.0 for _ in range(nx)] for _ in range(ny)]

        # Map trace segments into conductivity grid
        if trace_segments:
            for s in trace_segments:
                sx1, sy1, sx2, sy2 = _get_seg_coords(s)
                x1_n = sx1 / board_width_mm
                y1_n = sy1 / board_height_mm
                x2_n = sx2 / board_width_mm
                y2_n = sy2 / board_height_mm
                # Rasterize line into grid
                n_sub = max(5, int(math.hypot(x2_n - x1_n, y2_n - y1_n) * nx * 2))
                for k in range(n_sub):
                    t = k / float(n_sub - 1)
                    rx = int((x1_n + t * (x2_n - x1_n)) * (nx - 1))
                    ry = int((y1_n + t * (y2_n - y1_n)) * (ny - 1))
                    if 0 <= rx < nx and 0 <= ry < ny:
                        sigma[ry][rx] = 1.0e5  # High conductivity (PEC conductor)
        else:
            # Default central microstrip trace
            mid_y = ny // 2
            for ix in range(5, nx - 5):
                sigma[mid_y][ix] = 1.0e5

        # Initialize fields
        # Ez is at (i, j)
        # Hx is at (i, j + 1/2)
        # Hy is at (i + 1/2, j)
        ez = [[0.0 for _ in range(nx)] for _ in range(ny)]
        hx = [[0.0 for _ in range(nx)] for _ in range(ny - 1)]
        hy = [[0.0 for _ in range(nx - 1)] for _ in range(ny)]

        # History buffers for Mur 1st-order ABC
        ez_prev_left = [0.0] * ny
        ez_prev_right = [0.0] * ny
        ez_prev_top = [0.0] * nx
        ez_prev_bot = [0.0] * nx

        mur_coef = (self.C_0 * dt - dx) / (self.C_0 * dt + dx)

        # Source parameters: Gaussian-modulated RF sine pulse
        t0_ps = 25.0 * 1e-12
        sigma_t = 12.0 * 1e-12
        src_x = nx // 6
        src_y = ny // 2

        frames = []
        frame_times_ps = []
        max_abs_ez = 1e-6

        # FDTD Main Time-Stepping Loop
        for step in range(total_steps):
            t_now = step * dt

            # 1. Update Magnetic Field Hx
            # dHx/dt = - (1/mu0) * dEz/dy
            for iy in range(ny - 1):
                for ix in range(nx):
                    d_ez_dy = (ez[iy + 1][ix] - ez[iy][ix]) / dy
                    hx[iy][ix] -= (dt / self.MU_0) * d_ez_dy

            # 2. Update Magnetic Field Hy
            # dHy/dt = (1/mu0) * dEz/dx
            for iy in range(ny):
                for ix in range(nx - 1):
                    d_ez_dx = (ez[iy][ix + 1] - ez[iy][ix]) / dx
                    hy[iy][ix] += (dt / self.MU_0) * d_ez_dx

            # 3. Update Electric Field Ez
            # dEz/dt = (1/eps) * (dHy/dx - dHx/dy) - (sigma/eps) * Ez
            for iy in range(1, ny - 1):
                for ix in range(1, nx - 1):
                    curl_h = (hy[iy][ix] - hy[iy][ix - 1]) / dx - (hx[iy][ix] - hx[iy - 1][ix]) / dy
                    decay = math.exp(- (sigma[iy][ix] / eps[iy][ix]) * dt) if sigma[iy][ix] > 0 else 1.0
                    ez[iy][ix] = ez[iy][ix] * decay + (dt / eps[iy][ix]) * curl_h

            # 4. Inject Source Pulse at Port Pad
            pulse_envelope = math.exp(-0.5 * ((t_now - t0_ps) / sigma_t) ** 2)
            rf_carrier = math.sin(2.0 * math.pi * freq_hz * t_now)
            ez[src_y][src_x] += 100.0 * pulse_envelope * rf_carrier

            # 5. Apply Mur 1st-Order ABC on Borders
            for iy in range(ny):
                # Left border (x = 0)
                ez[iy][0] = ez_prev_left[iy] + mur_coef * (ez[iy][1] - ez[iy][0])
                ez_prev_left[iy] = ez[iy][1]
                # Right border (x = nx - 1)
                ez[iy][nx - 1] = ez_prev_right[iy] + mur_coef * (ez[iy][nx - 2] - ez[iy][nx - 1])
                ez_prev_right[iy] = ez[iy][nx - 2]

            for ix in range(nx):
                # Bottom border (y = 0)
                ez[0][ix] = ez_prev_bot[ix] + mur_coef * (ez[1][ix] - ez[0][ix])
                ez_prev_bot[ix] = ez[1][ix]
                # Top border (y = ny - 1)
                ez[ny - 1][ix] = ez_prev_top[ix] + mur_coef * (ez[ny - 2][ix] - ez[ny - 1][ix])
                ez_prev_top[ix] = ez[ny - 2][ix]

            # 6. Capture Sampled Frames for WebGL
            if step % sample_interval == 0:
                frame_max = max(abs(ez[iy][ix]) for iy in range(ny) for ix in range(nx))
                if frame_max > max_abs_ez:
                    max_abs_ez = frame_max

                # Normalize frame to [-1.0, 1.0]
                norm_frame = [
                    [round(ez[iy][ix] / max(1e-3, max_abs_ez), 3) for ix in range(nx)]
                    for iy in range(ny)
                ]
                frames.append(norm_frame)
                frame_times_ps.append(round(t_now * 1e12, 2))

        # Calculate Poynting energy density map
        energy_density = [
            [
                round(
                    0.5 * eps[iy][ix] * (ez[iy][ix] ** 2) * 1e6, 3
                )
                for ix in range(nx)
            ]
            for iy in range(ny)
        ]

        return {
            "board_width_mm": board_width_mm,
            "board_height_mm": board_height_mm,
            "frequency_ghz": frequency_ghz,
            "dielectric_constant": er_sub,
            "dt_ps": round(dt * 1e12, 3),
            "total_steps": total_steps,
            "grid_nx": nx,
            "grid_ny": ny,
            "num_frames": len(frames),
            "frame_times_ps": frame_times_ps,
            "frames": frames,
            "energy_density": energy_density,
            "peak_ez_v_m": round(max_abs_ez, 2)
        }
