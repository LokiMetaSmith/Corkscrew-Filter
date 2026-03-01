import re

file_content = """
    walls
    {
        type            nutkRoughWallFunction;
        Ks              uniform 0.0002;  // 0.2mm layer height roughness!
        Cs              uniform 0.5;     // Standard roughness constant
        value           uniform 0;
    }
"""

# Original script
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

# New: Replace all remaining uniform scalar values with 1e-8 for absolute freezing.
# Wait, this would overwrite Ks and Cs!!! "Ks uniform 0.0002"
print(file_content)
