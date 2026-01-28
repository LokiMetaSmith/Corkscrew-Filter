# Parameter Configurations

This directory contains OpenSCAD parameter configuration files (`.scad`). These files define specific variable values that control the geometry of the Thirsty Corkscrew filter.

## How to Use

These files can be used in two ways:

1.  **Manual Loading**: You can include these files in your main OpenSCAD script or load them to view different configurations.
2.  **Automated Optimization**: The `optimizer/main.py` script can be configured to start with parameters defined in these files (or similar structures).

## Configuration Files

*   **`default_param.scad`**: Contains the baseline parameters and variable definitions. It includes comments explaining what each parameter does (e.g., `num_bins`, `screw_OD_mm`, `pitch_mm`).
*   **`One_Corkscrew_param.scad`**: Configuration for a single-channel filter.
*   **`Three_Corkscrews_param.scad`**: Configuration for a 3-channel filter.
*   **`TwentyOne_Corkscrews_param.scad`**: Configuration for a high-capacity 21-channel filter.

When creating new configurations, it is recommended to copy `default_param.scad` and modify the values as needed.
