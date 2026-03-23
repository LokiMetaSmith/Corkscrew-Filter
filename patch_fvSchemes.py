import re
import os

with open("optimizer/foam_driver.py", "r") as f:
    content = f.read()

# Replace _update_fvSchemes by matching the function block
pattern = re.compile(r"    def _update_fvSchemes\(self, turbulence\):.*?(?=    def _update_fvSolution)", re.DOTALL)

new_func = """    def _update_fvSchemes(self, turbulence):
        quality_output = self._run_checkMesh()
        q = self._parse_mesh_quality(quality_output)

        # Check for degenerate cells first
        if q["min_vol"] < 1e-15:
            print(f"🚨 Degenerate cells detected (min_vol = {q['min_vol']:.3e}) → forcing laminar")
            turbulence = "laminar"

        mesh_class = self._classify_mesh(q)

        print(f"[Mesh Quality] {mesh_class} | {q}")

        # Base config
        snGrad = "limited corrected 0.33"
        laplacian = "Gauss linear limited corrected 0.33"
        div_u = "bounded Gauss upwind"

        # Adapt based on mesh
        if mesh_class == "good":
            snGrad = "corrected"
            laplacian = "Gauss linear corrected"
            div_u = "Gauss linearUpwind grad(U)"

        elif mesh_class == "moderate":
            snGrad = "limited corrected 0.5"
            laplacian = "Gauss linear limited corrected 0.5"
            div_u = "bounded Gauss linearUpwind grad(U)"

        elif mesh_class == "bad":
            snGrad = "limited corrected 0.33"
            laplacian = "Gauss linear limited corrected 0.33"
            div_u = "bounded Gauss upwind"

        elif mesh_class == "terrible":
            print("⚠️ Mesh is terrible → forcing laminar + max stability")
            turbulence = "laminar"
            snGrad = "limited corrected 0.2"
            laplacian = "Gauss linear limited corrected 0.2"
            div_u = "bounded Gauss upwind"

        # --- Build fvSchemes cleanly ---
        content = f\"\"\"/*--------------------------------*- C++ -*----------------------------------*\\
| =========                 |                                                 |
| \\\\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox           |
|  \\\\    /   O peration     | Version:  v2512                                 |
|   \\\\  /    A nd           | Website:  www.openfoam.com                      |
|    \\\\/     M anipulation  |                                                 |
\\*---------------------------------------------------------------------------*/
FoamFile
{{
    version     2.0;
    format      ascii;
    class       dictionary;
    location    "system";
    object      fvSchemes;
}}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

ddtSchemes
{{
    default         steadyState;
}}

gradSchemes
{{
    default         Gauss linear;
    grad(p)         Gauss linear;
}}

divSchemes
{{
    default         none;
    div(phi,U)      {div_u};
\"\"\"

        if turbulence != "laminar" and turbulence != "kOmegaSST_disabled":
            if turbulence == "RNGkEpsilon":
                content += \"\"\"    div(phi,k)      bounded Gauss upwind;
    div(phi,epsilon) bounded Gauss upwind;
\"\"\"
            elif turbulence == "kOmegaSST":
                content += \"\"\"    div(phi,k)      bounded Gauss upwind;
    div(phi,omega) bounded Gauss upwind;
\"\"\"

        content += \"\"\"}

laplacianSchemes
{
    default         \"\"\" + laplacian + \"\"\";
}

interpolationSchemes
{
    default         linear;
}

snGradSchemes
{
    default         \"\"\" + snGrad + \"\"\";
}

wallDist
{
    method meshWave;
}

// ************************************************************************* //
\"\"\"

        target_path = os.path.join(self.case_dir, "system", "fvSchemes")
        with open(target_path, "w", newline='\\n') as f:
            f.write(content)

        return turbulence

"""

content = pattern.sub(new_func, content, count=1)

with open("optimizer/foam_driver.py", "w") as f:
    f.write(content)
