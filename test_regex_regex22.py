import re

file_content = """
    walls
    {
        type            nutkRoughWallFunction;
        Ks              uniform 0.0002;  // 0.2mm layer height roughness!
        Cs              uniform 0.5;     // Standard roughness constant
        value           uniform 0;
    }
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
"""

file_content = re.sub(r'type\s+[a-zA-Z0-9]*WallFunction\s*;', 'type fixedValue;\n        value uniform 1e-8;', file_content)
file_content = re.sub(r'type\s+zeroGradient\s*;', 'type fixedValue;\n        value uniform 1e-8;', file_content)
file_content = re.sub(r'type\s+calculated\s*;', 'type fixedValue;\n        value uniform 1e-8;', file_content)
file_content = re.sub(r'type\s+[a-zA-Z0-9]*[iI]nlet[a-zA-Z0-9]*\s*;', 'type fixedValue;\n        value uniform 1e-8;', file_content)
file_content = re.sub(r'type\s+[a-zA-Z0-9]*[oO]utlet[a-zA-Z0-9]*\s*;', 'type fixedValue;\n        value uniform 1e-8;', file_content)

# 2. Replace absolute zeroes with 1e-8
file_content = re.sub(r'uniform\s+0(\.0+)?\s*;', 'uniform 1e-8;', file_content)
file_content = re.sub(r'(?m)^\s*0(\.0+)?\s*$', '1e-8', file_content)
file_content = re.sub(r'(?m)^\s*0\.0+e[+-]\d+\s*$', '1e-8', file_content)

# 3. Replace all remaining non-1e-8 uniform `value` entries (like 0.09375, 14.8, 150) with 1e-8
file_content = re.sub(r'value\s+uniform\s+[0-9\.eE\+\-]+;', 'value uniform 1e-8;', file_content)

# Deduplicate `value uniform 1e-8;`
file_content = re.sub(r'(value\s+uniform\s+1e-8;\s*)+', 'value uniform 1e-8;\n        ', file_content)

# Replace internalField
file_content = re.sub(r'internalField\s+uniform\s+[0-9\.eE\+\-]+;', 'internalField   uniform 1e-8;', file_content)

print(file_content)
