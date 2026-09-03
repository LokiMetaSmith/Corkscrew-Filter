import re

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

        # CONFLICT 1: topoSetDict template vs old f-string logic + "CRITICAL FIX: Subtract IO faces"
        if "topoSetDict" in head_text and "{%" in head_text:
            # We want to keep our Jinja template but inject the subtraction fix into it.
            # The fix belongs inside `{% for bin in bins %}`.
            fix_str = """
    {% if not skip_io %}
    {
        name    bin_{{ bin.index }}_faces;
        type    faceSet;
        action  subtract;
        source  faceToFace;
        set     inletFaces;
    }
    {
        name    bin_{{ bin.index }}_faces;
        type    faceSet;
        action  subtract;
        source  faceToFace;
        set     outletFaces;
    }
    {% endif %}"""
            # Inject before the end of the loop
            resolved = head_text.replace("{% endfor %}", fix_str + "\n    {% endfor %}")
            out_lines.extend(resolved.splitlines(keepends=True))

        # CONFLICT 2: kinematicCloudProperties dynamic sizing + Jinja vs main's Python dynamic sizing
        elif "kinematicCloudProperties" in head_text and "{{" in head_text:
            # Our Jinja version relies on `self.config` logic in python, so we keep `head_text` mostly.
            # But main has logic to scale `parcelsPerSecond` based on `tube_od_m` and `fluid_velocity_z`.
            # This logic should be ported into our Python prep step right before calling `template.render`.

            # Since we can't easily parse Python out of main_text, let's keep our head_text
            # and we will manually fix the Python logic via another pass.
            out_lines.extend(head_text.splitlines(keepends=True))

        # CONFLICT 3: locationInMesh dynamic update in main vs our jinja rewrite in _generate_snappyHexMeshDict
        elif "snappyHexMeshDict" in head_text and "geometries" in head_text:
            # In our Jinja version, we explicitly read `locationInMesh` using regex and preserve it.
            # Main did the same. So we just keep our HEAD text.
            out_lines.extend(head_text.splitlines(keepends=True))

        else:
            # If we don't recognize the conflict, default to HEAD
            out_lines.extend(head_text.splitlines(keepends=True))

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
