# Thirsty Corkscrew

A 3D-printable inertial filter for separating particles from a fluid stream, based on Dr. John Graf's "Thirsty Corkscrew" design. This project includes the OpenSCAD models for generating the filter and instructions for running a CFD simulation to analyze its performance.

## How it Works

The Thirsty Corkscrew uses the principle of inertial separation. As the fluid (e.g., air) flows through the corkscrew-shaped channels, its direction changes rapidly. Due to their inertia, heavier particles (e.g., dust, water droplets) cannot follow the sharp turns and are ejected through slits in the channel walls into a collection bin. The lighter fluid continues to flow through the channels.

## Getting Started: Generating the 3D Models

The 3D models for the filter are generated using OpenSCAD.

1.  **Install OpenSCAD**: If you don't have it already, download and install OpenSCAD from [openscad.org](https://openscad.org/).
2.  **Open the Main File**: Open the `ThirstyCorkscrew.scad` file in OpenSCAD.
3.  **Configure Parameters**: Adjust the parameters in the file to customize the filter to your needs. The most important parameters are located at the top of the file.
4.  **Render and Export**: Render the model (F6) and export it as an STL file for 3D printing.

### Key Parameters (`ThirstyCorkscrew.scad`)

*   `filter_height_mm`: The height of the filter.
*   `number_of_complete_revolutions`: The number of turns in the corkscrew channels.
*   `screw_OD_mm`, `screw_ID_mm`: The outer and inner diameters of the corkscrew channels.
*   `num_screws`: The number of parallel corkscrew channels.
*   `num_bins`: The number of collection bins.

## Assembly

For a complete list of materials required and assembly instructions, please see the [Bill of Materials (BOM.md)](./BOM.md).

## CFD Simulation (Advanced)

This project includes a case setup for running a CFD simulation using OpenFOAM to analyze the filter's performance. For detailed instructions on how to set up and run the simulation, please see the [README.md in the `corkscrewFilter` directory](./corkscrewFilter/README.md).

## Automated Optimization & Parameters

For those looking to optimize the filter design programmatically, the `optimizer/` directory contains tools to automate the design-simulation-analysis loop using Generative AI.
*   See [optimizer/README.md](./optimizer/README.md) for details on the AI-driven optimization workflow.
*   See [parameters/README.md](./parameters/README.md) for information on parameter configuration files.

## Future Work

For a list of planned enhancements and future work, please see the [TODO list (TODO.md)](./TODO.md).
