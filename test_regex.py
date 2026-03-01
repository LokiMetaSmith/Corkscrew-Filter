import re
file_content = """
    corkscrew
    {
        type            nutkRoughWallFunction;
        Ks              uniform 0.0002;
        Cs              uniform 0.5;
        value           uniform 0;
    }
"""
file_content = re.sub(r'type\s+[a-zA-Z0-9]*WallFunction\s*;', 'type fixedValue;\n        value uniform 1e-8;', file_content)
print(file_content)
