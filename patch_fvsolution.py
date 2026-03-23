import re

with open("optimizer/foam_driver.py", "r") as f:
    content = f.read()

# Replace _update_fvSolution signature and body
old_def = "    def _update_fvSolution(self, turbulence, cfd_settings=None):"
new_def = "    def _update_fvSolution(self, turbulence, cfd_settings=None, relaxation_override=None):"

content = content.replace(old_def, new_def)

# Find the part where it handles relaxation factors
old_relax = """        if cfd_settings and 'relaxation_factors' in cfd_settings:
            relax_factors = cfd_settings['relaxation_factors']"""

new_relax = """        relax_factors = relaxation_override or (cfd_settings.get('relaxation_factors', {}) if cfd_settings else {})
        if relax_factors:"""

content = content.replace(old_relax, new_relax)

with open("optimizer/foam_driver.py", "w") as f:
    f.write(content)
