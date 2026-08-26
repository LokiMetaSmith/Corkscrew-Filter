"""
cad_factory.py
Factory for creating CAD drivers (Build123dDriver vs ScadDriver).
"""

from scad_driver import ScadDriver
from build123d_driver import Build123dDriver

class CadEngineFactory:
    @staticmethod
    def get_driver(scad_file_path, cad_engine="build123d", fluid_volume_module="modular_filter_assembly", force_native=False):
        """
        Instantiates and returns the selected CAD driver.

        Args:
            scad_file_path (str): Path to CAD file or model identifier.
            cad_engine (str): 'build123d' or 'openscad' / 'scad'.
            fluid_volume_module (str): Name of fluid volume module / part.
            force_native (bool): Force native OpenSCAD CLI if using ScadDriver.

        Returns:
            CadDriverBase: Initialized CAD driver instance.
        """
        engine = str(cad_engine).lower().strip()
        if engine in ["build123d", "b3d", "python"]:
            return Build123dDriver(scad_file_path=scad_file_path, fluid_volume_module=fluid_volume_module)
        else:
            return ScadDriver(scad_file_path=scad_file_path, force_native=force_native, fluid_volume_module=fluid_volume_module)
