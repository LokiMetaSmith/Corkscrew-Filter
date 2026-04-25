import sys
import subprocess

try:
    import trimesh
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "trimesh"])
    import trimesh

import inspect
print(trimesh.__version__)
print(inspect.signature(trimesh.Trimesh.nondegenerate_faces))
