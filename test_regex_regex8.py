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
file_content = re.sub(r'type\s+(?!empty|fixedValue)[a-zA-Z0-9_]+\s*;', 'type fixedValue;\n        value uniform 1e-8;', file_content)
print(file_content)
