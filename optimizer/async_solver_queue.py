"""
async_solver_queue.py

Asynchronous Non-Blocking Simulation Queue and Worker Pool.
Enables real-time surrogate responsiveness while heavy CFD/FEA solvers
run in the background. Completed jobs trigger automatic callbacks and surrogate refitting.
"""

import os
import time
import uuid
import threading
from concurrent.futures import ThreadPoolExecutor, Future
from typing import Dict, Any, List, Optional, Callable, Tuple
import numpy as np


class SimulationJob:
    """Represents a single simulation task in the queue."""

    def __init__(self, job_id: str, params: Dict[str, float], domain: str = "cfd"):
        self.job_id = job_id
        self.params = params
        self.domain = domain
        self.status = "PENDING"  # PENDING, RUNNING, COMPLETED, FAILED
        self.submit_time = time.time()
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
        self.metrics: Dict[str, float] = {}
        self.field_data: Optional[Dict[str, np.ndarray]] = None
        self.error_message: Optional[str] = None
        self.duration_s: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "domain": self.domain,
            "status": self.status,
            "duration_s": round(self.duration_s, 2),
            "metrics": self.metrics,
            "error": self.error_message,
        }


class AsyncSolverQueue:
    """
    Manages non-blocking background execution of OpenFOAM, CalculiX, and OpenEMS drivers.
    """

    def __init__(
        self,
        max_workers: int = 2,
        on_job_completed: Optional[Callable[[SimulationJob], None]] = None,
        verbose: bool = True
    ):
        self.max_workers = max_workers
        self.on_job_completed = on_job_completed
        self.verbose = verbose

        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="SolverWorker")
        self._lock = threading.Lock()
        self._jobs: Dict[str, SimulationJob] = {}
        self._futures: Dict[str, Future] = {}
        self._completed_queue: List[SimulationJob] = []

    def submit_job(
        self,
        driver,
        params: Dict[str, float],
        domain: str = "cfd",
        mock: bool = False,
        field_extractor: Optional[Callable] = None
    ) -> str:
        """
        Submits a simulation job to the background queue without blocking.
        Returns unique job_id.
        """
        job_id = f"job_{int(time.time()*1000)}_{uuid.uuid4().hex[:6]}"
        job = SimulationJob(job_id=job_id, params=params, domain=domain)

        with self._lock:
            self._jobs[job_id] = job

        future = self._executor.submit(
            self._worker_execute,
            job=job,
            driver=driver,
            mock=mock,
            field_extractor=field_extractor
        )

        with self._lock:
            self._futures[job_id] = future

        if self.verbose:
            print(f"[AsyncQueue] Dispatched job {job_id} ({domain.upper()}) to background worker pool.")

        return job_id

    def _worker_execute(
        self,
        job: SimulationJob,
        driver,
        mock: bool,
        field_extractor: Optional[Callable]
    ):
        """Worker thread entry point."""
        job.status = "RUNNING"
        job.start_time = time.time()

        try:
            if not mock and driver is not None:
                driver.prepare_case(params=job.params)
                success = driver.run_solver()
                if success:
                    raw_m = driver.get_metrics()
                    for k, v in raw_m.items():
                        if isinstance(v, (int, float, np.number)) and np.isfinite(v):
                            job.metrics[k] = float(v)
                else:
                    job.error_message = "Driver run_solver failed"
            else:
                # Fast realistic synthetic output
                time.sleep(0.05)  # Simulate small non-zero solver latency
                if job.domain == "cfd":
                    n = job.params.get("number_of_complete_revolutions", 2.0)
                    r = job.params.get("helix_path_radius_mm", 1.8)
                    job.metrics = {
                        "delta_p": float(1500.0 + 800.0 * n + 120.0 * r),
                        "separation_efficiency": float(min(99.98, 88.0 + 3.5 * n - 1.5 * r)),
                        "residuals": 1.2e-4
                    }
                elif job.domain in ("fea", "structural"):
                    ch = job.params.get("blade_chamfer_mm", 0.5)
                    kt = max(1.1, 2.5 - ch * 0.8)
                    vm = 12.5 * kt
                    job.metrics = {
                        "max_von_mises_stress_MPa": float(round(vm, 2)),
                        "max_displacement_mm": float(round(0.08 / (1.0 + ch * 0.2), 3)),
                        "factor_of_safety": float(round(60.0 / vm, 2))
                    }
                else:
                    job.metrics = {"objective": 1.0}

            # Field extraction
            if field_extractor is not None:
                case_dir = getattr(driver, "case_dir", ".")
                job.field_data = field_extractor(case_dir, params=job.params)

            job.status = "COMPLETED"
        except Exception as e:
            job.status = "FAILED"
            job.error_message = str(e)

        job.end_time = time.time()
        job.duration_s = job.end_time - (job.start_time or job.submit_time)

        with self._lock:
            self._completed_queue.append(job)

        if self.verbose:
            print(f"[AsyncQueue] Completed job {job.job_id} ({job.domain.upper()}) in {job.duration_s:.2f}s with status '{job.status}'.")

        # Invoke callback if defined
        if self.on_job_completed:
            try:
                self.on_job_completed(job)
            except Exception as cb_err:
                print(f"[AsyncQueue] Callback warning: {cb_err}")

    def poll_completed(self) -> List[SimulationJob]:
        """
        Non-blocking check that retrieves and clears all jobs completed since last poll.
        """
        with self._lock:
            done = list(self._completed_queue)
            self._completed_queue.clear()
        return done

    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            job = self._jobs.get(job_id)
            return job.to_dict() if job else None

    def active_count(self) -> int:
        with self._lock:
            return sum(1 for j in self._jobs.values() if j.status in ("PENDING", "RUNNING"))

    def wait_all(self, timeout: Optional[float] = None):
        """Blocks until all running jobs have completed."""
        with self._lock:
            futures = list(self._futures.values())
        for f in futures:
            f.result(timeout=timeout)

    def shutdown(self):
        """Shuts down background worker pool cleanly."""
        self._executor.shutdown(wait=False)
