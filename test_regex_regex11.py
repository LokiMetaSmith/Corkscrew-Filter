import re
file_content = """
    walls
    {
        type fixedValue;
        value uniform 1e-8;
        value           uniform 0.09375;
        Ks              uniform 0.0002;
    }
    frontAndBack
    {
        type            empty;
    }
"""

# Replace values to 1e-8
file_content = re.sub(r'value\s+uniform\s+[\d\.e\-\+]+;', 'value uniform 1e-8;', file_content)
# remove duplicates
file_content = re.sub(r'(value\s+uniform\s+1e-8;\s*)+', 'value uniform 1e-8;\n        ', file_content)


print(file_content)
