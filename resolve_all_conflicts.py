import re

with open("optimizer/foam_driver.py", "r", encoding="utf-8") as f:
    content = f.read()

# Instead of complex regex matching that might fail due to DOTALL catching multiple conflict blocks,
# I will iterate over the file line by line to locate the start and end of conflict zones.
# Then I can choose exactly what to keep.

lines = content.split('\n')
resolved_lines = []
in_conflict = False
current_block_head = []
current_block_main = []
section = None

for line in lines:
    if line.startswith("<<<<<<< HEAD"):
        in_conflict = True
        section = "HEAD"
        current_block_head = []
        current_block_main = []
        continue
    elif line.startswith("======="):
        section = "MAIN"
        continue
    elif line.startswith(">>>>>>> origin/main"):
        in_conflict = False
        section = None

        # Resolve the conflict based on content
        # 1. run_command signature
        if any("def run_command(" in l for l in current_block_head):
            resolved_lines.append('    def run_command(self, cmd, log_file=None, description="Processing", ignore_error=False, timeout=None, capture_output=False, monitor_callback=None, idle_timeout=None):')
        # 2. output_str try block
        elif any("output_str = \"\"" in l for l in current_block_head) and any("output = run_command_with_spinner" in l for l in current_block_main):
            resolved_lines.extend([
                '            output = run_command_with_spinner(',
                '                full_cmd,',
                '                target_log,',
                '                cwd=cwd,',
                '                description=description,',
                '                timeout=timeout,',
                '                monitor_callback=monitor_callback,',
                '                idle_timeout=idle_timeout,',
                '                capture_output=capture_output',
                '            )',
                '            if capture_output:',
                '                return True, output',
                '            return True'
            ])
        # 3. except Exception blocks
        elif any("return (False, \"\") if capture_output else False" in l for l in current_block_head):
            if any("e.output" in l for l in current_block_main):
                resolved_lines.extend([
                    '            if capture_output:',
                    '                return False, e.output or ""',
                    '            return False'
                ])
            else:
                resolved_lines.extend([
                    '            if capture_output:',
                    '                return False, ""',
                    '            return False'
                ])
        # 4. _sanitize_fields, _run_checkMesh, _update_fvSchemes etc.
        # For these, the HEAD version is the robust adaptive numerics that we want to keep.
        # `main` just tries to put these into `run_solver` instead of `FoamDriver`, so keep HEAD.
        else:
            resolved_lines.extend(current_block_head)
        continue

    if in_conflict:
        if section == "HEAD":
            current_block_head.append(line)
        elif section == "MAIN":
            current_block_main.append(line)
    else:
        resolved_lines.append(line)

with open("optimizer/foam_driver.py", "w", encoding="utf-8") as f:
    f.write('\n'.join(resolved_lines))
