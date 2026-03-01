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

# Instead of injecting value uniform 1e-8 right away,
# let's just change the type to fixedValue, and then change ALL uniform values to 1e-8.
# That's much cleaner and won't result in duplicates.

file_content = re.sub(r'type\s+[a-zA-Z0-9]*WallFunction\s*;', 'type fixedValue;', file_content)
file_content = re.sub(r'type\s+zeroGradient\s*;', 'type fixedValue;\n        value uniform 1e-8;', file_content) # zeroGradient doesn't have a value by default, so we add it
file_content = re.sub(r'type\s+calculated\s*;', 'type fixedValue;\n        value uniform 1e-8;', file_content) # calculated may or may not have a value, so we add it just in case
file_content = re.sub(r'type\s+[a-zA-Z0-9]*[iI]nlet[a-zA-Z0-9]*\s*;', 'type fixedValue;', file_content)
file_content = re.sub(r'type\s+[a-zA-Z0-9]*[oO]utlet[a-zA-Z0-9]*\s*;', 'type fixedValue;', file_content)

# 2. Replace absolute zeroes with 1e-8
file_content = re.sub(r'uniform\s+0(\.0+)?\s*;', 'uniform 1e-8;', file_content)
file_content = re.sub(r'(?m)^\s*0(\.0+)?\s*$', '1e-8', file_content)
file_content = re.sub(r'(?m)^\s*0\.0+e[+-]\d+\s*$', '1e-8', file_content)

# 3. Replace all remaining non-1e-8 uniform values (like 0.09375, 14.8, 150) with 1e-8
file_content = re.sub(r'value\s+uniform\s+[0-9\.eE\+\-]+;', 'value uniform 1e-8;', file_content)

# Deduplicate `value uniform 1e-8;`
file_content = re.sub(r'(value\s+uniform\s+1e-8;\s*)+', 'value uniform 1e-8;\n        ', file_content)

# Replace internalField
file_content = re.sub(r'internalField\s+uniform\s+[0-9\.eE\+\-]+;', 'internalField   uniform 1e-8;', file_content)

print(file_content)
