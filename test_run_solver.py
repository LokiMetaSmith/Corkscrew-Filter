import re

with open("optimizer/foam_driver.py", "r") as f:
    content = f.read()

# Make sure _execute_simpleFoam is indented correctly since we just appended it to the file.
# The `class FoamDriver:` block ends somewhere. We need to make sure the appended functions are properly indented and placed *inside* the class.

if "def _execute_simpleFoam(" in content[-5000:]:
    print("Methods appended correctly. Verifying indentation...")

    # Find the class end and place methods correctly
    # actually, I just appended it to the end of the file. The end of the file in foam_driver.py might not be in the class!
