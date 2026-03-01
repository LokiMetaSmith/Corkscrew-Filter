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

# 1. First convert everything (except empty/symmetry) to fixedValue 1e-8
# We will do this by looking for the blocks, or doing line-by-line / regex replacements
# Wall functions
file_content = re.sub(r'type\s+[a-zA-Z0-9]*WallFunction\s*;', 'type fixedValue;\n        value uniform 1e-8;', file_content)
# Zero gradients
file_content = re.sub(r'type\s+zeroGradient\s*;', 'type fixedValue;\n        value uniform 1e-8;', file_content)
# Calculated
file_content = re.sub(r'type\s+calculated\s*;', 'type fixedValue;\n        value uniform 1e-8;', file_content)
# Inlets/Outlets
file_content = re.sub(r'type\s+[a-zA-Z0-9]*Inlet[a-zA-Z0-9]*\s*;', 'type fixedValue;\n        value uniform 1e-8;', file_content)
file_content = re.sub(r'type\s+[a-zA-Z0-9]*Outlet[a-zA-Z0-9]*\s*;', 'type fixedValue;\n        value uniform 1e-8;', file_content)

# 2. Replace absolute zeroes and all other uniform scalar values with 1e-8
file_content = re.sub(r'value\s+uniform\s+[\d\.e\-\+]+;', 'value uniform 1e-8;', file_content)

# 3. Clean up duplicate "value uniform 1e-8;" which might have been generated
file_content = re.sub(r'(value\s+uniform\s+1e-8;\s*)+', 'value uniform 1e-8;\n        ', file_content)

print(file_content)
