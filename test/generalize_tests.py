import os

test_stls_file = "test/test_parameter_stls.py"
with open(test_stls_file, "r") as f:
    stls_content = f.read()

stls_content = stls_content.replace('driver = ScadDriver("corkscrew.scad")', '''
        import yaml
        # Determine the correct scad file based on the parameter file's name or metadata
        # Fallback to corkscrew.scad if not specified
        scad_file = "corkscrew.scad"

        # Heuristic: try to parse configs to see if this param file aligns with a specific config
        # For generalization, let's load all configs and see if any mention this param file.
        # Alternatively, assume the parameter file contains a comment like `// scad_file: "..."`
        with open(param_file, "r") as pf:
            first_line = pf.readline()
            if "scad_file:" in first_line:
                scad_file = first_line.split("scad_file:")[1].strip().strip('"').strip("'")

        driver = ScadDriver(scad_file)
''')

with open(test_stls_file, "w") as f:
    f.write(stls_content)

test_cfd_file = "test/test_cfd_generation.py"
with open(test_cfd_file, "r") as f:
    cfd_content = f.read()

# For `test_cfd_generation.py`, the setup class currently hardcodes `corkscrew.scad`.
# We can make it read from configs or test multiple drivers.
# Actually, the user report tests are explicitly for the corkscrew model.
# But we can allow overriding. Let's make it data-driven if needed, or simply let `driver` be configurable per test.

cfd_content = cfd_content.replace('cls.driver = ScadDriver("corkscrew.scad")', '''
        cls.corkscrew_driver = ScadDriver("corkscrew.scad")
        cls.manifold_driver = ScadDriver("cyclone_filter_manifold.scad", fluid_volume_module="fluid_volume")
''')

cfd_content = cfd_content.replace('self.driver', 'self.corkscrew_driver')

with open(test_cfd_file, "w") as f:
    f.write(cfd_content)
