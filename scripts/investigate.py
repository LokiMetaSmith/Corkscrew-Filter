import yaml

with open("configs/corkscrew_config.yaml", "r") as f:
    config = yaml.safe_load(f)

print(config.get("geometry", {}).get("parameters", {}))
