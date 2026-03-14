
def validate_parameters(params):
    """
    Validates the geometric parameters for the corkscrew filter to prevent
    generation of invalid or self-intersecting geometry.

    Args:
        params (dict): Dictionary of parameters (e.g., from LLM or config).

    Returns:
        tuple: (is_valid (bool), error_message (str or None))
    """
    try:
        # Extract parameters with defaults matching config.scad where appropriate
        # We only validate specific corkscrew parameters if they are present in the params dictionary.
        # This prevents validation from failing when running with a different configuration file.

        if "tube_od_mm" in params or "tube_wall_mm" in params:
            tube_od = float(params.get("tube_od_mm", 32))
            tube_wall = float(params.get("tube_wall_mm", 1.0))
            if tube_od <= 0 or tube_wall <= 0:
                return False, f"Tube dimensions must be positive. Got OD={tube_od}, Wall={tube_wall}"
        else:
            tube_od = None
            tube_wall = None

        if "helix_path_radius_mm" in params or "helix_profile_radius_mm" in params or "helix_void_profile_radius_mm" in params:
            path_r = float(params.get("helix_path_radius_mm", 1.8))
            profile_r = float(params.get("helix_profile_radius_mm", 1.8))
            void_r = float(params.get("helix_void_profile_radius_mm", 1.0))

            if path_r <= 0 or profile_r <= 0 or void_r <= 0:
                return False, f"Helix dimensions must be positive. Got Path={path_r}, Profile={profile_r}, Void={void_r}"

            # 2. Check for Self-Intersection at Center
            if profile_r >= path_r:
                return False, (
                    f"Invalid Geometry: Helix profile radius ({profile_r}mm) must be strictly less than "
                    f"helix path radius ({path_r}mm) to avoid center-axis singularity."
                )

            # 3. Check for Wall Thickness (Solid vs Void)
            tolerance_channel = 0.1
            effective_void_r = void_r + tolerance_channel

            if effective_void_r >= profile_r:
                 return False, (
                    f"Invalid Geometry: Effective void radius ({effective_void_r}mm) is >= Profile radius ({profile_r}mm). "
                    f"This results in zero or negative wall thickness (void_r={void_r} + tol={tolerance_channel})."
                )

            # 4. Check for Void Singularity
            if effective_void_r >= path_r:
                return False, (
                    f"Invalid Geometry: Effective void radius ({effective_void_r}mm) must be strictly less than "
                    f"helix path radius ({path_r}mm) to avoid void channel singularity."
                )

            # Check for Tube Fit if tube dimensions are also available
            if tube_od is not None and tube_wall is not None:
                tube_id_radius = (tube_od / 2.0) - tube_wall
                helix_outer_radius = path_r + profile_r

                if helix_outer_radius > tube_id_radius:
                     return False, (
                        f"Invalid Geometry: Helix outer radius ({helix_outer_radius:.2f}mm) exceeds "
                        f"tube inner radius ({tube_id_radius:.2f}mm). It will intersect the tube wall."
                    )

        # 5. Check Insert Length
        if "insert_length_mm" in params:
            length = float(params.get("insert_length_mm", 50))
            if length <= 0:
                 return False, f"Insert length must be positive. Got {length}"

        # 6. Cyclone / Manifold checks
        if "cyclone_diameter" in params and "vortex_finder_diameter" in params and "inlet_width" in params:
            cyclone_d = float(params.get("cyclone_diameter"))
            vf_d = float(params.get("vortex_finder_diameter"))
            inlet_w = float(params.get("inlet_width"))

            # The inner edge of the inlet must not intersect or touch the vortex finder
            # Inner edge radius = (cyclone_d / 2) - inlet_w
            # Vortex finder outer radius = vf_d / 2
            inner_inlet_r = (cyclone_d / 2.0) - inlet_w
            vf_r = vf_d / 2.0

            if inner_inlet_r <= vf_r:
                return False, (
                    f"Invalid Geometry: Inlet inner edge radius ({inner_inlet_r}mm) intersects or is coincident "
                    f"with the vortex finder outer radius ({vf_r}mm). This guarantees meshing failure."
                )

        return True, None

    except (ValueError, TypeError) as e:
        return False, f"Parameter type error: {e}"
