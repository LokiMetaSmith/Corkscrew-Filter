import os
import json
from typing import Dict, Any, List
from .state import State, Action

class Timeline:
    def __init__(self, filepath: str = "timeline.jsonl"):
        self.filepath = filepath

    def append_transition(self, start_state: State, action: Action, predicted_state: State, actual_state: State):
        """
        Appends a complete state transition to the append-only log.
        """
        entry = {
            "start_state": start_state.to_dict(),
            "action": action.to_dict(),
            "predicted_state": predicted_state.to_dict(),
            "actual_state": actual_state.to_dict()
        }

        # Ensure directory exists
        dir_name = os.path.dirname(self.filepath)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)

        with open(self.filepath, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def load_transitions(self) -> List[Dict[str, Any]]:
        """
        Loads all past transitions from the append-only log.
        """
        transitions = []
        if not os.path.exists(self.filepath):
            return transitions

        with open(self.filepath, "r") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        transitions.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        return transitions
