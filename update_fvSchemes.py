import re

with open("optimizer/foam_driver.py", "r") as f:
    content = f.read()

# Replace _update_fvSchemes
old_func = """    def _update_fvSchemes(self, turbulence):
        import shutil
        template_path = os.path.join(self.case_dir, "system", "fvSchemes.template")
        target_path = os.path.join(self.case_dir, "system", "fvSchemes")

        # Recover from permanent modification if user lacks template
        if not os.path.exists(template_path) and os.path.exists(target_path):
            shutil.copy2(target_path, template_path)

        if os.path.exists(template_path):
            shutil.copy2(template_path, target_path)

        if not os.path.exists(target_path): return

        with open(target_path, 'r') as f:
            content = f.read()

        # Apply limited correctors for high-skew automated meshes
        # This prevents SIGFPEs in snGrad and laplacian calculations
        content = re.sub(r"(snGradSchemes\s*\{[^}]*?default\s+).*?;", r"\g<1>limited corrected 0.33;", content)
        content = re.sub(r"(laplacianSchemes\s*\{[^}]*?default\s+).*?;", r"\g<1>Gauss linear limited corrected 0.33;", content)

        if turbulence == "laminar":
            content = re.sub(r"div\(phi,k\).*?;", "", content)
            content = re.sub(r"div\(phi,epsilon\).*?;", "", content)
            content = re.sub(r"div\(phi,omega\).*?;", "", content)
            content = re.sub(r"div\(phi,R\).*?;", "", content)
            # Switch to upwind for U to ensure stability on coarse mesh without turbulent viscosity
            content = re.sub(r"div\(phi,U\).*?;", "div(phi,U)      bounded Gauss upwind;", content)
        elif turbulence == "RNGkEpsilon":
            content = re.sub(r"div\(phi,omega\).*?;", "", content)
            content = re.sub(r"div\(phi,R\).*?;", "", content)
            # Upwind U to ensure stability on coarse/scaled meshes with turbulence enabled
            content = re.sub(r"div\(phi,U\).*?;", "div(phi,U)      bounded Gauss upwind;", content)

            # Robustly inject if missing due to prior corrupted files (handles Windows CRLF and arbitrary spacing)
            if "div(phi,k)" not in content and "divSchemes" in content:
                content = re.sub(r"(divSchemes\s*\{)", r"\1\n    div(phi,k)      bounded Gauss upwind;", content, count=1)
            if "div(phi,epsilon)" not in content and "divSchemes" in content:
                content = re.sub(r"(divSchemes\s*\{)", r"\1\n    div(phi,epsilon) bounded Gauss upwind;", content, count=1)

        elif turbulence == "kOmegaSST" or turbulence == "kOmegaSST_disabled":
            content = re.sub(r"div\(phi,R\).*?;", "", content)

            if "div(phi,k)" not in content and "divSchemes" in content:
                content = re.sub(r"(divSchemes\s*\{)", r"\1\n    div(phi,k)      bounded Gauss upwind;", content, count=1)
            if "div(phi,omega)" not in content and "divSchemes" in content:
                content = re.sub(r"(divSchemes\s*\{)", r"\1\n    div(phi,omega) bounded Gauss upwind;", content, count=1)

        with open(target_path, 'w', newline='\n') as f:
            # Clean up empty lines created by regex sub and enforce Unix line endings
            cleaned = "\n".join([s for s in content.splitlines() if s.strip()])
            f.write(cleaned + "\n")

        # If we had to synthesize the file from scratch because template was corrupted, save it
        if not os.path.exists(template_path):
            shutil.copy2(target_path, template_path)"""

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
                content += f\"\"\"    div(phi,k)      bounded Gauss upwind;
    div(phi,epsilon) bounded Gauss upwind;
\"\"\"
            elif turbulence == "kOmegaSST":
                content += f\"\"\"    div(phi,k)      bounded Gauss upwind;
    div(phi,omega) bounded Gauss upwind;
\"\"\"

        content += f\"\"\"}}

laplacianSchemes
{{
    default         {laplacian};
}}

interpolationSchemes
{{
    default         linear;
}}

snGradSchemes
{{
    default         {snGrad};
}}

wallDist
{{
    method meshWave;
}}

// ************************************************************************* //
\"\"\"

        target_path = os.path.join(self.case_dir, "system", "fvSchemes")
        with open(target_path, "w", newline='\\n') as f:
            f.write(content)

        return turbulence"""

if old_func in content:
    content = content.replace(old_func, new_func)
else:
    print("Could not find old _update_fvSchemes")

with open("optimizer/foam_driver.py", "w") as f:
    f.write(content)
