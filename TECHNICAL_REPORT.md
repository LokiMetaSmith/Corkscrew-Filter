# NASA Technical Memorandum: Analysis of Corkscrew Filter Autonomous Design Framework

**Date:** October 26, 2023
**Subject:** Technical Evaluation of the Parametric Corkscrew Filter Repository
**Target Audience:** Technical Review Board, Open Source Community
**Author:** Lawrence Kincheloe

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

### 6.2. Multimodal Feedback Loop
A significant advancement in the current iteration is the integration of visual feedback. The optimization pipeline captures multi-view screenshots of the generated STL geometry and feeds them into the multimodal LLM (Gemini).
*   **Visual Defect Detection:** The agent can identify geometric failures—such as disconnected helical segments, wall thinning, or printability issues—that purely numerical CFD metrics (like pressure drop) might fail to capture or would misinterpret as "infinite resistance."
*   **Physics-Informed Prompting:** The system prompt has been refined to explicitly encode the governing physics ($$F_c = mv^2/r$$), instructing the agent to correlate visual features (e.g., "helix radius is too tight") with physical outcomes ("centrifugal force is high, but flow is choked").

## 7. Manual Fabrication and Evaluation

This section describes the manual fabrication and evaluation tests performed. In particular, we tested a 1/4" tube, a 3/4" tube, a single bin, a three bin, and a multi corkscrew configuration.

### 7.1. Experimental Run: October 30, 2025

**Caveats**

The confidence in the gram scale that was used in the experiment is low; an observed drift of 0.005g between measuring the same article was observed. There was also inadequate hose clamping at the barbs, and powdered sugar was observed puffing out of seams. Also, the nature of the powdered sugar left a residue on all surfaces it came in contact with. It is hard to estimate how much was lost to the environment, but an attempt was made.

This necessitated running a substantial amount of material through the system to achieve a convincing signal-to-noise ratio.

8.452g was initially used, and it is estimated that a non-measurable amount went into the corkscrew and filter. The backpressure based on the orifice size of the 3D printed hose adapter was large enough that most of the material escaped out the tops and sides of the sand blaster.

A funnel was used to directly load the tube, and a fluttering blast of air with long pre and post air blasts at 60psi were used to load a long length of tube as shown. This allowed for direct loading of the supply tube, but because of residue left inside the air blaster from previous runs, we can only report on the relative change in weight between runs. An unknown, but noticeable loss of powdered sugar was lost to the environment and test apparatus.

**Experimental Data**

*   **Corkscrew Configuration:**
    *   Initial weight: 13.206g
    *   Captured in corkscrew: 13.660g
    *   Difference (Pre/Post): 0.454g

*   **Trap Filter:**
    *   Initial weight: 41.566g
    *   Captured in trap filter: 41.591g
    *   Difference (Pre/Post): 0.025g

**Conclusion:** A ratio of **18.16 to 1** was calculated (Captured vs. Let Past).

### 7.2. Experimental Run: November 22, 2025

**Test Conditions**
*   Pressure: 1-7.5 psi (pressure regulator was not accurate at this level).

**Experimental Data**
*   **10 Micron Filter:**
    *   Pre-run weight: 41.575g
    *   Post-run weight: 41.666g
    *   Difference (Captured): 0.091g

*   **Corkscrew Filter:**
    *   Pre-run weight: 13.690g
    *   Post-run weight: 14.556g
    *   Difference (Captured): 0.866g

**Conclusion:**
(14.556 - 13.690) / (41.666 - 41.575) = 0.866 / 0.091
This results in a capture ratio of **9.736 : 1**.

### 7.3. Experimental Run: January 25, 2026

**Test Conditions**
*   **Material:** Cornstarch (4 Tablespoons initially in hopper).
*   **Pressure:** 0.04 PSI measured in 3/4" tube (used for estimating velocity). Compressor set to 30 psi (steady state) before gun opened; fluctuated 60-30 psi during pulsing.
*   **Agitation:** Agitated with mallet; tapping the gun followed by pulling the trigger proved most effective.

**Observations**
*   **10:33:** Gun opened and shaking began.
*   **10:35:** Agitated with mallet.
*   **10:37:** Experiment stopped.
*   **10:41 - 10:43:** Resumed with tapping.
*   **10:51:** Pressure fluctuation observed (60-30 psi) when trigger opened/pulsed. No noticeable change in regulator when pulsed with hammer.
*   **Failure Mode:** Corkscrew filter barb fitting broke at 10:53.

**Retention Analysis**
*   **Hopper:** Practically empty (2-3 tablespoons less than start).
*   **Gun:** Mostly empty (holds ~2 tablespoons).
*   **Post-Filter:** Less than 1 tsp found in the post-IF hose.

**Conclusion:**
The system appears to be less effective than the 1/4" version, likely due to the particulate filter catching significant fine particles.

### 7.4. Initial Tube Corkscrew Test

This test involved a non-optimal seal, as the O-ring geometry was not correct and print artifacts made it difficult to form a perfect seal. RTV silicone rubber was applied by hand to form a “good enough” seal.

**Notes:**
The outgoing air created a tight rotational vortex which kept the particles from coating the tube. A Dyson vacuum was used as the suction source. The slit didn’t capture particles as effectively as the other designs, but this was sized for larger particulates; a series of successively smaller baffles might produce better results. There were particles buffeted inside the tube. The clear tube made visual inspection of the airflow and dust-laden air possible. The geometry of the corkscrew may need to be further optimized. Being able to calculate the fluid flow should allow for optimal geometry generation. There’s the potential for machine learning parameter learning and auto parameter tuning.

