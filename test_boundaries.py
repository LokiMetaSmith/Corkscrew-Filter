import yaml
from optimizer.foam_driver import FoamDriver
import os
os.environ["PYTHONPATH"] = "optimizer"

with open("configs/example_manifold_config.yaml", "r") as f:
    config = yaml.safe_load(f)

driver = FoamDriver("corkscrewFilter", config=config)

# Setup initial conditions the same way it's done in `prepare_case`
driver._generate_turbulence_fields(os.path.join(driver.case_dir, "0.orig"), config.get('cfd_settings', {}))
driver._apply_boundary_conditions(os.path.join(driver.case_dir, "0.orig"))

for field in ["k", "epsilon", "omega", "nut"]:
    path = os.path.join(driver.case_dir, "0.orig", field)
    if os.path.exists(path):
        print(f"--- {field} ---")
        with open(path) as f:
            print(f.read())
