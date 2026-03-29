import yaml
from optimizer.foam_driver import FoamDriver
import os
os.environ["PYTHONPATH"] = "optimizer"

with open("configs/example_manifold_config.yaml", "r") as f:
    config = yaml.safe_load(f)

driver = FoamDriver("corkscrewFilter", config=config)

# Generate fields
driver._generate_turbulence_fields(os.path.join(driver.case_dir, "0.orig"), config.get('cfd_settings', {}))
driver._apply_boundary_conditions(os.path.join(driver.case_dir, "0.orig"))

print("epsilon value for inlet:")
with open(os.path.join(driver.case_dir, "0.orig", "epsilon")) as f:
    print([line for line in f if "value" in line])
