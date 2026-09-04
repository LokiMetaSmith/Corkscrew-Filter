from typing import Dict, List, Any, Optional, Callable
import uuid
import random
import numpy as np
from data_store import DataStore

import threading

class JobManager:
    def __init__(self, data_store: DataStore):
        self.store = data_store
        self._lock = threading.Lock()

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
        with self._lock:
            self.store.append_result(entry)
        return job_id

    def verify_claim_leadership(self, job_id: str, worker_id: str) -> bool:
        """
        Verifies if the specified worker is the legitimate claimant of the job.
        Rule: The first 'running' entry determines the owner.
        """
        history = self.store.load_history()
        for event in history:
            if event.get("id") == job_id and event.get("status") == "running":
                return event.get("worker_id") == worker_id
        return False

    def claim_job(self, job_id: str, worker_id: str, timestamp: Optional[float] = None) -> bool:
        """
        Marks a job as 'running'.
        Returns True if successful (job was previously queued), False otherwise.
        """
        with self._lock:
            latest = self._get_job_state(job_id)
            if not latest or latest["status"] != "queued":
                return False

            import time
            entry = {
                "id": job_id,
                "status": "running",
                "worker_id": worker_id,
                "timestamp": timestamp if timestamp is not None else time.time(),
                "parameters": latest["parameters"] # Carry forward params
            }
            self.store.append_result(entry)
            return True

    def record_heartbeat(self, worker_id: str, job_id: Optional[str] = None):
        """
        Records a worker heartbeat entry in the append-only log.
        """
        import time
        now = time.time()
        entry = {
            "id": f"hb_{worker_id}_{int(now)}",
            "status": "heartbeat",
            "type": "heartbeat",
            "worker_id": worker_id,
            "job_id": job_id,
            "parameters": {"_heartbeat": True, "worker_id": worker_id},
            "timestamp": now
        }
        self.store.append_result(entry)

    def requeue_stale_jobs(self, stale_threshold_sec: float = 300.0) -> int:
        """
        Identifies running jobs whose worker heartbeat has timed out, and requeues them.
        Returns count of requeued jobs.
        """
        import time
        now = time.time()
        all_states = self._get_all_latest_states()

        # Build worker last active timestamp dictionary
        history = self.store.load_history()
        worker_last_active = {}
        for entry in history:
            w_id = entry.get("worker_id")
            ts_raw = entry.get("timestamp")
            try:
                ts = float(ts_raw) if ts_raw is not None else now
            except (ValueError, TypeError):
                ts = now
            if w_id:
                worker_last_active[w_id] = max(worker_last_active.get(w_id, 0.0), ts)

        requeued_count = 0
        for job_id, job in all_states.items():
            if job.get("status") == "running":
                w_id = job.get("worker_id")
                last_active = worker_last_active.get(w_id, 0.0)
                if (now - last_active) >= stale_threshold_sec:
                    # Worker timed out - requeue job
                    entry = {
                        "id": job_id,
                        "status": "queued",
                        "parameters": job.get("parameters", {}),
                        "requeued_from": w_id
                    }
                    self.store.append_result(entry)
                    requeued_count += 1
        return requeued_count

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
                if isinstance(val, tuple) and len(val) == 2 and isinstance(val[0], (int, float)):
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
            if job_id and entry.get("type") != "heartbeat" and not str(job_id).startswith("hb_"):
                latest_states[job_id] = entry

        return latest_states

    def claim_next_job(self, worker_id: str, filter_func: Optional[Callable[[Dict], bool]] = None) -> Optional[Dict[str, Any]]:
        """
        Atomically finds and claims the next available queued job.
        Returns the claimed job object, or None if no jobs are available or race was lost.
        """
        with self._lock:
            pending = self.get_pending_jobs(filter_func=filter_func)
            for job in pending:
                job_id = job["id"]
                latest = self._get_job_state(job_id)
                if latest and latest.get("status") == "queued":
                    import time
                    entry = {
                        "id": job_id,
                        "status": "running",
                        "worker_id": worker_id,
                        "timestamp": time.time(),
                        "parameters": latest["parameters"]
                    }
                    self.store.append_result(entry)
                    return self._get_job_state(job_id)
            return None

    def sync_surrogate_from_completed_jobs(self, surrogate: Any) -> int:
        """
        Synchronizes an in-memory MultiPhysicsSurrogate with all completed jobs
        from the distributed log and refits the surrogate.
        Returns number of newly added samples.
        """
        all_states = self._get_all_latest_states()
        completed_jobs = [j for j in all_states.values() if j.get("status") == "completed"]

        added_count = 0
        existing_params = [p.tolist() if hasattr(p, "tolist") else list(p) for p in getattr(surrogate, "param_history", [])]

        for job in completed_jobs:
            params = job.get("parameters", {})
            metrics = job.get("metrics", {})
            if not params or not metrics:
                continue

            # Check if already in surrogate
            p_vec = surrogate._extract_param_vector(params) if hasattr(surrogate, "_extract_param_vector") else list(params.values())
            p_list = p_vec.tolist() if hasattr(p_vec, "tolist") else list(p_vec)

            is_duplicate = False
            for ep in existing_params:
                if len(ep) == len(p_list) and np.allclose(ep, p_list, atol=1e-5):
                    is_duplicate = True
                    break

            if not is_duplicate:
                surrogate.add_sample(params, metrics)
                existing_params.append(p_list)
                added_count += 1

        if added_count > 0 and hasattr(surrogate, "fit"):
            surrogate.fit()

        return added_count

    def _get_job_state(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Gets the latest state for a single job.
        """
        states = self._get_all_latest_states()
        return states.get(job_id)


if __name__ == "__main__":
    # Simple test
    print("JobManager module loaded.")
