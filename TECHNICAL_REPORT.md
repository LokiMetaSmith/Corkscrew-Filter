# NASA Technical Memorandum: Analysis of Corkscrew Filter Autonomous Design Framework

**Date:** October 26, 2023
**Subject:** Technical Evaluation of the Parametric Corkscrew Filter Repository
**Target Audience:** Technical Review Board, Open Source Community

---

## Abstract

This report provides a comprehensive technical analysis of the "Corkscrew Filter" repository, a software-defined engineering project capable of autonomously designing, simulating, and optimizing inertial filtration devices. The system integrates three distinct technical domains: parametric Computer-Aided Design (CAD) using OpenSCAD (via WebAssembly), Computational Fluid Dynamics (CFD) using OpenFOAM, and Generative Artificial Intelligence (AI) using Large Language Models (LLMs). This evaluation focuses on the software architecture, physics simulation fidelity, and the efficacy of the agentic control loop. The analysis confirms the existence of a functional "Hardware-in-the-Loop" simulation pipeline where an AI agent iteratively modifies geometry based on physics feedback.

## 1. Introduction

The objective of the Corkscrew Filter project is to develop a modular, high-efficiency inertial filter system using a helical (corkscrew) geometry. The primary engineering challenge in inertial filtration is balancing **separation efficiency** (maximizing the removal of particulates) against **energy consumption** (minimizing pressure drop, $$\Delta P$$).

Traditional design methodologies rely on manual iteration and empirical testing. This project implements an **Inverse Design** methodology, where a central software controller generates geometry, validates it through virtual wind tunnel testing (CFD), and employs an AI agent to determine the optimal parameters for the subsequent iteration. Additionally, the integration of WebAssembly-based compilation enhances portability, allowing the system to operate in diverse computing environments.

## 2. Governing Physics and Theoretical Basis

The design of the corkscrew filter is grounded in the principles of inertial separation.

### 2.1. Fluid Dynamics
The simulation environment utilizes the **SIMPLE (Semi-Implicit Method for Pressure-Linked Equations)** algorithm to solve the steady-state, incompressible Navier-Stokes equations:

$$ \nabla \cdot \mathbf{U} = 0 $$
$$ \nabla \cdot (\mathbf{U} \mathbf{U}) - \nabla \cdot (\nu_{eff} \nabla \mathbf{U}) = -\nabla p $$

Where:
*   $$\mathbf{U}$$ is the velocity vector field.
*   $$p$$ is the kinematic pressure.
*   $$\nu_{eff}$$ is the effective kinematic viscosity (sum of molecular and turbulent viscosity).

### 2.2. Particle Separation Mechanics
The helical geometry induces a tangential velocity component ($$v_\theta$$). As the fluid traverses the helical path, particles suspended in the flow are subjected to a centrifugal force ($$F_c$$) directed radially outward:

$$ F_c = m_p \frac{v_\theta^2}{r} $$

Where:
*   $$m_p$$ is the mass of the particle.
*   $$v_\theta$$ is the tangential velocity, which is a function of the inlet velocity and the helix twist angle.
*   $$r$$ is the local radius of curvature (defined by the `helix_path_radius_mm` parameter).

**Design Implication:** Increasing the twist angle increases $$v_\theta$$, thereby increasing $$F_c$$ and separation efficiency. However, this simultaneously increases wall shear stress and turbulence, leading to a higher pressure drop ($$\Delta P$$). The optimization goal is to find the critical point where separation is sufficient without excessive energy penalty.

## 3. System Architecture

The system operates as a closed-loop feedback mechanism managed by a Python-based orchestrator (`optimizer/main.py`). The workflow proceeds as follows:

1.  **Generation:** The system utilizes a dual-mode generation pipeline. The primary engine is a Node.js script (`export.js`) leveraging `openscad-wasm` (OpenSCAD compiled to WebAssembly). This provides a portable, "headless" compilation capability that eliminates the need for a native OpenSCAD installation on the host machine. The `ScadDriver` orchestrates this process, maintaining a fallback capability to the native binary if available.
2.  **Meshing:** The `FoamDriver` processes the resulting STL into a hexahedral-dominant CFD mesh using `snappyHexMesh`.
3.  **Simulation:** The `simpleFoam` solver executes a steady-state flow simulation.
4.  **Feedback:** The `LLMAgent` analyzes the performance metrics against defined constraints and provides a new set of parameters via the Google Gemini API.

[Figure 1: System Architecture Diagram - Data Flow between OpenSCAD, OpenFOAM, and LLM Agent]

## 4. Subsystem Analysis: Parametric Modeling (OpenSCAD)

The geometric modeling is performed by OpenSCAD, a script-based CAD modeler. The codebase has evolved from a monolithic structure to a highly modular library.

### 4.1. Modularity and Structure
The system adopts a "Configuration-as-Code" architecture. The primary entry point, `corkscrew.scad`, acts as a dispatcher, but the execution logic is driven by the `configs/` directory.
*   **`config.scad`:** Defines the complete schema of design parameters with default values.
*   **`configs/*.scad`:** Each file represents a discrete build target (e.g., `modular_filter_assembly.scad`). These files inherit defaults from `config.scad`, apply specific parameter overrides, and then invoke the geometry generator. This structure facilitates batch processing and version-controlled configuration management.
*   **`modules/` Directory:** Encapsulates the core geometry logic (e.g., `core.scad` for the helix, `inlets.scad` for threading integration via `BOSL2`).

