import re
file_content = """
    corkscrew
    {
        type fixedValue;
        value uniform 1e-8;
        Ks              uniform 0.0002;
        Cs              uniform 0.5;
        value           uniform 0;
    }
    inlet
    {
        type            turbulentIntensityKinematicEnergyInlet;
        intensity       0.05;
        value           uniform 0.0375;
    }
"""
file_content = re.sub(r'type\s+[a-zA-Z0-9]*WallFunction\s*;', 'type fixedValue;\n        value uniform 1e-8;', file_content)
file_content = re.sub(r'type\s+zeroGradient\s*;', 'type fixedValue;\n        value uniform 1e-8;', file_content)
file_content = re.sub(r'type\s+calculated\s*;', 'type fixedValue;\n        value uniform 1e-8;', file_content)
file_content = re.sub(r'type\s+[a-zA-Z0-9]*Inlet\s*;', 'type fixedValue;\n        value uniform 1e-8;', file_content)

# 2. Replace absolute zeroes with 1e-8
file_content = re.sub(r'uniform\s+0(\.0+)?\s*;', 'uniform 1e-8;', file_content)
file_content = re.sub(r'(?m)^\s*0(\.0+)?\s*$', '1e-8', file_content)
file_content = re.sub(r'(?m)^\s*0\.0+e[+-]\d+\s*$', '1e-8', file_content)
print(file_content)
