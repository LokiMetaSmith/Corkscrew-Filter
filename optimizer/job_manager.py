from typing import Dict, List, Any, Optional, Callable
import uuid
import random
from data_store import DataStore

class JobManager:
    def __init__(self, data_store: DataStore):
        self.store = data_store

    def create_job(self, parameters: Dict[str, Any]) -> str:
        """
        Creates a new job with 'queued' status.
        Returns the job ID.
        """
        job_id = str(uuid.uuid4())
        entry = {
            "id": job_id,
            "status": "queued",
            "parameters": parameters
        }
        self.store.append_result(entry)
        return job_id

    def claim_job(self, job_id: str, worker_id: str) -> bool:
        """
        Marks a job as 'running'.
        Returns True if successful (job was previously queued), False otherwise.
        """
        latest = self._get_job_state(job_id)
        if not latest or latest["status"] != "queued":
            print(f"Cannot claim job {job_id}: Status is '{latest.get('status') if latest else 'unknown'}'")
            return False

        entry = {
            "id": job_id,
            "status": "running",
            "worker_id": worker_id,
            "parameters": latest["parameters"] # Carry forward params
        }
        self.store.append_result(entry)
        return True

    def complete_job(self, job_id: str, metrics: Dict[str, Any]) -> bool:
        """
        Marks a job as 'completed' with results.
        """
        latest = self._get_job_state(job_id)
        if not latest:
            return False

        entry = {
            "id": job_id,
            "status": "completed",
            "parameters": latest["parameters"],
            "metrics": metrics
        }
        self.store.append_result(entry)
        return True

    def fail_job(self, job_id: str, error: str) -> bool:
        """
        Marks a job as 'failed'.
        """
        latest = self._get_job_state(job_id)
        if not latest:
            return False

        entry = {
            "id": job_id,
            "status": "failed",
            "parameters": latest["parameters"],
            "error": error
        }
        self.store.append_result(entry)
        return True

    def get_pending_jobs(self, filter_func: Optional[Callable[[Dict], bool]] = None) -> List[Dict[str, Any]]:
        """
        Returns a list of job objects (latest state) that are currently 'queued'.
        Optional filter_func accepts the job object and returns True to include it.
        """
        all_states = self._get_all_latest_states()
        pending = [job for job in all_states.values() if job["status"] == "queued"]

        if filter_func:
            pending = [job for job in pending if filter_func(job)]

        return pending

    def generate_jobs_from_region(self, param_ranges: Dict[str, Any], num_samples: int = 5) -> List[str]:
        """
        Generates jobs by random sampling from ranges.
        param_ranges: Dict where keys are param names and values are (min, max) tuples or lists.
                      Fixed values can be passed as non-tuples.
        """
        created_ids = []
        for _ in range(num_samples):
            params = {}
            for key, val in param_ranges.items():
                if isinstance(val, (tuple, list)) and len(val) == 2 and isinstance(val[0], (int, float)):
                    # Random sample
                    if isinstance(val[0], int) and isinstance(val[1], int):
                        params[key] = random.randint(val[0], val[1])
                    else:
                        params[key] = random.uniform(val[0], val[1])
                elif isinstance(val, list):
                    # Choice
                    params[key] = random.choice(val)
                else:
                    # Fixed value
                    params[key] = val

            created_ids.append(self.create_job(params))

        return created_ids

    def _get_all_latest_states(self) -> Dict[str, Dict[str, Any]]:
        """
        Reconstructs the latest state for all jobs from the append-only log.
        """
        history = self.store.load_history()
        latest_states = {}

        # History is likely chronological, but we can rely on timestamp if needed.
        # Since file is append-only, later entries override earlier ones.
        for entry in history:
            job_id = entry.get("id")
            if job_id:
                # If we already saw this ID, merge/overwrite.
                # Since we iterate start to end, this entry is newer (or same).
                # Ideally we check timestamps, but file order is a strong proxy here.
                latest_states[job_id] = entry

        return latest_states

    def _get_job_state(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Gets the latest state for a single job.
        """
        states = self._get_all_latest_states()
        return states.get(job_id)

if __name__ == "__main__":
    # Simple test
    print("JobManager module loaded.")
