import re

with open("optimizer/foam_driver.py", "r", encoding="utf-8") as f:
    content = f.read()

# I see what happened. The pattern.sub regex I used for replacing the fvSchemes block truncated the string abruptly at `| `.
# I need to restore the full fvSchemes string assignment.

head_f_string = """        # --- Build fvSchemes cleanly ---
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
"""

pattern = re.compile(r"        # --- Build fvSchemes cleanly ---.*?        target_path = os.path.join\(self.case_dir, \"system\", \"fvSchemes\"\)", re.DOTALL)
content = pattern.sub(head_f_string + "\n        target_path = os.path.join(self.case_dir, \"system\", \"fvSchemes\")", content, count=1)

with open("optimizer/foam_driver.py", "w", encoding="utf-8") as f:
    f.write(content)
