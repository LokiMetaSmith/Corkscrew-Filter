import os
import sys

def main():
    # Update path so tests can run from anywhere
    sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'optimizer'))
    import yaml
    try:
        from foam_driver import FoamDriver
    except ImportError:
        from optimizer.foam_driver import FoamDriver

    # Just load config
    config_path = os.path.join(os.path.dirname(__file__), '..', "configs/example_manifold_config.yaml")
    if not os.path.exists(config_path):
        config_path = "configs/example_manifold_config.yaml"

    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    # Mock FoamDriver just to generate initial fields
    os.environ["PYTHONPATH"] = "optimizer"

    driver = FoamDriver("corkscrewFilter", config=config)
    driver._generate_turbulence_fields(os.path.join(driver.case_dir, "0.orig"), config.get('cfd_settings', {}))

    for field in ["k", "epsilon", "omega", "nut"]:
        p = os.path.join(driver.case_dir, "0.orig", field)
        print(f"File: {field} exists: {os.path.exists(p)}")

if __name__ == "__main__":
    main()
