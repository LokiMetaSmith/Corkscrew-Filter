import re

with open("optimizer/foam_driver.py", "r", encoding="utf-8") as f:
    content = f.read()

pat = re.compile(r"<<<<<<< HEAD\n                return \(False, \"\"\) if capture_output else False\n            return \(False, \"\"\) if capture_output else False\n=======\n            if capture_output:\n                return False, e.output or \"\"\n            return False\n>>>>>>> origin/main")
content = pat.sub(r'            if capture_output:\n                return False, e.output or ""\n            return False', content)

with open("optimizer/foam_driver.py", "w", encoding="utf-8") as f:
    f.write(content)
