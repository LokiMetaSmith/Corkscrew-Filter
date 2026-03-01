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

# Freeze wall functions so they don't recalculate to 0 at runtime
file_content = re.sub(r'type\s+[a-zA-Z0-9]*WallFunction\s*;', 'type fixedValue;\n        value uniform 1e-8;', file_content)
file_content = re.sub(r'type\s+zeroGradient\s*;', 'type fixedValue;\n        value uniform 1e-8;', file_content)
file_content = re.sub(r'type\s+calculated\s*;', 'type fixedValue;\n        value uniform 1e-8;', file_content)
file_content = re.sub(r'type\s+[a-zA-Z0-9]*Inlet[a-zA-Z0-9]*\s*;', 'type fixedValue;\n        value uniform 1e-8;', file_content)

# Replace values to 1e-8
file_content = re.sub(r'value\s+uniform\s+[\d\.e\-\+]+;', 'value uniform 1e-8;', file_content)

print(file_content)
