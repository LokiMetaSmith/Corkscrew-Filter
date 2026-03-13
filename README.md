# OpenAuto-CFD: Universal Configuration-Driven CFD Optimizer

OpenAuto-CFD is a powerful "Software-Defined Engineering" framework designed for the autonomous generation, simulation, and optimization of 3D-printable fluid dynamics components. It creates a seamless loop integrating parametric Computer-Aided Design (OpenSCAD), Computational Fluid Dynamics (OpenFOAM), and Generative Artificial Intelligence (LLM) to perform automated searches of high-dimensional design spaces.

By leveraging a universal Configuration-Driven Architecture (via YAML Problem Definition files), OpenAuto-CFD is not tied to a single geometry. Instead, it allows users to specify parameter ranges, physics constraints, and optimization goals, enabling an AI "Virtual Engineer" to iteratively design, simulate, and refine models toward an optimal solution.

## Key Features

*   **Universal Configuration-Driven Architecture**: Define any parametric optimization problem via a single YAML file, decoupled from hardcoded logic.
*   **AI-Powered Design Optimization**: Utilizes an LLM (e.g., Google Gemini) acting as an engineer that uses Chain-of-Thought reasoning to evaluate CFD results and propose logical geometric adjustments.
*   **Physics-Informed Agents**: The AI is prompted with the governing physics equations and makes decisions based on multivariable trade-offs (e.g., maximizing separation efficiency while minimizing pressure drop).
*   **Automated CFD Pipeline**: Robustly drives OpenFOAM meshing (`blockMesh`, `snappyHexMesh`) and solving directly from generated STL files.
*   **Multimodal Feedback**: The agent analyzes both numerical metrics and 3D renderings of the generated geometry to detect visual defects that might cause printability or flow issues.

---

## Case Study: Parametric Corkscrew Filter

To demonstrate the capabilities of OpenAuto-CFD, this repository includes a comprehensive system validation study: the **Parametric Corkscrew Filter**.

This is a 3D-printable inertial filter designed for separating particles from a fluid stream—ideal for challenging environments like mitigating abrasive lunar regolith.

### Theory of Operation

The corkscrew filter combines advanced fluid dynamics principles with the AI-driven engineering of OpenAuto-CFD.
See the [TECHNICAL_REPORT.md](./TECHNICAL_REPORT.md) for a detailed explanation of the physics and validation results.

#### Physics of Inertial Separation

The core mechanism of the corkscrew filter is **inertial separation**. As fluid traverses the helical channel, it is subjected to rapid changes in direction, inducing specific forces:

1.  **Centrifugal Force ($$F_c = m \frac{v^2}{r}$$)**: The helical geometry acts as a continuous centrifuge. Heavier particles possess greater inertia and are flung toward the outer wall of the channel.
2.  **Dean Vortices**: In curved pipes, the velocity differential creates secondary flows known as Dean Vortices that sweep the cross-section and transport particles toward trapping zones.
3.  **"Clog-Free" Trapping**: Unlike barrier filters (e.g., HEPA), this design uses "stepped traps" to eject particles *out* of the main flow stream into a quiescent collection bin. The filter maintains constant flow conductance until the bin is physically full.

## Getting Started

### 1. Install Dependencies

*   **Node.js**: Run `npm install` in the root directory to install geometry generation tools (`openscad-wasm`).
*   **Python**: Run `pip install -r optimizer/requirements.txt` to install the optimization and testing framework.

### 2. Generating the 3D Models (OpenSCAD)

The 3D models for the filter are generated using OpenSCAD.
1.  **Open the Main File**: Open the `corkscrew.scad` file in OpenSCAD (or use the CLI tools provided).
2.  **Configure Parameters**: Adjust the parameters in `config.scad` or the `parameters/` directory.
3.  **Render and Export**: Render the model (F6) and export it as an STL file for 3D printing.

#### Key Parameters (`corkscrew.scad`)
*   `filter_height_mm`: The height of the filter.
*   `number_of_complete_revolutions`: The number of turns in the corkscrew channels.
*   `screw_OD_mm`, `screw_ID_mm`: The outer and inner diameters of the corkscrew channels.
*   `num_screws`: The number of parallel corkscrew channels.
*   `num_bins`: The number of collection bins.

### 3. Automated Optimization & Parameters

The `optimizer/` directory contains tools to automate the design-simulation-analysis loop using the OpenAuto-CFD framework.
*   See [optimizer/README.md](./optimizer/README.md) for details on the AI-driven optimization workflow.
*   See [parameters/README.md](./parameters/README.md) for information on parameter configuration files.

> **Pro Tip:** When running the optimizer `main.py`, you can parallelize the meshing and CFD solver by using the `--cpus X` flag (where X is the number of cores). This makes OpenFOAM execute much faster!

### 4. CFD Simulation (Advanced)

This project includes a base case setup for running a CFD simulation using OpenFOAM. For detailed instructions on how to set up and run the simulation, please see the [README.md in the `corkscrewFilter` directory](./corkscrewFilter/README.md).

## Assembly

For a complete list of materials required and assembly instructions for the Corkscrew Filter validation study, please see the [Bill of Materials (BOM.md)](./BOM.md).

## Testing

To ensure the system is working correctly:
1.  **Geometry Regression**: Run `npm test` to verify that the OpenSCAD modules can generate STLs for all configuration files.
2.  **Unit Tests**: Run `PYTHONPATH=optimizer python3 -m pytest test/` to verify the optimization and simulation drivers.

## Future Work

For a list of planned enhancements and future work, please see the [TODO list (TODO.md)](./TODO.md).
