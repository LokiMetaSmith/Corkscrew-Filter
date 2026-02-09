import json
import os
import uuid
import datetime
from typing import Dict, List, Any
try:
    from scoring import calculate_score
except ImportError:
    # Fallback for when running directly or in tests without full path
    try:
        from optimizer.scoring import calculate_score
    except ImportError:
        # Define a dummy calculate_score if import fails (should not happen in prod)
        def calculate_score(metrics): return (0, 0, 0)

class DataStore:
    def __init__(self, log_file="optimization_log.jsonl"):
        self.log_file = log_file

    def append_result(self, result: Dict[str, Any]):
        """
        Appends a result record to the JSONL log file.
        Validates the schema before writing.
        """
        # Ensure required fields
        if "id" not in result:
            result["id"] = str(uuid.uuid4())
        if "timestamp" not in result:
            result["timestamp"] = datetime.datetime.now(datetime.timezone.utc).isoformat()

        # Mandatory fields
        required_fields = ["id", "timestamp", "status", "parameters"]
        for field in required_fields:
            if field not in result:
                raise ValueError(f"Missing required field: {field}")

        # Explicit validation for parameters
        if not isinstance(result["parameters"], dict) or not result["parameters"]:
            raise ValueError("Invalid parameters: must be a non-empty dictionary.")

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

    def get_top_runs(self, n: int = 10) -> List[Dict[str, Any]]:
        """
        Returns the top N runs based on the scoring criteria defined in scoring.py.
        """
        history = self.load_history()
        # Sort using the calculate_score function (descending order for 'best')
        sorted_runs = sorted(history, key=lambda r: calculate_score(r.get("metrics", {})), reverse=True)
        return sorted_runs[:n]

    def clean_artifacts(self, keep_runs: List[Dict[str, Any]]):
        """
        Deletes STL and image files for runs that are NOT in the keep_runs list.
        Args:
            keep_runs: List of run dictionaries that should be preserved.
        """
        # Create a set of IDs to keep for faster lookup
        keep_ids = {r.get("id") for r in keep_runs if "id" in r}

        history = self.load_history()

        deleted_count = 0

        for run in history:
            run_id = run.get("id")
            if run_id in keep_ids:
                continue

            # This run is not in the top N, so we should delete its artifacts
            # Check for 'output_stl' or derive filename if standard
            # Check for 'images' list

            # 1. Delete Images
            images = run.get("images", [])
            if images:
                for img_path in images:
                    if os.path.exists(img_path):
                        try:
                            os.remove(img_path)
                            deleted_count += 1
                        except OSError as e:
                            print(f"Warning: Failed to delete {img_path}: {e}")

            # 2. Delete STLs
            # STLs might not be explicitly listed in the run dict if they use a standard name.
            # However, main.py passes 'output_stl' name.
            # If main.py renames the STL to include ID/iteration, we need that path.
            # Currently main.py overwrites 'corkscrew_fluid.stl' unless we change it.
            # TODO: If we want to keep top 10 STLs, main.py MUST be saving unique STLs per run.
            # If main.py is overwriting, then only the last one exists anyway.
            # Assumption: main.py will be updated to save unique filenames for artifacts.

            stl_path = run.get("artifact_stl_path")
            if stl_path and os.path.exists(stl_path):
                try:
                    os.remove(stl_path)
                    deleted_count += 1
                except OSError as e:
                    print(f"Warning: Failed to delete {stl_path}: {e}")

        if deleted_count > 0:
            print(f"Cleanup: Deleted {deleted_count} artifact files from non-top runs.")

if __name__ == "__main__":
    # Test stub
    store = DataStore("test_log.jsonl")
    try:
        # Should fail
        store.append_result({
            "status": "fail_test"
        })
    except ValueError as e:
        print(f"Caught expected error: {e}")

    try:
        # Should succeed
        store.append_result({
            "status": "success_test",
            "parameters": {"a": 1}
        })
        print("Success test passed.")
    except Exception as e:
        print(f"Unexpected error: {e}")

    if os.path.exists("test_log.jsonl"):
        os.remove("test_log.jsonl")
