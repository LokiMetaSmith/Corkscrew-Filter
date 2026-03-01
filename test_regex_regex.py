import re
file_content = """
    inlet
    {
        type            turbulentMixingLengthDissipationRateInlet;
        mixingLength    0.007; // 0.07 * D_hydraulic (~0.1m)
        value           uniform 14.8;
    }
"""
file_content = re.sub(r'type\s+[a-zA-Z0-9]*Inlet\s*;', 'type fixedValue;\n        value uniform 1e-8;', file_content)
print(file_content)