### 4.2. Geometric Optimization Features
A critical geometric parameter is the `helix_profile_scale_ratio`.
*   **Function:** This parameter scales the circular cross-section of the helix into an ellipse.
*   **Why it matters:** By stretching the profile, the design maximizes the cross-sectional area within the annular space between the inner core and outer tube. This reduces the hydraulic resistance (increasing hydraulic diameter) while maintaining the rotational path required for separation.

[Figure 2: Wireframe view of Helical Geometry generated by OpenSCAD]

### 4.3. Component Evolution
The design library has expanded to support rapid prototyping and standardized interconnects.
*   **FilterHolder Module:** This component facilitates the integration of the filter cartridge into existing piping systems. It features a dual-seal mechanism, capable of utilizing either an axial "Face Seal" or a traditional radial seal depending on the threading configuration. This versatility allows for airtight connections with both 3D-printed and off-the-shelf components.
*   **Unified Barb Module:** Hose retention geometry is now generated by a fully parameterized `Barb` module. This replaces legacy hardcoded functions with a "Christmas tree" profile generator that dynamically calculates barb count, swell diameter, and wall thickness to match specific hose flexibility requirements.

## 5. Subsystem Analysis: Computational Fluid Dynamics (OpenFOAM)

The simulation environment is built upon OpenFOAM v2406. The automation logic resides in `optimizer/foam_driver.py`.

### 5.1. Mesh Generation Strategy
Meshing helical geometries is notoriously difficult due to the complex curvature. The project employs `snappyHexMesh` with specific settings to ensure solution fidelity:

*   **Boundary Layer Resolution (`addLayers`):**
    *   **Setting:** `nSurfaceLayers 3`
    *   **Why it matters:** In helical flows, secondary flows (Dean vortices) are driven by wall interactions. Without adequate boundary layer resolution (prism layers), the simulation would inaccurate predict skin friction, leading to a significant error in the computed $$\Delta P$$.
*   **Surface Refinement:**
    *   **Setting:** `refinementSurfaces ... level (2 2)`
    *   **Why it matters:** High curvature requires a fine mesh to avoid "faceting," where the smooth curve is approximated by flat planes, which would artificially induce turbulence.

### 5.2. Instrumentation
The `FoamDriver` dynamically injects `functionObjects` (`surfaceFieldValue`) into the `controlDict`. This provides a robust, code-driven method to extract the area-averaged pressure at the inlet and outlet patches, automating the calculation of $$\Delta P$$.

[Figure 3: Velocity streamlines through the helical channel (OpenFOAM Output)]

## 6. Subsystem Analysis: Autonomous Optimization (AI Agent)

The `optimizer/llm_agent.py` module represents the cognitive layer of the system.

### 6.1. Agent Implementation
The agent utilizes the Google Generative AI SDK (`gemini-1.5-flash`). Unlike a traditional gradient-descent optimizer, the agent employs **Chain-of-Thought** reasoning.
*   **Context:** It receives the full history of runs and a set of natural language constraints.
*   **Reasoning:** The system prompts the model to "Analyze the history. Identify trends."
*   **Why it matters:** The design space is likely non-convex and discontinuous (e.g., changing the number of bins is a discrete step). A gradient-based solver might get stuck in local minima, whereas the LLM can "reason" its way out of a local trap by proposing a novel parameter combination based on the trend data.

## 7. Manual Fabrication and Evaluation

This section describes the manual fabrication and evaluation tests performed. In particular, we tested a 1/4" tube, a 3/4" tube, a single bin, a three bin, and a multi corkscrew configuration.

## 8. Legacy Code Evolution

A review of the `legacy/` directory (specifically `ThirstyCorkscrew.scad`) reveals significant architectural maturation.
*   **Monolithic vs. Modular:** The legacy code contained all logic in a single file, limiting scalability.
*   **Manual vs. Automated:** The legacy approach relied on manual boolean flags for debugging, whereas the current system is built for "headless" automated execution.

## 9. Conclusion and Recommendations

The Corkscrew Filter repository demonstrates a high Technology Readiness Level (TRL) for an automated design framework. It successfully bridges the gap between parametric CAD and high-fidelity CFD using modern AI orchestration.

### 9.1. Technical Recommendations for Improvement
1.  **Turbulence Model Verification:** Explicitly define the turbulence model (e.g., $$k-\omega$$ SST) to ensure the simulation accurately captures the rotational flow separation.
2.  **Convergence Criteria:** The `FoamDriver` currently runs for a fixed number of iterations. Implementing a residual-based stopping criterion (e.g., stop when residuals < $$10^{-4}$$) would optimize computational resource usage.
3.  **Parallel Execution:** The current optimization loop is sequential. Running multiple simulations in parallel would significantly accelerate the exploration of the high-dimensional parameter space.

### 9.2. Recent Improvements
The following recommendations from previous evaluations have been successfully implemented:
1.  **Repository Integrity:** The missing `corkscrewFilter/constant` directory has been restored, ensuring the OpenFOAM simulation case is fully defined with `transportProperties` and `turbulenceProperties`.
2.  **WASM Portability:** The generation pipeline has been migrated to `openscad-wasm`, decoupling the runtime environment from local binary dependencies.
3.  **Standardized Configuration:** A scalable "Configuration-as-Code" structure (`configs/`) has replaced ad-hoc variable modification, enabling reproducible batch generation.

---
*End of Document*
