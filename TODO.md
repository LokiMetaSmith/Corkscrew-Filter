# Project To-Do List

This file tracks planned enhancements and future work for the Thirsty Corkscrew project.

- [x] Add the ability to make different parameter configurations based on included config files.
- [x] Refine the `CorkscrewSlitKnife` geometry to have a chamfered or ramped leading edge to improve separation efficiency.
- [ ] Conduct CFD analysis to test different design parameters (slit shape, screw pitch, etc.).
- [ ] Add particle tracking to the CFD simulation to visualize and quantify separation effectiveness.
- [x] Document `optimizer/` and `parameters/` directories in the README. These are core functions for simulation and parameter evaluation.
- [x] Complete refactor of barb generators into a unified, parameterized `Barb` module.
- [x] Create `FilterHolder` part (barb fitting with dual O-rings and optional threading).
- [x] Standardize legacy coupling configurations (Cartridge, Sandblaster) into `configs/` files.

## Distributed Optimization (Git-Based)
- [ ] **Data Schema:** Design a JSONL-based schema for the Job Queue/Result Log. This format should favor append-only operations to minimize merge conflicts when multiple users push results.
- [ ] **Job Manager:** Implement a `JobManager` class capable of:
    - "Checking out" a specific parameter region of interest.
    - Generating a local queue of jobs derived from that region.
    - Managing the state of claimed jobs.
- [ ] **Versioning Strategy:** Implement a hashing or UUID system to link specific job queues/results to the git commit hash of the codebase at the time of execution. This ensures reproducibility.
- [ ] **Agent "Campaign" Mode:** Update the `LLMAgent` to support generating batch "campaigns" (multiple parameter sets) into the queue, rather than single-step iterations.
- [ ] **Synchronization Workflow:** Create scripts/logic to handle the `pull` -> `claim` -> `run` -> `push` lifecycle, allowing a team to collaborate on the optimization surface asynchronously.
