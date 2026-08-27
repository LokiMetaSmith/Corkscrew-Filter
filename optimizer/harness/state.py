import numpy as np
from typing import Dict, Any, List

class State:
    def __init__(self, geometry: Dict[str, float] = None, fluid: Dict[str, float] = None,
                 structural: Dict[str, float] = None, electromagnetic: Dict[str, float] = None):
        # S_t = [G, F, M, E]
        self.geometry = geometry or {}
        self.fluid = fluid or {}
        self.structural = structural or {}
        self.electromagnetic = electromagnetic or {}

    def to_dict(self) -> Dict[str, Dict[str, float]]:
        return {
            "geometry": self.geometry,
            "fluid": self.fluid,
            "structural": self.structural,
            "electromagnetic": self.electromagnetic
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'State':
        return cls(
            geometry=data.get("geometry", {}),
            fluid=data.get("fluid", {}),
            structural=data.get("structural", {}),
            electromagnetic=data.get("electromagnetic", {})
        )

    def to_flat_vector(self, keys_schema: Dict[str, List[str]]) -> np.ndarray:
        """
        Converts the state to a flat numpy vector based on a schema of keys.
        Missing keys are populated with 0.0 to ensure consistent length.
        """
        vector = []
        for domain in ["geometry", "fluid", "structural", "electromagnetic"]:
            domain_dict = getattr(self, domain, {})
            for key in keys_schema.get(domain, []):
                vector.append(float(domain_dict.get(key, 0.0)))
        return np.array(vector, dtype=float)

class Action:
    def __init__(self, mutations: Dict[str, float] = None):
        self.mutations = mutations or {}

    def to_dict(self) -> Dict[str, float]:
        return self.mutations

    @classmethod
    def from_dict(cls, data: Dict[str, float]) -> 'Action':
        return cls(mutations=data)


def compute_state_distance(s1: State, s2: State, keys_schema: Dict[str, List[str]] = None) -> float:
    """
    Computes the normalized Euclidean distance between two State objects.
    """
    if keys_schema is None:
        # Build default schema based on keys present in both states
        keys_schema = {}
        for domain in ["geometry", "fluid", "structural", "electromagnetic"]:
            d1 = getattr(s1, domain, {})
            d2 = getattr(s2, domain, {})
            keys_schema[domain] = list(set(d1.keys()) | set(d2.keys()))

    v1 = s1.to_flat_vector(keys_schema)
    v2 = s2.to_flat_vector(keys_schema)

    if len(v1) == 0:
        return 0.0

    # Avoid divide-by-zero or scaling skew by using simple Euclidean distance
    # option: normalized by max of absolute values or simple L2 norm
    dist = np.linalg.norm(v1 - v2)
    return float(dist)


def parse_solver_outputs_to_state(params: Dict[str, Any], metrics: Dict[str, Any]) -> State:
    """
    Parses parameters and solver metrics into a structured State representation.
    """
    # Extract G: geometry parameters
    geometry_keys = [
        "tube_od_mm", "tube_wall_mm", "cyclone_diameter", "vortex_finder_diameter",
        "inlet_width", "helix_path_radius_mm", "helix_profile_radius_mm",
        "helix_void_profile_radius_mm", "slit_axial_length_mm", "slit_chamfer_height",
        "filter_height_mm", "number_of_complete_revolutions", "screw_OD_mm",
        "screw_ID_mm", "num_screws", "num_bins", "blade_chamfer_mm", "inlet_fillet_radius_mm"
    ]
    geometry = {}
    for k in geometry_keys:
        if k in params:
            geometry[k] = float(params[k])

    # Extract F: fluid parameters
    fluid_keys = ["delta_p", "drag_coefficient", "lift_coefficient", "separation_efficiency", "pressure_drop", "residuals"]
    fluid = {}
    for k in fluid_keys:
        if k in metrics:
            fluid[k] = float(metrics[k])
        # Check alternative common names
        elif k == "pressure_drop" and "delta_p" in metrics:
            fluid[k] = float(metrics["delta_p"])

    # Extract M: structural parameters
    structural_keys = ["max_von_mises_stress_MPa", "max_displacement_mm", "total_mass_g", "factor_of_safety"]
    structural = {}
    for k in structural_keys:
        if k in metrics:
            structural[k] = float(metrics[k])

    # Extract E: electromagnetic parameters
    em_keys = ["S11", "gain", "resonance_efficiency", "signal_attenuation", "field_intensity"]
    electromagnetic = {}
    for k in em_keys:
        if k in metrics:
            electromagnetic[k] = float(metrics[k])

    return State(geometry=geometry, fluid=fluid, structural=structural, electromagnetic=electromagnetic)
