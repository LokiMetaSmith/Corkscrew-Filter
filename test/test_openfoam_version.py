import pytest
import sys
import os

sys.path.append(os.path.abspath("optimizer"))
from check_openfoam import parse_openfoam_version

def test_parse_openfoam_version():
    assert parse_openfoam_version("Version: v2512") == 2512
    assert parse_openfoam_version("Version: 2206") == 2206
    assert parse_openfoam_version("OPENFOAM=2206") == 2206
    assert parse_openfoam_version("OPENFOAM=v2206") == 2206
    assert parse_openfoam_version("WM_PROJECT_VERSION=v2512") == 2512
    assert parse_openfoam_version("v2406") == 2406
    assert parse_openfoam_version("Some random output with v2312 embedded") == 2312
    assert parse_openfoam_version("No version here") is None
