# OpenFOAM Case for Corkscrew Filter

This directory contains the necessary files to run a basic CFD simulation of the corkscrew filter using OpenFOAM. This guide summarizes the workflow.

## Step 1: Generate and Place Geometry

1.  Open the `corkscrew filter.scad` file.
2.  Set the `GENERATE_CFD_VOLUME` parameter to `true`.
3.  Render the model (F6) and export the resulting geometry as an STL file named `corkscrew_fluid.stl`.
4.  Place the `corkscrew_fluid.stl` file into the `constant/triSurface/` directory.

## Step 2: Configure the Mesh

1.  **Edit `system/blockMeshDict`**: Open this file and adjust the `vertices` to define a bounding box that is slightly larger than your `corkscrew_fluid.stl` model. You can find the dimensions of your STL by opening it in ParaView or another STL viewer.
2.  **Edit `system/snappyHexMeshDict`**: For advanced users. The default settings provide a basic mesh, but you can edit this file to change mesh refinement levels, boundary layers, and quality controls.

## Step 3: Run the Simulation

Execute the following commands in order from within this directory (`corkscrewFilter/`) in your OpenFOAM terminal:

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

4.  **(Optional) Check mesh quality:**
    ```bash
    checkMesh
    ```

5.  **Run the solver:**
    ```bash
    simpleFoam
    ```

## Step 4: Visualize the Results

1.  Create an empty file for ParaView to open:
    ```bash
    touch case.foam
    ```
2.  Open the `case.foam` file in the ParaView application.
3.  Use ParaView's filters (e.g., Stream Tracer, Glyph, Contour) to analyze velocity, pressure, and flow patterns.
