# Project To-Do List

This file tracks planned enhancements and future work for the Thirsty Corkscrew project.

- [x] Add the ability to make different parameter configurations based on included config files.
- [x] Refine the `CorkscrewSlitKnife` geometry to have a chamfered or ramped leading edge to improve separation efficiency.
- [x] Conduct CFD analysis to test different design parameters (slit shape, screw pitch, etc.) - *Enabled via new parameters in config.scad and optimizer/constraints.py*
- [x] Add particle tracking to the CFD simulation to visualize and quantify separation effectiveness.
- [x] Document `optimizer/` and `parameters/` directories in the README. These are core functions for simulation and parameter evaluation.
- [x] Complete refactor of barb generators into a unified, parameterized `Barb` module.
- [x] Create `FilterHolder` part (barb fitting with dual O-rings and optional threading).
- [x] Standardize legacy coupling configurations (Cartridge, Sandblaster) into `configs/` files.

## Distributed Optimization (Git-Based)
- [x] **Data Schema:** Design a JSONL-based schema for the Job Queue/Result Log. This format should favor append-only operations to minimize merge conflicts when multiple users push results.
- [x] **Job Manager:** Implement a `JobManager` class capable of:
    - "Checking out" a specific parameter region of interest.
    - Generating a local queue of jobs derived from that region.
    - Managing the state of claimed jobs.
- [x] **Versioning Strategy:** Implement a hashing or UUID system to link specific job queues/results to the git commit hash of the codebase at the time of execution. This ensures reproducibility.
- [x] **Agent "Campaign" Mode:** Update the `LLMAgent` to support generating batch "campaigns" (multiple parameter sets) into the queue, rather than single-step iterations.
- [x] **Synchronization Workflow:** Create scripts/logic to handle the `pull` -> `claim` -> `run` -> `push` lifecycle, allowing a team to collaborate on the optimization surface asynchronously.
- [x] **CLI Region Support:** Updated `generate_campaign.py` to allow direct job generation for specific parameter regions (e.g., `--param key=min:max`) without requiring LLM assistance.

## Simulation Fidelity & Physics
- [x] **Re-enable Lagrangian Turbulence:** Remove the `_disable_turbulence` hack in `foam_driver.py`. Update `kinematicCloudProperties` to use `dispersionModel StochasticDispersionRAS;` to accurately model particle re-entrainment.
- [x] **Safeguard Wall Distances:** Add `postProcess -func wallDist` to the simulation pipeline immediately prior to particle tracking to prevent crashes when evaluating turbulent wall functions.
- [x] **Switch Integration Scheme:** Change the particle tracking integration scheme from `Euler` to `analytical` in `kinematicCloudProperties` to resolve the SIGFPE math explosion caused by explicit integration overshooting drag equilibrium on fine particles.

## Metric Extraction & Data Handling
- [x] **Implement `particleCollector`:** Inject `particleCollector` into the `cloudFunctions` dictionary to capture discrete particle fate data for individual trapping bins.
- [x] **Aggregate Patch Data:** Update `foam_driver.get_metrics()` to parse the `particleCollector` CSV/OBJ outputs. Aggregate the raw hit counts into LLM-friendly summary statistics (e.g., capture efficiency per bin).
- [x] **Ensure Face Flux (Phi):** Run `postProcess -func writePhi` automatically when preparing the transient `0` directory from steady-state results to ensure velocity interpolation works for all sub-models.

## Optimization Loop & Architecture
- [x] **Inter-Simulation Parallelization:** Refactor the optimization orchestrator (`main.py` / `worker.py`) to process LLM-generated parameter batches concurrently by spinning up multiple asynchronous OpenFOAM container instances, rather than evaluating one design at a time.
- [x] **Bug Fix:** Fixed parameter type handling in `JobManager` to correctly distinguish between ranges (tuples) and discrete choices (lists).

## Project Readiness & Review (Jan 2026)
- [x] **Comprehensive Review:** Conducted a full review of the codebase, documentation, and tests.
- [x] **Geometry Fixes:** Attempted to fix non-planar faces in `RampedKnifeShape` (triangulation) and added epsilon overlap to cutters to improve CSG stability.
- [x] **Test Reliability:** Increased timeouts for WASM-based tests (`test/regression.js` and `test/test_parameter_stls.py`) to prevent false failures on slower environments.
- [x] **Documentation:** Updated `README.md` with explicit installation/testing instructions and `TECHNICAL_REPORT.md` with notes on missing figures.
- [ ] **Geometry Stability:** Resolve persistent `CGAL error: precondition violation` in `single_cell_filter.scad` and `flat_end_screw.scad` when running in `openscad-wasm`. (Native OpenSCAD may work fine).
- [ ] **Visual Assets:** Generate and insert Figure 3 (Velocity Streamlines) into `TECHNICAL_REPORT.md` using ParaView.
