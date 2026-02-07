
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
        # Dimensions
        tube_od = float(params.get("tube_od_mm", 32))
        tube_wall = float(params.get("tube_wall_mm", 1.5))

        path_r = float(params.get("helix_path_radius_mm", 1.8))
        profile_r = float(params.get("helix_profile_radius_mm", 1.8))
        void_r = float(params.get("helix_void_profile_radius_mm", 1.0))

        # 1. Check for valid positive dimensions
        if tube_od <= 0 or tube_wall <= 0:
            return False, f"Tube dimensions must be positive. Got OD={tube_od}, Wall={tube_wall}"

        if path_r <= 0 or profile_r <= 0 or void_r <= 0:
            return False, f"Helix dimensions must be positive. Got Path={path_r}, Profile={profile_r}, Void={void_r}"

        # 2. Check for Self-Intersection at Center
        # The profile is centered at x=path_r. If profile_r > path_r, it crosses x=0.
        # When twisted, this creates a self-intersecting geometry.
        # Additionally, for WASM/CGAL stability, we strictly require profile_r < path_r
        # to avoid grazing contact singularities at x=0.
        if profile_r >= path_r:
            return False, (
                f"Invalid Geometry: Helix profile radius ({profile_r}mm) must be strictly less than "
                f"helix path radius ({path_r}mm) to avoid center-axis singularity."
            )

        # 3. Check for Wall Thickness (Solid vs Void)
        # We need some wall thickness.
        if void_r >= profile_r:
             return False, (
                f"Invalid Geometry: Void radius ({void_r}mm) is >= Profile radius ({profile_r}mm). "
                "This results in zero or negative wall thickness."
            )

        # 4. Check for Tube Fit
        # The outer radius of the helix is path_r + profile_r.
        # It must fit inside the tube inner radius (tube_od/2 - tube_wall).
        tube_id_radius = (tube_od / 2.0) - tube_wall
        helix_outer_radius = path_r + profile_r

        # Allow a small tolerance/clearance, but strictly it shouldn't be larger.
        # If it's larger, it intersects the tube.
        if helix_outer_radius > tube_id_radius:
             return False, (
                f"Invalid Geometry: Helix outer radius ({helix_outer_radius:.2f}mm) exceeds "
                f"tube inner radius ({tube_id_radius:.2f}mm). It will intersect the tube wall."
            )

        # 5. Check Insert Length
        length = float(params.get("insert_length_mm", 50))
        if length <= 0:
             return False, f"Insert length must be positive. Got {length}"

        return True, None

    except (ValueError, TypeError) as e:
        return False, f"Parameter type error: {e}"
