# OpenFOAM Case for Corkscrew Filter

This directory contains the necessary files to run a basic CFD simulation of the corkscrew filter using OpenFOAM. This guide summarizes the workflow.

## Step 1: Generate and Place Geometry

1.  Open the `corkscrew filter.scad` file.
2.  Set the `GENERATE_CFD_VOLUME` parameter to `true`.
3.  Render the model (F6) and export the resulting geometry as an STL file named `corkscrew_fluid.stl`.
4.  Place the `corkscrew_fluid.stl` file into the `constant/triSurface/` directory.

## Step 2: Configure the Mesh

1.  **Edit `system/blockMeshDict.template`**: This file is a template for the mesh generation. Open it and adjust the `vertices` to define a bounding box that is slightly larger than your `corkscrew_fluid.stl` model. The `FoamDriver` script (or your manual process) will use this template to generate the final `system/blockMeshDict`.
2.  **Edit `system/snappyHexMeshDict.template`**: For advanced users. The default settings provide a basic mesh, but you can edit this file to change mesh refinement levels, boundary layers, and quality controls. The `FoamDriver` automatically adjusts the `locationInMesh` in this template.
3.  **Edit `system/controlDict.template`**: To adjust solver settings or time controls, edit this template. The `FoamDriver` uses it to generate the run-specific `controlDict`.

## Step 3: Run the Simulation

Execute the following commands in order from within this directory (`corkscrewFilter/`) in your OpenFOAM terminal.

### Option A: Serial Execution (Single Core)

1.  **Create the background mesh:**
    ```bash
    blockMesh
    ```

2.  **Extract surface features to preserve sharp edges:**
    ```bash
    surfaceFeatureExtract
    ```

3.  **Generate the mesh around the STL:**
    *(This is the most time-consuming step)*
    ```bash
    snappyHexMesh -overwrite
    ```

4.  **(Optional) Create Patches:**
    ```bash
    topoSet
    createPatch -overwrite
    ```

5.  **(Optional) Check mesh quality:**
    ```bash
    checkMesh
    ```

6.  **Run the solver:**
    ```bash
    simpleFoam
    ```

### Option B: Parallel Execution (Multiple Cores)

If you have multiple cores, you can parallelize the meshing and solving steps to make them go faster. Ensure you have `system/decomposeParDict` configured (the default is 4 cores using the `hierarchical` method). Note that if you are using the AI-optimizer Python framework, you do not need to do this manually; just pass the `--cpus X` argument to the script!

1.  **Create the background mesh and extract features:**
    ```bash
    blockMesh
    surfaceFeatureExtract
    ```

2.  **Decompose the mesh for parallel processing:**
    ```bash
    decomposePar
    ```

3.  **Run snappyHexMesh in parallel (e.g., with 4 processors):**
    ```bash
    mpirun -np 4 snappyHexMesh -overwrite -parallel
    ```

4.  **Reconstruct the mesh:**
    ```bash
    reconstructParMesh -constant
    rm -rf processor*  # Optional: Clean up to save disk space
    ```

5.  **(Optional) Create Patches (Must be done serially!):**
    ```bash
    topoSet
    createPatch -overwrite
    ```

6.  **Decompose the final mesh for solving:**
    ```bash
    decomposePar -force
    ```

7.  **Run simpleFoam in parallel:**
    ```bash
    mpirun -np 4 simpleFoam -parallel
    ```

8.  **Reconstruct the final results:**
    ```bash
    reconstructPar -latestTime
    ```

## Step 4: Visualize the Results

1.  Create an empty file for ParaView to open:
    ```bash
    touch case.foam
    ```
2.  Open the `case.foam` file in the ParaView application.
3.  Use ParaView's filters (e.g., Stream Tracer, Glyph, Contour) to analyze velocity, pressure, and flow patterns.
