import re

with open("optimizer/foam_driver.py", "r", encoding="utf-8") as f:
    content = f.read()

# 1. run_command method signature + output capture fix
c1 = re.compile(r"<<<<<<< HEAD\n    def run_command\(self, cmd, log_file=None, description=\"Processing\", ignore_error=False, timeout=None, capture_output=False\):\n=======\n    def run_command\(self, cmd, log_file=None, description=\"Processing\", ignore_error=False, timeout=None, capture_output=False, monitor_callback=None, idle_timeout=None\):\n>>>>>>> origin/main")
content = c1.sub(r'    def run_command(self, cmd, log_file=None, description="Processing", ignore_error=False, timeout=None, capture_output=False, monitor_callback=None, idle_timeout=None):', content)

# 2. Try-block in run_command
c2 = re.compile(r"<<<<<<< HEAD\n            output_str = \"\".*?return True\n=======\n            output = run_command_with_spinner.*?\n            return True\n>>>>>>> origin/main", re.DOTALL)
new_try = """            output = run_command_with_spinner(
                full_cmd,
                target_log,
                cwd=cwd,
                description=description,
                timeout=timeout,
                monitor_callback=monitor_callback,
                idle_timeout=idle_timeout,
                capture_output=capture_output
            )
            if capture_output:
                return True, output
            return True"""
content = c2.sub(new_try, content)

# 3. Exception handlers in run_command
c3 = re.compile(r"<<<<<<< HEAD\n                return \(False, \"\"\) if capture_output else False\n            return \(False, \"\"\) if capture_output else False\n=======\n            if capture_output:\n                return False, \"\"\n            return False\n>>>>>>> origin/main")
content = c3.sub(r'            if capture_output:\n                return False, ""\n            return False', content)

c4 = re.compile(r"<<<<<<< HEAD\n                return \(False, \"\"\) if capture_output else False\n            return \(False, \"\"\) if capture_output else False\n=======\n            if capture_output:\n                return False, e.output or \"\"\n            return False\n>>>>>>> origin/main")
content = c4.sub(r'            if capture_output:\n                return False, e.output or ""\n            return False', content)

# 4. _update_fvSolution signature and fvSchemes regex logic
# In `main`, it introduced a `mesh_class='bad'` to `_update_fvSchemes`.
# But in our adaptive numerics code, `_update_fvSchemes` runs `_run_checkMesh` itself.
# This means we just keep the HEAD version for these methods.
c5 = re.compile(r"<<<<<<< HEAD\n(.*?)\n=======\n.*?\n>>>>>>> origin/main", re.DOTALL)

def keep_head(match):
    return match.group(1)

content = c5.sub(keep_head, content)

with open("optimizer/foam_driver.py", "w", encoding="utf-8") as f:
    f.write(content)
