import re
file_content = """
    walls
    {
        type fixedValue;
        value uniform 1e-8;
        Ks              uniform 0.0002;  // 0.2mm layer height roughness!
        Cs              uniform 0.5;     // Standard roughness constant
        value           uniform 0;
    }
"""
file_content = re.sub(r'uniform\s+0(\.0+)?\s*;', 'uniform 1e-8;', file_content)
print(file_content)
