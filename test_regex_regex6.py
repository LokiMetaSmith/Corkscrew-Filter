import re
file_content = """
    walls
    {
        type fixedValue;
        value uniform 1e-8;
        value           uniform 0.09375;
    }
"""
file_content = re.sub(r'(?m)^(\s*value\s+)uniform\s+[\d\.e\-\+]+;$', r'\g<1>uniform 1e-8;', file_content)
print(file_content)
