import re

with open("optimizer/foam_driver.py", "r", encoding="utf-8") as f:
    content = f.read()

# We will replace the whole conflict block with the HEAD version,
# because HEAD contains our new adaptive logic which replaces the main logic.
# Wait, `main` also has some import updates (os, re, shutil).
# However, the HEAD version rewrites the `content` completely using an f-string template,
# so it doesn't need to read the old file or modify existing blocks like main does.
# But main also had: `def _update_fvSolution(self, turbulence, cfd_settings=None):`
# while we updated it to `def _update_fvSolution(self, turbulence, cfd_settings=None, relaxation_override=None):`.

pattern = re.compile(r"<<<<<<< HEAD.*?=======(.*?)>>>>>>> origin/main", re.DOTALL)

def replacer(match):
    # The block matched by `(.*?)` is the main version. The content before `=======` is the HEAD version.
    # We want to extract the HEAD version and keep our signature for _update_fvSolution
    head_content = match.group(0).split("=======")[0].replace("<<<<<<< HEAD\n", "")

    # We need to extract the HEAD signature for _update_fvSolution
    if "def _update_fvSolution(self, turbulence, cfd_settings=None, relaxation_override=None):" in head_content:
        return head_content
    else:
        # If it doesn't have the signature (it was a different conflict), we just keep HEAD.
        return head_content

content = pattern.sub(replacer, content)

with open("optimizer/foam_driver.py", "w", encoding="utf-8") as f:
    f.write(content)
