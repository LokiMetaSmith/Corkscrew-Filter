import pytest
import tempfile
import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'optimizer'))
from physics_factory import PhysicsEngineFactory
from foam_driver import FoamDriver
from em_driver import OpenEMSDriver
from fea_driver import FeaDriver
from joint_driver import JointPhysicsDriver

def test_physics_factory_cfd():
    with tempfile.TemporaryDirectory() as td:
        driver = PhysicsEngineFactory.get_driver(td, {'physics': {'type': 'cfd'}})
        assert isinstance(driver, FoamDriver)

def test_physics_factory_em():
    with tempfile.TemporaryDirectory() as td:
        driver = PhysicsEngineFactory.get_driver(td, {'physics': {'type': 'em'}})
        assert isinstance(driver, OpenEMSDriver)

def test_physics_factory_fea():
    with tempfile.TemporaryDirectory() as td:
        driver = PhysicsEngineFactory.get_driver(td, {'physics': {'type': 'fea'}})
        assert isinstance(driver, FeaDriver)

def test_physics_factory_joint():
    with tempfile.TemporaryDirectory() as td:
        driver = PhysicsEngineFactory.get_driver(td, {'physics': {'type': 'joint'}})
        assert isinstance(driver, JointPhysicsDriver)

def test_physics_factory_invalid():
    with tempfile.TemporaryDirectory() as td:
        with pytest.raises(ValueError):
            PhysicsEngineFactory.get_driver(td, {'physics': {'type': 'invalid_type'}})
