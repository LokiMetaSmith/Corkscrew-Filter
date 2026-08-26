import os
import shutil
import build123d as b3d
from cad_driver_base import CadDriverBase
import cad_models

class Build123dDriver(CadDriverBase):
    def __init__(self, scad_file_path=None, fluid_volume_module="modular_filter_assembly", **kwargs):
        self.scad_file_path = scad_file_path or "corkscrew.scad"
        self.fluid_volume_module = fluid_volume_module
        self.use_native = False

    def _parse_params_file(self, params_file):
        """Helper to parse key=value lines from a scad parameters file if provided."""
        parsed = {}
        if not params_file or not os.path.exists(params_file):
            return parsed
        context = {}
        with open(params_file, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('//') or '=' not in line:
                    continue
                parts = line.split('=', 1)
                k = parts[0].strip()
                v = parts[1].strip()
                if '//' in v:
                    v = v.split('//')[0].strip()
                v = v.rstrip(';')

                val = v
                if v.lower() == 'true':
                    val = True
                elif v.lower() == 'false':
                    val = False
                else:
                    try:
                        val = float(v)
                    except ValueError:
                        try:
                            val = float(eval(v, {"__builtins__": None}, context))
                        except Exception:
                            val = v

                if isinstance(val, (int, float)):
                    context[k] = val
                parsed[k] = val
        return parsed

    def build_part_shape(self, params):
        """Selects and builds the build123d Solid shape based on model configuration."""
        part_name = params.get("part_to_generate", self.fluid_volume_module)
        scad_name = os.path.basename(self.scad_file_path) if self.scad_file_path else "corkscrew.scad"

        if scad_name == "dipole_antenna.scad":
            return cad_models.build_dipole_antenna(params)
        elif scad_name == "puck_antenna.scad":
            return cad_models.build_puck_antenna(params)
        elif scad_name == "trace_optimizer.scad":
            part = params.get("part", "all")
            return cad_models.build_trace_optimizer(params, part=part)
        elif scad_name == "cyclone_filter_manifold.scad":
            return cad_models.build_cyclone_manifold(params, part_to_generate=part_name)

        # Default Corkscrew filter parts
        if part_name == "inlet_cap":
            return cad_models.build_inlet_cap(params)
        elif part_name == "outlet_cap":
            return cad_models.build_outlet_cap(params)
        elif part_name == "cfd_wall":
            return cad_models.build_cfd_wall(params)
        elif part_name == "flat_end_screw":
            return cad_models.build_flat_end_screw(params)
        else:
            return cad_models.build_modular_filter_assembly(params)

    def generate_stl(self, params, output_path, log_file=None, params_file=None):
        """Builds geometry and exports to STL file."""
        run_params = params.copy()
        if params_file:
            parsed = self._parse_params_file(params_file)
            for k, v in parsed.items():
                if k not in run_params:
                    run_params[k] = v

        try:
            shape = self.build_part_shape(run_params)
            out_dir = os.path.dirname(output_path)
            if out_dir and not os.path.exists(out_dir):
                os.makedirs(out_dir, exist_ok=True)

            b3d.export_stl(shape, output_path)

            if log_file:
                with open(log_file, 'a') as f:
                    f.write(f"build123d generated STL successfully at {output_path}\n")

            gen_cfd = cad_models.get_param(run_params, "GENERATE_CFD_VOLUME", False)
            path_r = float(cad_models.get_param(run_params, "helix_path_radius_mm", 10.0))

            if gen_cfd:
                anchor = [path_r, 0.0, 0.0]
                if log_file:
                    with open(log_file, 'a') as f:
                        f.write(f"ECHO: \"MESH_ANCHOR=[{anchor[0]}, {anchor[1]}, {anchor[2]}]\"\n")
                return anchor
            return True

        except Exception as e:
            print(f"Build123d generation failed: {e}")
            if log_file:
                with open(log_file, 'a') as f:
                    f.write(f"Build123d generation failed: {e}\n")
            return False

    def generate_step(self, params, output_path, log_file=None, params_file=None):
        """Builds geometry and exports exact STEP CAD model."""
        run_params = params.copy()
        if params_file:
            parsed = self._parse_params_file(params_file)
            for k, v in parsed.items():
                if k not in run_params:
                    run_params[k] = v

        try:
            shape = self.build_part_shape(run_params)
            out_dir = os.path.dirname(output_path)
            if out_dir and not os.path.exists(out_dir):
                os.makedirs(out_dir, exist_ok=True)

            b3d.export_step(shape, output_path)
            return True
        except Exception as e:
            print(f"Build123d STEP generation failed: {e}")
            return False

    def generate_visualization(self, params, output_base, log_file=None, params_file=None):
        """Generates solid model STL."""
        stl_path = output_base + ".stl"
        vis_params = params.copy()
        vis_params["GENERATE_CFD_VOLUME"] = False
        vis_params["GENERATE_SLICE"] = False

        res = self.generate_stl(vis_params, stl_path, log_file=log_file, params_file=params_file)
        if res:
            return [stl_path]
        return []

    def generate_cfd_assets(self, params, output_dir, log_file=None, params_file=None):
        """Generates all STLs required for CFD: fluid, inlet, outlet, wall."""
        if not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)

        fluid_params = params.copy()
        fluid_params["GENERATE_CFD_VOLUME"] = True

        fluid_path = os.path.join(output_dir, "corkscrew_fluid.stl")
        mesh_anchor_result = self.generate_stl(fluid_params, fluid_path, log_file, params_file)
        if not mesh_anchor_result:
            print("Failed to generate fluid volume via build123d.")
            return None

        inlet_params = fluid_params.copy()
        inlet_params["part_to_generate"] = "inlet_cap"
        inlet_path = os.path.join(output_dir, "inlet.stl")
        if not self.generate_stl(inlet_params, inlet_path, log_file, params_file):
            print("Failed to generate inlet cap via build123d.")
            return None

        outlet_params = fluid_params.copy()
        outlet_params["part_to_generate"] = "outlet_cap"
        outlet_path = os.path.join(output_dir, "outlet.stl")
        if not self.generate_stl(outlet_params, outlet_path, log_file, params_file):
            print("Failed to generate outlet cap via build123d.")
            return None

        wall_params = fluid_params.copy()
        wall_params["part_to_generate"] = "cfd_wall"
        wall_path = os.path.join(output_dir, "wall.stl")
        if not self.generate_stl(wall_params, wall_path, log_file, params_file):
            print("Failed to generate CFD wall via build123d.")
            return None

        return {
            "fluid": fluid_path,
            "inlet": inlet_path,
            "outlet": outlet_path,
            "wall": wall_path,
            "mesh_anchor": mesh_anchor_result if isinstance(mesh_anchor_result, list) else None
        }

if __name__ == "__main__":
    driver = Build123dDriver()
    print("Build123dDriver initialized successfully.")
