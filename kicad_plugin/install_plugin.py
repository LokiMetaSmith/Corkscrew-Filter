"""
install_plugin.py

Auto-installer for the OpenAuto EM Live KiCad Action Plugin.
Detects KiCad installation directories across Windows, Linux, and macOS.
Creates symlink or copies plugin directory into KiCad's scripting/plugins folder.
"""

import os
import sys
import shutil
import argparse
from typing import List


def find_kicad_plugin_dirs() -> List[str]:
    """Scans operating system for KiCad scripting plugin directories."""
    candidates = []

    if sys.platform.startswith("win"):
        appdata = os.environ.get("APPDATA", "")
        if appdata:
            # Check KiCad 10.0, 9.0, 8.0, 7.0, 6.0, and unversioned
            for ver in ["10.0", "9.0", "8.0", "7.0", "6.0", ""]:
                ver_dir = os.path.join(appdata, "kicad", ver) if ver else os.path.join(appdata, "kicad")
                if os.path.exists(ver_dir):
                    candidates.append(os.path.join(ver_dir, "scripting", "plugins"))
                    candidates.append(os.path.join(ver_dir, "plugins"))

    elif sys.platform.startswith("linux"):
        home = os.path.expanduser("~")
        for ver in ["10.0", "9.0", "8.0", "7.0", "6.0", ""]:
            for base in [os.path.join(home, ".local", "share", "kicad", ver), os.path.join(home, ".kicad", ver)]:
                if os.path.exists(base):
                    candidates.append(os.path.join(base, "scripting", "plugins"))
                    candidates.append(os.path.join(base, "plugins"))

    elif sys.platform == "darwin":
        home = os.path.expanduser("~")
        for ver in ["10.0", "9.0", "8.0", "7.0", "6.0", ""]:
            base = os.path.join(home, "Library", "Preferences", "kicad", ver)
            if os.path.exists(base):
                candidates.append(os.path.join(base, "scripting", "plugins"))
                candidates.append(os.path.join(base, "plugins"))

    return list(dict.fromkeys(candidates))


def install_plugin(target_dir: str = None, use_symlink: bool = True):
    plugin_src = os.path.abspath(os.path.dirname(__file__))

    if not target_dir:
        dirs = find_kicad_plugin_dirs()
        if not dirs:
            print("[Install] Notice: No existing KiCad directory found.")
            # Default Windows fallback
            if sys.platform.startswith("win"):
                appdata = os.environ.get("APPDATA", "")
                target_dir = os.path.join(appdata, "kicad", "10.0", "scripting", "plugins")
            else:
                target_dir = os.path.expanduser("~/.local/share/kicad/10.0/scripting/plugins")
        else:
            target_dir = dirs[0]

    dest = os.path.join(target_dir, "openauto_em_live")
    os.makedirs(target_dir, exist_ok=True)

    print(f"\n=======================================================")
    print(f"  Installing OpenAuto EM Live Action Plugin to KiCad")
    print(f"  Source: {plugin_src}")
    print(f"  Target: {dest}")
    print(f"=======================================================\n")

    if os.path.exists(dest):
        if os.path.islink(dest):
            os.unlink(dest)
        else:
            shutil.rmtree(dest)

    success = False
    if use_symlink:
        try:
            os.symlink(plugin_src, dest, target_is_directory=True)
            print("[Install] Successfully created directory symlink.")
            success = True
        except Exception as e:
            print(f"[Install] Symlink failed ({e}), falling back to direct copy...")

    if not success:
        shutil.copytree(plugin_src, dest)
        print("[Install] Successfully copied plugin files.")

    print("\nInstallation Complete!")
    print("Next Steps in KiCad PCB Editor:")
    print("  1. Open KiCad PCB Editor (pcbnew).")
    print("  2. Navigate to: Tools -> External Plugins -> Refresh Plugins.")
    print("  3. The 'OpenAuto EM Live Bridge' button will appear on your top toolbar.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Install OpenAuto EM Live KiCad Plugin")
    parser.add_argument("--dir", help="Explicit target directory for installation", default=None)
    parser.add_argument("--copy", action="store_true", help="Copy files instead of creating symlink")
    args = parser.parse_args()

    install_plugin(target_dir=args.dir, use_symlink=not args.copy)
