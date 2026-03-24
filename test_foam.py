from optimizer.foam_driver import FoamDriver
import os
import shutil

d = FoamDriver("test_case")
os.makedirs("test_case/constant", exist_ok=True)
with open("test_case/constant/turbulenceProperties", "w") as f:
    f.write("""simulationType RAS;
RAS
{
    model           kOmegaSST;
    turbulence      on;
}
""")
d._update_turbulence_properties("laminar")
with open("test_case/constant/turbulenceProperties", "r") as f:
    print(f.read())
