import re

with open('optimizer/foam_driver.py', 'r') as f:
    content = f.read()

# We have two conflicts. The first is in _generate_kinematicCloudProperties where upstream has the old f-string logic and we have the new Jinja2 template logic. We want to keep our Jinja2 template logic.
# The second is in interpolationSchemes where upstream changed 'cell' to 'cellPoint'. We should keep the new jinja2 string format, but update 'cell' to 'cellPoint'.

parts = re.split(r'<<<<<<< Updated upstream.*?=======', content, flags=re.DOTALL)

# Since we split on the conflict marker, parts[1] is everything after the first ======= up to the end or next <<<<<<<
# parts[2] is after the second =======, etc.
# This might be tricky, let's just use regex substitution.

# 1. The first conflict: the whole python f-string logic vs our Jinja template setup.
# We want the Jinja template setup (Stashed changes).
content = re.sub(r'<<<<<<< Updated upstream.*?=======\n(.*?)\n>>>>>>> Stashed changes', r'\1', content, flags=re.DOTALL)

# Now we need to manually update cell to cellPoint in the interpolationSchemes in our Jinja template string since that was the upstream fix.
content = content.replace('k               cell;', 'k               cellPoint;')
content = content.replace('epsilon         cell;', 'epsilon         cellPoint;')
content = content.replace('omega           cell;', 'omega           cellPoint;')

with open('optimizer/foam_driver.py', 'w') as f:
    f.write(content)
