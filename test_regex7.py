import re
file_content = """
    outlet
    {
        type            inletOutlet;
        inletValue      uniform 0;
        value           uniform 0;
    }
"""
file_content = re.sub(r'type\s+[a-zA-Z0-9]*[iI]nlet[a-zA-Z0-9]*\s*;', 'type fixedValue;\n        value uniform 1e-8;', file_content)
print(file_content)
