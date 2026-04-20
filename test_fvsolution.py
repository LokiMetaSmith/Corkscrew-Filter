import yaml
from optimizer.foam_driver import FoamDriver
import os
os.environ["PYTHONPATH"] = "optimizer"

with open("configs/example_manifold_config.yaml", "r") as f:
    config = yaml.safe_load(f)

driver = FoamDriver("corkscrewFilter", config=config)

# Run fvSolution update
driver._update_fvSolution("kOmegaSST", config.get('cfd_settings', {}), {"p": 0.1, "U": 0.3, "k": 0.3, "omega": 0.3})

with open(os.path.join(driver.case_dir, "system", "fvSolution")) as f:
    print(f.read())
