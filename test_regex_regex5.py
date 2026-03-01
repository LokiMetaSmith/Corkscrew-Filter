import re
file_content = """
    outlet
    {
        type            zeroGradient;
    }
"""
file_content = re.sub(r'type\s+zeroGradient\s*;', 'type fixedValue;\n        value uniform 1e-8;', file_content)
print(file_content)
