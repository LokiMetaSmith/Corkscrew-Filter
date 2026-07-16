import copy
from typing import Dict, Any, List, Tuple
from .state import State, Action
from .surrogate import SurrogateManager

class BFSPlanner:
    def __init__(self, surrogate_manager: SurrogateManager, parameter_defs: Dict[str, Any]):
        self.surrogate_manager = surrogate_manager
        self.parameter_defs = parameter_defs

    def _get_allowed_mutations(self) -> List[Dict[str, float]]:
        """
        Determines localized mutations for each active continuous or discrete parameter.
        """
        mutations_list = []
        # Support small set of representative mutations
        # e.g., widening, narrowing, thickening, thinning
        keys = [
            "helix_path_radius_mm",
            "helix_profile_radius_mm",
            "helix_void_profile_radius_mm",
            "tube_wall_mm"
        ]

        # Simple step options
        for key in keys:
            if key in self.parameter_defs:
                info = self.parameter_defs[key]
                if info.get('constant', False):
                    continue
                step_val = float(info.get('default', 1.0)) * 0.1
                if step_val == 0.0:
                    step_val = 0.5
                mutations_list.append({key: step_val})
                mutations_list.append({key: -step_val})

        # Fallback to general generic if none match
        if not mutations_list:
            for key, info in self.parameter_defs.items():
                if info.get('constant', False):
                    continue
                mutations_list.append({key: 0.1})
                mutations_list.append({key: -0.1})

        return mutations_list

    def search(self, start_state: State, score_func, max_depth: int = 4) -> Tuple[Action, State, float]:
        """
        Runs Breadth-First Search inside the fast virtual surrogate to discover
        the optimal mutation action that maximizes/minimizes the provided score_func.
        score_func takes a State object and returns a numeric score.
        """
        allowed_mutations = self._get_allowed_mutations()

        # Queue elements are (current_state, action_sequence, current_depth)
        queue = [(start_state, [], 0)]

        best_state = start_state
        best_action_seq = []
        best_score = score_func(start_state)

        visited = set()

        while queue:
            curr_state, action_seq, depth = queue.pop(0)

            # Evaluate current node
            curr_score = score_func(curr_state)
            if curr_score > best_score:
                best_score = curr_score
                best_state = curr_state
                best_action_seq = action_seq

            if depth >= max_depth:
                continue

            # Expand kids
            for mut in allowed_mutations:
                # Build compound action
                act = Action(mutations=mut)
                try:
                    next_state = self.surrogate_manager.run_step(curr_state, act)

                    # Convert to stable state representation to avoid inf loops
                    geom_tuple = tuple(sorted((k, round(v, 4)) for k, v in next_state.geometry.items()))
                    if geom_tuple not in visited:
                        visited.add(geom_tuple)
                        queue.append((next_state, action_seq + [act], depth + 1))
                except Exception:
                    continue

        # Return first action in the path, the expected best state, and expected score
        if best_action_seq:
            return best_action_seq[0], best_state, best_score
        else:
            # No action found or best is starting state. Propose a small random mutation
            mut = allowed_mutations[0] if allowed_mutations else {"helix_path_radius_mm": 0.1}
            return Action(mutations=mut), start_state, best_score