**Conclusion:**
The pressure differential and accompanying speed definitely changed the ratio of captured material in the pre-filter vs the post-filter. We can conclude that the filter itself fundamentally works, but given the vastly different performance from the much larger vacuum filter, more work needs to be done to combine existing fluid flow theory with our parameterized 3D model.

### 7.5. Supplementary Materials

*   **Experimental Run 10/30/2025 Photo Album:** [https://photos.app.goo.gl/baQobViRN2EK12yL6](https://photos.app.goo.gl/baQobViRN2EK12yL6)
*   **Experimental Run 11/22/2025 Photo Album:** [https://photos.app.goo.gl/WuuFNhYvLVV2sVhG9](https://photos.app.goo.gl/WuuFNhYvLVV2sVhG9)
*   **Experimental Run 01/25/2026 Photo Album:** [https://photos.app.goo.gl/kphwWbPpzWjCYpaS9](https://photos.app.goo.gl/kphwWbPpzWjCYpaS9)

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

## Appendix A: Advanced Inertial Filtration Architectures for Microgravity and Lunar Environments

**A Comprehensive Analysis of Helical Channel "Corkscrew" Separators**

### Executive Summary

The exploration of the lunar surface presents a unique and formidable challenge to Environmental Control and Life Support Systems (ECLSS): the omnipresent, abrasive, and cohesive threat of lunar regolith. As humanity prepares for sustained presence on the Moon under the Artemis program, the limitations of terrestrial filtration paradigms—specifically their reliance on gravity and disposable barrier media—have become critically apparent. This report presents an exhaustive technical analysis of helical channel centrifugal filtration systems, colloquially known as "corkscrew filters," as a robust alternative for orientation-agnostic, clog-resistant particulate separation.
The analysis is grounded in a specific experimental investigation involving the pneumatic conveyance of powdered sugar—a fine particulate proxy—through a three-chamber helical geometry at varying pressures (60 psi versus 1–10 psi). These experiments serve as a microcosm for the broader fluid dynamic challenges inherent in inertial separation: the necessity of achieving critical Reynolds (Re) and Dean (De) numbers to initiate stable particle migration against stochastic turbulence.
This document serves as a foundational chapter for a larger body of work on centrifugal filtration. It synthesizes experimental data with advanced fluid dynamics theory, specifically focusing on the generation of Dean vortices within curved geometries. These secondary flows offer a mechanism to direct contaminants away from the clean flow path, effectively transitioning filtration from a "barrier" methodology (pore exclusion) to a "force-field" methodology (inertial sorting).
Furthermore, this report critically evaluates the physicochemical properties of powdered sugar as a simulant for lunar regolith. While sugar effectively mimics the aerodynamic diameter of the hazardous respirable dust fraction (<20 µm), significant divergences in bulk density and electrostatic behavior necessitate careful calibration of experimental results when extrapolating to lunar conditions. The analysis concludes with optimized design parameters for a lunar-dust-rated corkscrew filter, integrating features such as stepped contours for particle trapping, conductive materials for electrostatic dissipation, and regenerative purge mechanisms to ensure indefinite operational lifespans.

### A.1. Introduction: The Imperative for Clog-Resistant, Orientation-Agnostic Filtration

**A.1.1 The Failure Modes of Traditional Filtration in Space**

Human spaceflight has historically relied on High-Efficiency Particulate Air (HEPA) filters and barrier media to maintain cabin air quality. While these systems have proven effective in the controlled environments of the Space Shuttle and the International Space Station (ISS), they face catastrophic limitations in long-duration exploration missions, particularly those targeting the lunar surface. The fundamental operational premise of barrier filtration—trapping particles within a fibrous matrix—creates a finite lifespan defined by saturation. Once the matrix is loaded, the pressure drop across the filter rises exponentially, necessitating replacement. In a mission scenario such as a Mars transit or a lunar outpost, the logistics of resupplying disposable filter cartridges are prohibitive, consuming valuable launch mass and volume.
The primary failure mode in lunar environments is particulate loading. On the Moon, the environment is dominated by lunar regolith—a jagged, electrostatically charged dust that pervades all mechanical seals and habitable volumes. Unlike terrestrial dust, which is often rounded by weathering, lunar dust retains sharp, abrasive edges due to its formation via micrometeoroid bombardment.1 This ubiquitous, clinging dust caused a plethora of problems during the Apollo missions, compromising seals, abrading spacesuit fabrics, and posing significant health risks including "lunar dust hay fever." Standard HEPA filters, while capable of capturing these particles, would become clogged rapidly given the high concentration of dust anticipated in airlocks and suit preparation areas.2 The operational data from Apollo suggests that the dust's unique properties allow it to bypass standard mitigation techniques, necessitating a filtration approach that does not rely on a consumable media matrix.
The second critical failure mode is gravity dependence. Many terrestrial inertial separators, such as standard industrial cyclones, rely partially on gravity to settle the separated "dust cake" into a hopper. In microgravity (0g) or reduced gravity (1/6g on the Moon), these gravitational forces are effectively absent.3 A standard cyclone operating in microgravity faces the risk of re-entraining separated particles into the vortex finder if the centrifugal forces are not sufficient to substitute for gravitational settling. The distinct lack of a "down" vector means that separated particles do not naturally fall into a collection bin; they must be actively driven there by fluid forces. Consequently, any filtration system designed for the Moon must be "orientation agnostic," capable of functioning regardless of the spacecraft's attitude or the local gravity vector.4

**A.1.2 The "Corkscrew" Solution: Helical Inertial Filtration**

The "corkscrew filter," a technology notably advanced by NASA Johnson Space Center and IRPI, LLC, addresses these limitations through a multi-phase flow separation method.5 This technology represents a paradigm shift from barrier filtration to inertial separation. Unlike a barrier filter, which physically obstructs the flow to trap particles, a corkscrew filter structures the flow itself to fling particles into specific trapping zones. The design utilizes a helical flow path to generate continuous centrifugal force. This force acts as an "artificial gravity," driving denser phases (liquids or solids) toward the channel walls regardless of the spacecraft's orientation.6
The key innovation in these designs distinguishes them from simple coiled tubes. The "corkscrew" architecture often incorporates stepped contours or wicking walls that capture the separated material.5 As the aerosol traverses the helical path, the centrifugal force pushes the denser particles into these recessed traps. Once a particle enters the trap, it is shielded from the high-velocity main flow, preventing re-entrainment. This mechanism allows the filter to operate continuously without a rise in pressure drop, as the primary flow channel remains unobstructed even as the traps fill. This "clog-free" characteristic is paramount for life support systems that must operate for months or years without maintenance.7
The application of this technology extends beyond simple dust removal. The initial development of the corkscrew filter was driven by the need to separate liquid water from the cabin atmosphere following a fire event and the discharge of a water-based fire extinguisher.6 In such a scenario, the filter must handle a multi-phase mixture of gas, liquid water, and smoke particulates. The helical geometry proved capable of separating these phases by leveraging their density differences, sequestering the liquid into wicking materials while allowing the gas to pass through. This capability to handle "wet" filtration makes the corkscrew filter uniquely suited for the complex, unpredictable environment of a spacecraft emergency.

**A.1.3 Report Objectives**

This report aims to provide a comprehensive analysis of helical channel filtration, structured around the following objectives:
Deconstruct the Physics: To elucidate the complex fluid dynamics of helical flows, with a specific focus on the generation and manipulation of Dean vortices and their role in particle trapping.
Analyze Experimental Parameters: To rigorously evaluate the experimental conditions (60 psi vs. 1–10 psi) and explain the performance differentials observed with powdered sugar based on Reynolds and Dean number thresholds.
Evaluate Material Proxies: To critically assess the validity of using powdered sugar as a simulant for lunar regolith in filtration studies, accounting for differences in density, shape, and cohesion.
Design for the Moon: To propose optimized design parameters for a lunar-dust-rated corkscrew filter, addressing the unique challenges of regolith cohesion, electrostatic adhesion, and vacuum stability.

### A.2. Fluid Dynamics of Helical Channels: The Physics of Separation

To understand the operational mechanics of the corkscrew filter—and to interpret the stark difference in experimental results between 60 psi and 1–10 psi—one must delve into the fluid dynamics of curved pipes. The flow regime in a helical channel is fundamentally distinct from the Poiseuille flow observed in straight pipes due to the emergence of curvature-induced secondary flows. These secondary flows are not merely parasitic disturbances; they are the primary mechanism driving separation efficiency in helical inertial microfluidics.8

**A.2.1 The Dean Mechanism and Secondary Flows**

When a fluid flows through a curved channel, the interplay between centrifugal forces and pressure gradients creates a distinct secondary flow pattern. Fluid elements near the center of the channel, possessing higher velocity, experience a larger centrifugal force ($F_c \propto U^2/R$) than the slower-moving fluid near the channel walls. This force differential drives the core fluid outward toward the concave (outer) wall of the bend. To satisfy the conservation of mass (continuity), the fluid near the top and bottom walls must recirculate inward toward the convex (inner) wall to replace the displaced fluid.
This recirculation results in a pair of counter-rotating vortices known as Dean vortices.9 These vortices are superimposed on the primary axial flow, creating a double-helical streamline pattern for the fluid itself. The fluid spirals as it moves downstream, effectively sweeping the cross-section of the channel. The strength and stability of these vortices are characterized by the dimensionless Dean number ($De$):

$$De = Re \sqrt{\frac{D_h}{2R_c}}$$
Where:
$Re$ is the Reynolds number ($Re = \frac{\rho U D_h}{\mu}$), representing the ratio of inertial forces to viscous forces.
$D_h$ is the hydraulic diameter of the channel.
$R_c$ is the radius of curvature of the helix.
The separation efficiency of a corkscrew filter is critically dependent on $De$. The magnitude of the secondary flow velocity scales with the Dean number (approximately $U_{Dean} \sim De^2$).10 Below a critical Dean number, the secondary flows are too weak to transport particles effectively across the primary streamlines against the forces of Brownian motion and diffusion. This theoretical threshold explains the experimental divergence: at 60 psi, the velocity $U$ is high, yielding a high $Re$ and consequently a high $De$, which drives robust separation. At 1–10 psi, the $De$ likely falls below the threshold required to initiate stable inertial migration, resulting in poor or negligible separation.11

**A.2.2 Particle Migration Forces in Helical Geometries**

In a helical filter, a solid particle is subject to a complex balance of forces that dictates its trajectory. The "clog-free" nature of the device depends on these forces effectively dominating the particle's motion, ensuring it is directed toward the trapping zones rather than remaining entrained in the clean gas stream.

*   **Centrifugal Force (Primary Separation Force):** The dominant force driving separation in macro-scale helical filters is the centrifugal force generated by the primary flow curvature. This force acts radially outward, pushing denser particles toward the outer wall of the channel. The magnitude of this force is given by:

    $$F_{centrifugal} = (\rho_p - \rho_f) V_p \frac{U_\theta^2}{R}$$
    Where $\rho_p$ and $\rho_f$ are the densities of the particle and the fluid, respectively, $V_p$ is the particle volume, and $U_\theta$ is the tangential velocity of the fluid.
    **Implication for Operation:** Heavier particles (like powdered sugar or lunar regolith) are flung toward the outer wall. Crucially, this force is proportional to the square of the velocity ($U^2$). A reduction in pressure from 60 psi to 10 psi results in a significant decrease in flow velocity, which in turn causes a quadratic drop in the separation force. This physics confirms why the high-pressure run is essential for successful filtration; the low-pressure run simply does not generate sufficient g-forces to separate the solid phase from the gas phase.12

*   **Dean Drag Force:** The secondary Dean vortices exert a viscous drag force on the particles, pulling them laterally across the channel cross-section. This force is described by Stokes' drag law tailored for the transverse velocity field:

    $$F_{Dean} = 3 \pi \mu d_p U_{Dean}$$
    Where $U_{Dean}$ is the transverse velocity of the Dean vortices.10
    **Implication for Fine Particles:** For very small particles (typically <10 µm), the Dean drag force can rival or even exceed the centrifugal force. Dean vortices can entrain these fine particles and circulate them within the vortices, potentially trapping them in the vortex cores or remixing them if the filter geometry isn't tuned. However, in optimized designs, Dean vortices effectively "sweep" particles toward specific equilibrium positions. In microfluidic applications, this effect is used to focus particles into tight bands, allowing them to be "skimmed" off into separate outlets.8

*   **Inertial Lift Forces:** Close to the channel walls, particles experience inertial lift forces arising from the shear gradient of the fluid flow. The shear-gradient lift force pushes particles toward the channel walls, where the shear rate is highest. Conversely, the wall-induced lift force repels particles away from the wall due to the pressure buildup between the particle and the boundary.
    **Net Effect:** In helical channels, the interplay of Dean drag and inertial lift forces creates stable equilibrium positions. At high Reynolds numbers (Re > 50), these forces act to focus particles into distinct streamlines. This phenomenon is exploited in "inertial microfluidics" to separate particles based on size, as the equilibrium position is size-dependent.11 For the corkscrew filter, these lift forces help keep larger particles moving along the wall (where the traps are located) while preventing them from becoming re-entrained in the center of the channel.

**A.2.3 The "Clog-Free" Dynamic**

The design requirement for a filter that "cannot be clogged" implies a system where particles are continuously removed or stored in a "dead zone" that does not impede the primary flow path. In barrier filters, the particles become the obstruction. In the corkscrew filter, the particles are moved out of the flow.
In the NASA/IRPI Corkscrew Filter, this is achieved via stepped contours or helical baffles.5
*   **Separation Mechanism:** The centrifugal force drives particles to the outer wall.
*   **Trapping Mechanism:** The outer wall is not a smooth arc; it contains a recessed step, a gutter, or a wicking (porous) layer. Once a particle crosses the streamline into this recessed zone, it enters a region of low velocity. The step shields the particle from the high-shear main flow, preventing re-entrainment.
*   **Prevention of Clogging:** Because the particles are sequestered in a recess (or "trap") while the main gas flow continues down the center of the channel, the pressure drop remains constant until the trap is physically 100% full. Unlike a HEPA filter, which begins to choke flow as soon as surface coverage begins, the corkscrew filter maintains 100% flow conductance even as it loads. The capacity of the filter is defined by the volume of these gutters, not by the surface area of a media. This geometric decoupling of "flow path" and "storage volume" is the essence of its clog-free performance.

### A.3. Experimental Analysis: The Powdered Sugar Proxy

The experimental setup employs powdered sugar as a test medium to evaluate the corkscrew filter's performance. To draw meaningful conclusions for space applications, it is essential to analyze the validity of this proxy and interpret the pressure-dependent results through the lens of fluid mechanics.

**A.3.1 Physicochemical Comparison: Sugar vs. Lunar Regolith**

To validate the experimental results, we must rigorously compare the physical properties of powdered sugar to the target contaminant: lunar dust (regolith).

**Table 1: Comparative Properties of Powdered Sugar and Lunar Regolith Simulants**

| Property | Powdered Sugar (Confectioners) | Lunar Regolith (Simulant JSC-1A / Highland) | Implication for Filtration |
| :--- | :--- | :--- | :--- |
| **Particle Size (D50)** | ~10–15 µm [14] | 40–130 µm (bulk), <20 µm dust fraction is critical [15] | Sugar is an excellent size proxy for the hazardous "respirable" fraction of lunar dust. |
| **Particle Size (D90)** | ~40–50 µm [14] | ~500 µm (coarse fraction included) [17] | Sugar lacks the coarse grit of raw regolith, meaning it tests the hardest filtration case (fines). |
| **Bulk Density (Loose)** | ~0.56 g/cm³ [18] | ~1.50 g/cm³ [19] | **Critical Divergence.** Regolith is ~3x denser. Centrifugal separation will be easier with regolith than sugar for the same size. |
| **Particle Shape** | Crystalline, semi-regular | Angular, jagged, agglutinates (glassy) [19] | Regolith is more abrasive and prone to mechanical interlocking (clogging). |
| **Cohesion** | High (hygroscopic clumping) | High (electrostatic + vacuum adhesion) [3] | Both are cohesive, but mechanisms differ. Sugar clumps due to moisture; regolith due to electrostatics. |

**Insight:** The use of powdered sugar represents a conservative test for centrifugal separation efficiency. Centrifugal force is directly proportional to the density difference between the particle and the fluid ($F \propto \rho_p - \rho_f$). Since sugar (approx. 1.6 g/cm³ particle density, 0.56 g/cm³ bulk density) is significantly less dense than lunar regolith (approx. 2.9 g/cm³ particle density, 1.5 g/cm³ bulk density), the forces acting on a sugar particle will be weaker than those on a regolith particle of the same size. Therefore, a filter geometry that successfully separates powdered sugar will almost certainly separate lunar dust even more effectively. However, the hygroscopic nature of sugar may lead to "caking" in the traps that mimics the cohesive behavior of lunar dust, albeit through a moisture-driven mechanism rather than the electrostatic mechanism prevalent on the Moon.

**A.3.2 Analysis of the "60 psi" vs "1-10 psi" Runs**

Experimental runs were conducted at two distinct pressure regimes: 60 psi and 1–10 psi. The vast difference in outcome between these two conditions is physically deterministic and aligns with the theoretical constraints of inertial separation.

*   **High Pressure (60 psi) - The Inertial Regime**
    *   At 60 psi, the air velocity within the filter assembly (assuming a standard hose diameter of 0.25" to 0.5") is substantial, likely reaching highly turbulent flow conditions.
    *   **Reynolds Number:** High velocity ($U$) implies a high Reynolds number ($Re > 4000$).
    *   **Separation Physics:** As noted in the literature, particle separation efficiency in helical channels peaks at Re > 50–100.11 At these Reynolds numbers, the inertial lift forces (which scale with $Re^2$) and centrifugal forces are maximized.
    *   **Result:** The 60 psi run likely generated strong, stable Dean vortices and sufficient centrifugal force to fling the sugar particles to the channel walls. If the hose had any curvature (coiling) and the filter included trapping features, the sugar would have stratified rapidly, explaining the successful collection.

*   **Low Pressure (1-10 psi) - The Diffusive/Laminar Regime**
    *   At 1–10 psi, the flow velocity is drastically reduced, likely by an order of magnitude or more compared to the 60 psi case.
    *   **Reynolds Number:** The Reynolds number drops significantly, potentially into the laminar or transitional regime.
    *   **Separation Physics:** Below a critical Re, inertial migration forces become negligible compared to viscous drag. The particles tend to follow the fluid streamlines (Stokes regime) rather than crossing them to reach the walls.21 The Dean vortices, if present, are weak and unable to transport particles effectively against diffusion.
    *   **Result:** The sugar likely remained entrained in the airflow, behaving as a tracer rather than a separated phase. This confirms that corkscrew filters are velocity-dependent devices. They require a minimum flow rate (critical velocity) to "switch on" the separation physics.

*   **The "Hose" Factor**
    *   The experiment involved "filling a hose" with sugar. In a flexible hose, the radius of curvature ($R_c$) is variable and potentially large.
    *   **Torsion and Helicity:** If the hose was coiled, it acted as a helical channel. However, if the coiling radius was too large (large $R_c$), the centrifugal force ($U^2/R_c$) would diminish.
    *   **Roughness and Trapping:** Standard hoses are smooth-walled. The NASA corkscrew filter relies on stepped contours.5 In a smooth hose, sugar might be flung to the wall by centrifugal force but then simply slide along the wall and re-entrain at the outlet due to shear flow. Without a physical trap (wicking material or a step), separation in a smooth hose is temporary and unstable.

### A.4. The Design of the "Corkscrew" Filter: Anatomy of a Clog-Free System

The "corkscrew filter" is not merely a coiled tube; it is a precision-engineered multiphase separator designed to handle complex mixtures of gas, liquid, and solids. Based on the NASA/IRPI patents and technical descriptions [5], the design consists of three critical subsystems that work in concert to achieve high efficiency and clog resistance.

**A.4.1 The Helical Flow Path (The Accelerator)**

The core of the filter is a multi-channel helix. Unlike a single spiral tube, these filters often employ multiple parallel helical channels (a "multi-start" helix) to maximize the surface area available for separation and increase throughput while maintaining a small hydraulic diameter ($D_h$).
*   **Function:** The primary function of the helix is to accelerate the aerosol and generate sustained g-forces.
*   **Design Constraint:** The pitch and radius of the helix must be constant to maintain stable Dean vortices. Variable curvature can lead to vortex breakdown and remixing of the separated phases.11 The curvature induces the secondary flows that sweep the channel cross-section, moving particles towards the trapping zones.

**A.4.2 The Stepped Contour (The Trap)**

This is the defining feature that allows for "clog-free" operation and distinguishes the corkscrew filter from simple inertial separators.
*   **Geometry:** The outer wall of the helical channel is not a smooth arc. Instead, it features a "step," "gutter," or "recess" that is set back from the main flow path.
*   **Mechanism:** Centrifugal force drives particles radially outward. As they migrate to the outer wall, they cross the streamline that divides the main flow from the recessed trap. Once inside the gutter, the boundary layer velocity is significantly lower. The step acts as a shield, protecting the trapped particles from the high-shear main flow.
*   **Clogging Resistance:** Because the main flow path remains unobstructed, the pressure drop across the filter does not rise as the traps fill. The capacity of the filter is limited only by the volume of these gutters. Even as the gutters fill with dust, the gas continues to flow unimpeded down the center of the channel.

**A.4.3 The Wicking/Porous Wall (Phase Separation)**

In the original NASA application for separating liquid water (from fire extinguishers), the trap walls were lined with a hydrophilic wicking material.7
*   **Mechanism:** Liquid droplets impinging on the wall wet the surface and are wicked away by capillary action into a storage reservoir. This effectively separates the liquid phase from the gas phase.
*   **Solid Application:** For solid particulates like lunar dust, the wicking material might be replaced by a porous metal sinter or a magnetic trap (leveraging the iron content of regolith). A porous wall allows a small amount of gas to bleed off through the trap, creating a net flow vector into the trap that helps retain the solids.12 This "bleed flow" effectively concentrates the dust cake against the wall.

**A.4.4 Comparison to Cyclones**

While sharing the fundamental principle of centrifugal separation, the corkscrew filter offers distinct advantages over standard cyclone separators for space applications:
*   **Residence Time:** The helical path is significantly longer than the body of a standard cyclone, providing a longer residence time for separation forces to act on the particles.22 This allows for the separation of finer particles than a cyclone of comparable diameter.
*   **Orientation Agnostic:** Cyclones typically rely on gravity to pull the separated "dust cone" down into the hopper. In microgravity, the dust can hover in the separation zone and be re-entrained. The corkscrew filter uses the flow's own momentum and the stepped trap geometry to sequester particles, making it fully functional in zero gravity.23

### A.5. Application: Lunar Regolith and Space Exploration

The ultimate goal is to apply this filtration technology to the challenge of moon dust. This application introduces extreme environmental variables—specifically abrasion, electrostatics, and vacuum—that the powdered sugar experiment does not capture.

**A.5.1 The Lunar Dust Threat**

Lunar dust is widely recognized as one of the primary hazards to lunar exploration. Its properties are uniquely challenging:
*   **Abrasive:** Formed by continuous micrometeoroid bombardment, lunar dust particles are jagged shards of glass and agglutinates. They act like microscopic knives, shredding soft materials such as seals and fabrics.1
*   **Electrostatic:** The lunar surface is exposed to the solar wind and UV radiation, which charge the dust particles. This "triboelectric charging" causes the dust to cling tenaciously to surfaces, making it difficult to remove mechanically.24
*   **Respiring Hazard:** The fine fraction (<20 µm) is particularly dangerous as it can settle deep in the lungs, posing long-term health risks to astronauts.

**A.5.2 Electrostatic Challenges in Inertial Filtration**

In a helical filter, triboelectric charging can be a significant complicating factor.
*   **The Problem:** The high-velocity transport of dielectric dust (regolith) through dielectric channels (plastic or polymer 3D prints) generates massive static charges due to contact electrification. The dust may adhere to the channel walls before reaching the trap, or clump together in unpredictable ways. This adhesion can alter the effective geometry of the channel, potentially leading to clogging or flow disruption.
*   **The Solution:** The filter walls must be made of conductive materials and grounded to dissipate charge. Alternatively, electrostatic precipitation principles can be integrated into the design. By applying a voltage to the helical walls, the separation efficiency for the finest particles (which are the hardest to separate inertially) can be boosted.26 The helical channel can act as a long electrostatic precipitator, attracting charged dust particles to the walls.

**A.5.3 Simulant Fidelity: JSC-1A vs. Sugar**

While sugar was employed for initial testing, future validation must transition to high-fidelity lunar simulants.
*   **JSC-1A:** This is a standard mare simulant with a basaltic composition that replicates the density, chemical composition, and abrasiveness of Moon dust.19
*   **Density Factor:** As noted in 27, simulants like OB-1A and JSC-1A have particle densities of ~2.9 g/cm³ and bulk densities of ~1.5–1.7 g/cm³. This density difference is critical for inertial separation calculations.
*   **Calculation:** The centrifugal force on a regolith particle ($F_{regolith}$) compared to a sugar particle ($F_{sugar}$) of the same size is approximately:
    $$ \frac{F_{regolith}}{F_{sugar}} = \frac{\rho_{regolith} - \rho_{air}}{\rho_{sugar} - \rho_{air}} \approx \frac{2.9}{0.56} \approx 5.1 $$
*   **Conclusion:** A corkscrew filter that is optimized for sugar will be 5 times more effective (in terms of force magnitude) when separating lunar regolith. The successful separation of sugar at 60 psi is therefore a very positive indicator for the system's potential performance with lunar dust.

**A.5.4 "Filtration That Cannot Be Clogged"**

For a permanent lunar outpost, "cannot be clogged" implies a system that is regenerative. A trap that fills up is eventually a clog.
*   **The Scroll Filter Concept:** NASA Glenn has developed systems where the "trap" media is a scroll that can be advanced to a clean section automatically.28
*   **The Corkscrew Adaptation:** The helical traps could be designed with a "bleed" flow or an active purge. A small fraction of the air (5–10%) could continuously flush the trapped dust into a high-density storage bag or a vacuum port. This "active purge" would render the filter truly non-clogging, as the traps would never reach capacity.29

### A.6. Comparative Performance Analysis

**Table 2: Technology Comparison for Space Filtration**

| Feature | Corkscrew Filter (Helical) | Conventional Cyclone | HEPA / Barrier Filter | Electrostatic Precipitator |
| :--- | :--- | :--- | :--- | :--- |
| **Separation Principle** | Centrifugal + Dean Vortices | Centrifugal + Gravity | Physical Interception | Electrostatic Attraction |
| **Pressure Drop** | Low, Constant [30] | Moderate to High | Increases w/ Loading | Low |
| **Clog Resistance** | High (Open Channel) | Moderate (Outlet clogging) | Low (Pore blocking) | High (Plate cleaning needed) |
| **Gravity Dependence** | None (Orientation Agnostic) | High (typ. uses gravity) | None | None |
| **Cut-Point (Efficiency)** | High for >2 µm [31] | High for >5–10 µm [32] | High for >0.3 µm | High for <1 µm |
| **Lunar Dust Suitability** | Excellent (Pre-filter) | Good (Pre-filter) | Poor (Primary) / Good (Final) | Excellent (Fine fraction) |
| **Maintenance** | Passive / Regenerative | Passive / Hopper Emptying | Consumable Replacement | Plate Cleaning |

**Key Insight:** The corkscrew filter sits in the "sweet spot" as a pre-filter. It protects the HEPA filter. A standalone HEPA filter on the Moon would clog in hours due to the high dust load. A corkscrew filter upstream removes 90–95% of the mass (the coarse and medium dust), allowing the HEPA to function for months or years handling only the sub-micron fines.28

### A.7. Second and Third-Order Insights

**A.7.1 The Thermodynamics of Compression**

The 60 psi experiment introduces a thermodynamic variable that may have influenced the results. Compressing air to 60 psi heats it. Expanding it through a nozzle or filter cools it rapidly.
*   **Moisture Risk:** If the compressed air used in the experiment contained humidity (typical of Earth air), the rapid expansion in the filter could condense water vapor. Powdered sugar is highly hygroscopic.
*   **Risk:** The "clogging" or "caking" observed in low-pressure runs (or potentially in high-pressure runs if not careful) might not be purely mechanical, but chemical—the formation of sugar syrup or cement in the channels due to moisture.
*   **Space Context:** Lunar air is dry, but cabin air has humidity. The "wicking" walls of the NASA design are specifically intended to handle this condensation/liquid phase.5 This feature turns a potential failure mode (condensation) into a functional capability (humidity control), allowing the filter to manage both dust and excess moisture.

**A.7.2 Acoustophoretic Hybridization**

The literature suggests that helical channels are often combined with acoustophoretic separation (sound waves) in microfluidic applications.11
*   **Future Insight:** For a lunar base, combining a corkscrew filter with ultrasonic transducers could create a "solid-state" filter with no moving parts that separates particles based on compressibility as well as density. This hybrid approach could help separate biological contaminants (skin flakes) from regolith, which is useful for recycling resources and characterizing the cabin environment.

**A.7.3 The "Dean Drag" Limit**

There is a theoretical limit to corkscrew filtration efficiency for ultrafine particles. As particles get smaller (<1 µm), the Dean drag forces (recirculation) begin to overpower the centrifugal forces.
*   **Implication:** The corkscrew filter cannot be the only filter in a life support system. It must be part of a series architecture: Corkscrew (Bulk Removal) -> Electrostatic (Fines) -> HEPA (Polishing). The goal of a single "uncloggable" filter is achievable for bulk dust removal, but not for sterilization grade air quality. The system must be viewed as a bulk separator that enables the longevity of the finer polishing filters.

### A.8. Recommendations for the Final Report

Based on this analysis, the following recommendations are made for the final report and design iteration:
1.  **Adopt the "Stepped" Geometry:** The "hose" experiment likely lacked the precision stepped traps of the NASA design. Future prototypes should use 3D-printed helical inserts with defined particle traps (gutters) to prevent re-entrainment and ensure true clog-free performance.
2.  **Maintain High Reynolds Number:** The experimental data confirms that high pressure (high velocity) is non-negotiable for this scale of device. For space applications, this implies the filter should be placed on the high-pressure side of circulation fans or compressors, rather than the suction side, to ensure sufficient $De$.
3.  **Transition to Dense Simulants:** Move from sugar to a sand or regolith simulant (like JSC-1A or even fine silica sand) to better model the density-driven separation forces. This will provide more realistic efficiency data for lunar applications.
4.  **Integrate Conductive Materials:** To address the electrostatic adhesion of lunar dust, the filter body should be printed in conductive PLA or machined aluminum and grounded. This will prevent static buildup and potential clogging due to triboelectric charging.
5.  **Focus on "Regenerative" Traps:** Design the trap sections to be purgeable. A simple valve that opens to vacuum (space environment) or a secondary collection bag could instantly suck the trapped dust out of the filter, cleaning it without disassembly.

### A.9. Conclusion

The "corkscrew" helical channel filter represents a robust, gravity-independent solution to the problem of particulate filtration in space exploration. The experiment with powdered sugar effectively demonstrates the fundamental dependency of this technology on inertial velocity (pressure). While 1–10 psi flows fail to generate the necessary Dean vortices and centrifugal forces for separation, 60 psi flows successfully activate the inertial separation regime.
For lunar applications, the corkscrew filter offers a critical advantage: the ability to separate the abrasive, dense bulk of lunar regolith without the clogging inevitable with barrier filters. By refining the geometry to include stepped traps and leveraging the high density of regolith, this technology can serve as the primary defense line in Environmental Control and Life Support Systems (ECLSS) for the Artemis generation of lunar habitats.

### A.10. Works Cited

1.  dust mitigation: lunar air filtration with a permanent-magnet system (laf-pms), accessed November 23, 2025, https://www.lpi.usra.edu/meetings/lpsc2007/pdf/1654.pdf
2.  HEPA Filter Testing for Life Support Systems on Artemis Lunar Missions, accessed November 23, 2025, https://ttu-ir.tdl.org/bitstreams/01236268-2dc8-46ab-a3fe-6d9d5cbd9797/download
3.  Effects of gravity on cohesive behavior of fine powders: Implications for processing Lunar regolith - ResearchGate, accessed November 23, 2025, https://www.researchgate.net/publication/225955959_Effects_of_gravity_on_cohesive_behavior_of_fine_powders_Implications_for_processing_Lunar_regolith
4.  How do you properly orient your filters? Explore our Filters Guide - Idex-hs.com, accessed November 23, 2025, https://www.idex-hs.com/news-events/stories-and-features/detail/orientation-of-filters
5.  Corkscrew Filter Extracts Liquid From Air Charge - NASA Technology Transfer Program, accessed November 23, 2025, https://technology.nasa.gov/patent/MSC-TOPS-118
6.  Corkscrew Filter Extracts Liquid from Air Charge - Tech Briefs, accessed November 23, 2025, https://www.techbriefs.com/component/content/article/49236-msc-tops-118
7.  filtration - NASA Technology Transfer Program, accessed November 23, 2025, https://technology.nasa.gov/tags/filtration
8.  The Physics and Manipulation of Dean Vortices in Single- and Two-Phase Flow in Curved Microchannels: A Review - PMC, accessed November 23, 2025, https://pmc.ncbi.nlm.nih.gov/articles/PMC10745399/
9.  Numerical investigation of Dean vortex evolution in turbulent flow through 90° pipe bends, accessed November 23, 2025, https://www.frontiersin.org/journals/mechanical-engineering/articles/10.3389/fmech.2025.1405148/full
10. Enhancing particle focusing: a comparative experimental study of modified square wave and square wave microchannels in lift and Dean vortex regimes - PubMed Central, accessed November 23, 2025, https://pmc.ncbi.nlm.nih.gov/articles/PMC10834497/
11. Lab on a rod: Size-based particle separation and sorting in a helical channel - PMC, accessed November 23, 2025, https://pmc.ncbi.nlm.nih.gov/articles/PMC7661098/
12. A Novel Centrifugal Filtration Device - MDPI, accessed November 23, 2025, https://www.mdpi.com/2297-8739/9/5/129
13. In a curved channel two counter rotating Dean vortices (secondary flow)... - ResearchGate, accessed November 23, 2025, https://www.researchgate.net/figure/n-a-curved-channel-two-counter-rotating-Dean-vortices-secondary-flow-develop_fig1_233951453
14. Size Matters: Crystal Size Analysis for the Louisiana Sugar Industry - LSU AgCenter, accessed November 23, 2025, https://www.lsuagcenter.com/profiles/lbenedict/articles/page1491324916020
15. An Engineering Guide to Lunar Geotechnical Properties - NASA Technical Reports Server, accessed November 23, 2025, https://ntrs.nasa.gov/api/citations/20220014634/downloads/Final%20IEEE%20paper%20formatted%20footnote%20added.pdf
16. Characterizing Detailed Grain Shape and Size Distribution Properties of Lunar Regolith, accessed November 23, 2025, https://ntrs.nasa.gov/citations/20210026714
17. Particle Size Distribution of Lunar Soil - ResearchGate, accessed November 23, 2025, https://www.researchgate.net/publication/271358087_Particle_Size_Distribution_of_Lunar_Soil
18. Bulk Density Guide – Understanding Material Weight & Flow, accessed November 23, 2025, https://www.bpsvibes.com/bulk-density-guide
19. Exploration Science Projects | Lunar Regolith Simulants | JSC-1/1A - NASA • ARES, accessed November 23, 2025, https://ares.jsc.nasa.gov/projects/simulants/jsc-1-1a.html
20. 2021 Lunar Simulant Assessment, accessed November 23, 2025, https://lsic.jhuapl.edu/Our-Work/Working-Groups/files/Lunar-Simulants/2021%20Lunar%20Simulant%20Assessment_final.pdf
21. Continuous inertial focusing, ordering, and separation of particles in microchannels - PNAS, accessed November 23, 2025, https://www.pnas.org/doi/10.1073/pnas.0704958104
22. Computational and Experimental Analysis of Axial Flow Cyclone Used for Intake Air Filtration in Internal Combustion Engines - MDPI, accessed November 23, 2025, https://www.mdpi.com/1996-1073/14/8/2285
23. Simulation of Helical-Baffle Inlet Structure Cyclone Separator - MDPI, accessed November 23, 2025, https://www.mdpi.com/2297-8739/12/6/166
24. Lunar Dust Mitigation: A Guide and Reference - NASA Technical Reports Server, accessed November 23, 2025, https://ntrs.nasa.gov/api/citations/20220018746/downloads/TP-20220018746.pdf
25. Modeling of electrostatic and contact interaction between low-velocity lunar dust and spacecraft | EurekAlert!, accessed November 23, 2025, https://www.eurekalert.org/news-releases/1106261
26. Forced Triboelectrification of Fine Powders in Particle Wall Collisions - Publikationsserver der TU Clausthal, accessed November 23, 2025, https://dokumente.ub.tu-clausthal.de/servlets/MCRFileNodeServlet/clausthal_derivate_00001854/minerals-12-00132.pdf
27. 2022 Lunar Simulant Assessment, accessed November 23, 2025, https://lsic.jhuapl.edu/Our-Work/Working-Groups/files/Lunar-Simulants/2022%20Lunar%20Simulants%20Assessment%20Final.pdf
28. Multi-Stage Filtration System | T2 Portal - NASA Technology Transfer Program, accessed November 23, 2025, https://technology.nasa.gov/patent/lew-tops-93
29. Fine particle removal from gas stream using a helical-duct dust concentrator: Numerical study | Request PDF - ResearchGate, accessed November 23, 2025, https://www.researchgate.net/publication/333605900_Fine_particle_removal_from_gas_stream_using_a_helical-duct_dust_concentrator_Numerical_study
30. Additively manufactured multiplexed inertial coalescence filters (Journal Article) | OSTI.GOV, accessed November 23, 2025, https://www.osti.gov/pages/biblio/1981758
31. Effect of Inlet Air Volumetric Flow Rate on the Performance of a Two-Stage Cyclone Separator - PubMed Central, accessed November 23, 2025, https://pmc.ncbi.nlm.nih.gov/articles/PMC6644756/
32. Understanding Industrial Cyclone Separators: Engineered for Efficient Particle Removal, accessed November 23, 2025, https://www.cecoenviro.com/understanding-industrial-cyclone-separators-engineered-for-efficient-particle-removal/
33. Hydrodynamic mechanisms of cell and particle trapping in microfluidics - PubMed Central, accessed November 23, 2025, https://pmc.ncbi.nlm.nih.gov/articles/PMC3631262/

---
*End of Document*
