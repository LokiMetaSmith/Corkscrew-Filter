import os
import sys

def main():
    sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'optimizer'))
    import yaml
    try:
        from foam_driver import FoamDriver
    except ImportError:
        from optimizer.foam_driver import FoamDriver

    os.environ["PYTHONPATH"] = "optimizer"

    config_path = os.path.join(os.path.dirname(__file__), '..', "configs/example_manifold_config.yaml")
    if not os.path.exists(config_path):
        config_path = "configs/example_manifold_config.yaml"

    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    driver = FoamDriver("corkscrewFilter", config=config)

    # Setup initial conditions the same way it's done in `prepare_case`
    driver._generate_turbulence_fields(os.path.join(driver.case_dir, "0.orig"), config.get('cfd_settings', {}))
    driver._apply_boundary_conditions(os.path.join(driver.case_dir, "0.orig"))
    driver._sanitize_fields(os.path.join(driver.case_dir, "0.orig"))

if __name__ == "__main__":
    main()
