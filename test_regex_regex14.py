import re
file_content = """
    inlet
    {
        type            turbulentIntensityKineticEnergyInlet;
        intensity       0.05;
        value           uniform 0.09375;
    }

    outlet
    {
        type            zeroGradient;
    }

    walls
    {
        type            kqRWallFunction;
        value           uniform 0.09375;
    }

    frontAndBack
    {
        type            empty;
    }

    somePatch
    {
        type            fixedValue;
        value           uniform 1e-8;
    }
"""

# Let's target the exact problem
# The problem is that inlet and outlet are not being frozen in the original script!
# They use `turbulentMixingLengthDissipationRateInlet`, `turbulentIntensityKineticEnergyInlet`, `turbulentMixingLengthFrequencyInlet`, `inletOutlet`, etc.
# These recalculate the fields!

file_content = re.sub(r'type\s+[a-zA-Z0-9]*WallFunction\s*;', 'type fixedValue;\n        value uniform 1e-8;', file_content)
file_content = re.sub(r'type\s+zeroGradient\s*;', 'type fixedValue;\n        value uniform 1e-8;', file_content)
file_content = re.sub(r'type\s+calculated\s*;', 'type fixedValue;\n        value uniform 1e-8;', file_content)

# We need to freeze ANY type that ends with "Inlet", "Outlet", "InletOutlet", etc.
file_content = re.sub(r'type\s+[a-zA-Z0-9]*[iI]nlet[a-zA-Z0-9]*\s*;', 'type fixedValue;\n        value uniform 1e-8;', file_content)
file_content = re.sub(r'type\s+[a-zA-Z0-9]*[oO]utlet[a-zA-Z0-9]*\s*;', 'type fixedValue;\n        value uniform 1e-8;', file_content)

# 2. Replace absolute zeroes with 1e-8
file_content = re.sub(r'uniform\s+0(\.0+)?\s*;', 'uniform 1e-8;', file_content)
file_content = re.sub(r'(?m)^\s*0(\.0+)?\s*$', '1e-8', file_content)
file_content = re.sub(r'(?m)^\s*0\.0+e[+-]\d+\s*$', '1e-8', file_content)

print(file_content)
