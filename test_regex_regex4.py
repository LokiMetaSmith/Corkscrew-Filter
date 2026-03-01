import re
file_content = """
    inlet
    {
        type            turbulentMixingLengthFrequencyInlet;
        mixingLength    0.007;
        value           uniform 150;
    }
"""
file_content = re.sub(r'type\s+[a-zA-Z0-9]*Inlet\s*;', 'type fixedValue;\n        value uniform 1e-8;', file_content)
print(file_content)
