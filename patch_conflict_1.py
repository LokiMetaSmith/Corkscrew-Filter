import re

with open("optimizer/foam_driver.py", "r", encoding="utf-8") as f:
    content = f.read()

# Replace run_command definition conflict
pat1 = re.compile(r"<<<<<<< HEAD\n    def run_command\(self, cmd, log_file=None, description=\"Processing\", ignore_error=False, timeout=None, capture_output=False\):\n=======\n    def run_command\(self, cmd, log_file=None, description=\"Processing\", ignore_error=False, timeout=None, capture_output=False, monitor_callback=None, idle_timeout=None\):\n>>>>>>> origin/main")
content = pat1.sub(r'    def run_command(self, cmd, log_file=None, description="Processing", ignore_error=False, timeout=None, capture_output=False, monitor_callback=None, idle_timeout=None):', content)

# Replace try block conflict
pat2 = re.compile(r"<<<<<<< HEAD\n            output_str = \"\".*?return True\n=======\n            output = run_command_with_spinner.*?\n            return True\n>>>>>>> origin/main", re.DOTALL)

# In the try block conflict, the main branch uses an enhanced run_command_with_spinner that supports capture_output and monitors/idle.
# Let's keep the main version of the block, but ensuring capture_output logic acts correctly.

new_try_block = """            output = run_command_with_spinner(
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
content = pat2.sub(new_try_block, content)

# Replace TimeoutExpired return conflict
pat3 = re.compile(r"<<<<<<< HEAD\n                return \(False, \"\"\) if capture_output else False\n            return \(False, \"\"\) if capture_output else False\n=======\n            if capture_output:\n                return False, \"\"\n            return False\n>>>>>>> origin/main")
content = pat3.sub(r'            if capture_output:\n                return False, ""\n            return False', content)

# Replace CalledProcessError return conflict
pat4 = re.compile(r"<<<<<<< HEAD\n                return \(False, \"\"\) if capture_output else False\n            return \(False, \"\"\) if capture_output else False\n=======\n            if capture_output:\n                return False, \"\"\n            return False\n>>>>>>> origin/main")
content = pat4.sub(r'            if capture_output:\n                return False, ""\n            return False', content)

# Replace Exception return conflict
pat5 = re.compile(r"<<<<<<< HEAD\n                return \(False, \"\"\) if capture_output else False\n            return \(False, \"\"\) if capture_output else False\n=======\n            if capture_output:\n                return False, \"\"\n            return False\n>>>>>>> origin/main")
content = pat5.sub(r'            if capture_output:\n                return False, ""\n            return False', content)

with open("optimizer/foam_driver.py", "w", encoding="utf-8") as f:
    f.write(content)
