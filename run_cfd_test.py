import yaml
from optimizer.foam_driver import FoamDriver

# Just load config
with open("configs/example_manifold_config.yaml", "r") as f:
    config = yaml.safe_load(f)

# Mock FoamDriver just to generate initial fields
import os
os.environ["PYTHONPATH"] = "optimizer"

driver = FoamDriver("corkscrewFilter", config=config)
driver._generate_turbulence_fields(os.path.join(driver.case_dir, "0.orig"), config.get('cfd_settings', {}))

for field in ["k", "epsilon", "omega", "nut"]:
    p = os.path.join(driver.case_dir, "0.orig", field)
    print(f"File: {field} exists: {os.path.exists(p)}")
