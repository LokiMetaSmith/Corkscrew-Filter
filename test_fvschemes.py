import yaml
from optimizer.foam_driver import FoamDriver
import os
os.environ["PYTHONPATH"] = "optimizer"

with open("configs/example_manifold_config.yaml", "r") as f:
    config = yaml.safe_load(f)

driver = FoamDriver("corkscrewFilter", config=config)

# Run fvSchemes update
driver._update_fvSchemes("kOmegaSST", "bad")

with open(os.path.join(driver.case_dir, "system", "fvSchemes")) as f:
    print(f.read())
