# Thirsty Corkscrew

A 3D-printable inertial filter for separating particles from a fluid stream, based on Dr. John Graf's "Thirsty Corkscrew" design. This project includes the OpenSCAD models for generating the filter and instructions for running a CFD simulation to analyze its performance.

## Theory of Operation

This project combines advanced fluid dynamics principles with modern AI-driven engineering to optimize the design of inertial filters.

### Physics of Inertial Separation

The core mechanism of the Thirsty Corkscrew is **inertial separation**. As fluid traverses the helical channel, it is subjected to rapid changes in direction. This induces specific forces that separate particles based on mass and density:

1.  **Centrifugal Force ($$F_c = m \frac{v^2}{r}$$)**: The helical geometry acts as a continuous centrifuge. The curvature forces the fluid to accelerate radially. Heavier particles (like dust or water droplets) possess greater inertia and are flung toward the outer wall of the channel with a force proportional to the square of the velocity ($$v^2$$) and inversely proportional to the radius ($$r$$).
2.  **Dean Vortices**: In curved pipes, the velocity differential between the inner and outer walls creates secondary flows known as Dean Vortices. These counter-rotating vortices spiral down the channel, effectively sweeping the cross-section and transporting particles toward the trapping zones.
3.  **"Clog-Free" Trapping**: Unlike barrier filters (e.g., HEPA) that trap particles *in* the flow path (leading to pressure buildup), this design uses "stepped traps" or slits. Particles are ejected *out* of the main flow stream into a quiescent collection bin. Because the storage volume is decoupled from the flow path, the filter can accumulate significant amounts of debris without increasing the pressure drop, maintaining constant system performance until the bin is physically full.

### AI-Powered Design Optimization

The design of such a filter involves a complex trade-off between **separation efficiency** (maximizing particle capture) and **energy efficiency** (minimizing pressure drop). To solve this non-linear problem, we employ an autonomous **AI Agent**.

*   **Virtual Engineer**: The AI (Google Gemini) does not merely guess parameters. It acts as an engineer, analyzing the results of previous CFD simulations. It uses **Chain-of-Thought** reasoning to hypothesize why a design performed poorly (e.g., "The pressure drop is too high, likely due to the twist rate being too aggressive") and proposes logical adjustments.
*   **Physics-Informed**: The AI is explicitly prompted with the governing physics equations. It understands that increasing the helix radius will lower the centrifugal force, or that tightening the pitch will increase capture efficiency at the cost of higher backpressure.
*   **Multimodal Feedback**: The agent is not limited to numbers. It analyzes **3D renderings** of the generated geometry to detect visual defects—such as disconnected helical segments or unprintable wall thicknesses—that might not be immediately obvious from numerical simulation data alone.

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
