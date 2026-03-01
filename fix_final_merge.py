with open('optimizer/foam_driver.py', 'r') as f:
    lines = f.readlines()

out_lines = []
in_conflict = False
conflict_part = 0
head_lines = []
main_lines = []

for line in lines:
    if line.startswith('<<<<<<< HEAD'):
        in_conflict = True
        conflict_part = 1
        head_lines = []
        main_lines = []
        continue
    elif line.startswith('======='):
        conflict_part = 2
        continue
    elif line.startswith('>>>>>>> origin/main'):
        in_conflict = False

        # Analyze the conflict and resolve
        head_text = "".join(head_lines)
        main_text = "".join(main_lines)

        if "self._apply_boundary_conditions(zero)" in head_text and "self._update_turbulence_properties(turbulence)" in main_text:
            out_lines.append(head_text)
            out_lines.append(main_text)
        elif "def _apply_boundary_conditions" in head_text and "def _update_turbulence_properties" in main_text:
            out_lines.append(head_text)
            out_lines.append(main_text)
        elif "def _generate_kinematicCloudProperties(self, bin_config=None, turbulence=\"laminar\")" in main_text:
            # We already have def _generate_kinematicCloudProperties above, but main modified it to take turbulence
            # We should probably just pass turbulence to the template if needed, or ignore it if our template handles it differently.
            # Actually, main's _generate_kinematicCloudProperties sets dispersion based on turbulence.
            # Let's keep head_text and discard main_text here, since we will manually update our _generate_kinematicCloudProperties signature later.
            out_lines.append(head_text)
        elif "template = jinja2.Template(template_str)" in head_text:
            # This is where main has the new template string generation for kinematic cloud.
            out_lines.append(head_text)
        else:
            out_lines.append(head_text)

        continue

    if in_conflict:
        if conflict_part == 1:
            head_lines.append(line)
        else:
            main_lines.append(line)
    else:
        out_lines.append(line)

with open('optimizer/foam_driver.py', 'w') as f:
    f.writelines(out_lines)

# Resolve test_cloud_config.py
with open('test/test_cloud_config.py', 'r') as f:
    content = f.read()
import re
content = re.sub(r'<<<<<<< HEAD.*?=======\n', '', content, flags=re.DOTALL)
content = re.sub(r'>>>>>>> origin/main\n', '', content)
with open('test/test_cloud_config.py', 'w') as f:
    f.write(content)
