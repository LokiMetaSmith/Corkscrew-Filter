import json
import os
import uuid
import datetime
from typing import Dict, List, Any

class DataStore:
    def __init__(self, log_file="optimization_log.jsonl"):
        self.log_file = log_file

    def append_result(self, result: Dict[str, Any]):
        """
        Appends a result record to the JSONL log file.
        Validates the schema before writing.
        """
        # Ensure required fields
        required_fields = ["id", "timestamp", "status", "parameters"]
        for field in required_fields:
            if field not in result:
                # If missing, try to populate defaults or raise error
                if field == "id":
                    result["id"] = str(uuid.uuid4())
                elif field == "timestamp":
                    result["timestamp"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
                else:
                    raise ValueError(f"Missing required field: {field}")

        # Write to file
        with open(self.log_file, "a") as f:
            f.write(json.dumps(result) + "\n")

    def load_history(self) -> List[Dict[str, Any]]:
        """
        Loads the full history from the JSONL log file.
        Returns a list of dictionaries.
        """
        history = []
        if not os.path.exists(self.log_file):
            return history

        with open(self.log_file, "r") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        history.append(json.loads(line))
                    except json.JSONDecodeError:
                        print(f"Warning: Skipping invalid JSON line in {self.log_file}")
                        continue
        return history

if __name__ == "__main__":
    # Test stub
    store = DataStore("test_log.jsonl")
    store.append_result({
        "status": "test",
        "parameters": {"a": 1}
    })
    print(store.load_history())
    if os.path.exists("test_log.jsonl"):
        os.remove("test_log.jsonl")
