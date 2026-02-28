import re
with open("optimizer/foam_driver.py", "r") as f:
    code = f.read()

code = code.replace("self._generate_topoSetDict(bin_config, skip_io=using_assets)", "self._generate_topoSetDict(bin_config, skip_io=False)")
code = code.replace("self._generate_createPatchDict(bin_config, skip_io=using_assets)", "self._generate_createPatchDict(bin_config, skip_io=False)")

with open("optimizer/foam_driver.py", "w") as f:
    f.write(code)
