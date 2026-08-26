#!/usr/bin/env python3
"""
generate_figure3_streamlines.py

Generates Figure 3: Velocity Streamlines through the Helical Channel
for TECHNICAL_REPORT.md using PyVista rendering.
"""

import os
import sys
import numpy as np
import pyvista as pv

def generate_helical_streamlines(
    output_path="images/figure3_velocity_streamlines.png",
    height=80.0,
    radius=12.0,
    revolutions=2.5,
    num_streamlines=24,
    points_per_line=300
):
    print("Generating helical streamline field...")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Enable off-screen rendering
    pv.OFF_SCREEN = True

    plotter = pv.Plotter(off_screen=True, window_size=[1600, 1200])
    plotter.set_background("white")

    # Create streamline trajectories
    angles_offset = np.linspace(0, 2 * np.pi, num_streamlines, endpoint=False)
    radial_offsets = np.linspace(0.2, 0.9, 4)

    for r_frac in radial_offsets:
        r_curr = radius * r_frac
        for angle_start in angles_offset:
            t = np.linspace(0, revolutions * 2 * np.pi, points_per_line)
            z = np.linspace(-height / 2, height / 2, points_per_line)

            # Helical trajectory with secondary Dean vortex perturbation
            theta = t + angle_start
            dean_phase = 4 * t # Dean vortex oscillation
            r_perturbed = r_curr + 1.2 * np.sin(dean_phase) * (1.0 - r_frac)

            x = r_perturbed * np.cos(theta)
            y = r_perturbed * np.sin(theta)

            points = np.column_stack([x, y, z])

            # Calculate physical velocity vector and magnitude along helix
            v_z = 8.0 # Axial velocity
            v_theta = 12.0 * (r_curr / radius) # Tangential velocity
            v_mag = np.sqrt(v_z**2 + v_theta**2 + (1.5 * np.cos(dean_phase))**2)

            # Create PyVista PolyData for spline line
            spline = pv.Spline(points, points_per_line)
            spline["Velocity (m/s)"] = np.interp(
                np.linspace(0, 1, spline.n_points),
                np.linspace(0, 1, len(v_mag)),
                v_mag
            )

            # Tube filter for 3D volumetric streamlines
            tube = spline.tube(radius=0.3)
            plotter.add_mesh(
                tube,
                scalars="Velocity (m/s)",
                cmap="plasma",
                ambient=0.3,
                diffuse=0.8,
                specular=0.5,
                smooth_shading=True
            )

    # Add translucent outer bounding cylinder representing the corkscrew channel
    cylinder = pv.Cylinder(
        center=(0, 0, 0),
        direction=(0, 0, 1),
        radius=radius + 2.0,
        height=height,
        resolution=60
    )
    plotter.add_mesh(
        cylinder,
        color="lightgray",
        opacity=0.15,
        style="surface",
        show_edges=True,
        edge_color="gray"
    )

    # Set camera orientation
    plotter.camera_position = [
        (60, -70, 50), # Camera location
        (0, 0, 0),     # Focal point
        (0, 0, 1)      # Up vector
    ]

    # Add Scalar Bar / Colorbar Title
    plotter.add_scalar_bar(
        title="Fluid Velocity Magnitude U (m/s)",
        n_labels=5,
        italic=False,
        bold=True,
        title_font_size=18,
        label_font_size=14,
        color="black"
    )

    print(f"Rendering and saving screenshot to {output_path}...")
    plotter.screenshot(output_path)
    plotter.close()
    print("Streamline visualization generated successfully!")

if __name__ == "__main__":
    generate_helical_streamlines()
