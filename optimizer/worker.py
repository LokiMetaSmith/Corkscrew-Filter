import argparse
import time
import os
import socket
import uuid
import sys
from job_manager import JobManager
from data_store import DataStore
from scad_driver import ScadDriver
from foam_driver import FoamDriver
from simulation_runner import run_simulation
from git_utils import git_pull_rebase, git_commit, git_push_with_retry, get_git_commit

def get_default_worker_id():
    hostname = socket.gethostname()
    uid = str(uuid.uuid4())[:8]
    return f"{hostname}-{uid}"

def verify_claim_leadership(store, job_id, worker_id):
    """
    Verifies if the specified worker is the legitimate claimant of the job.
    Rule: The first 'running' entry after 'queued' determines the owner.
    """
    history = store.load_history()

    # Filter for this job
    job_events = [e for e in history if e.get("id") == job_id]

    # Iterate through events to find the first valid claim
    # We assume file order is chronological
    for event in job_events:
        status = event.get("status")
        if status == "running":
            # Found the first claim
            owner = event.get("worker_id")
            if owner == worker_id:
                return True
            else:
                print(f"Job {job_id} was already claimed by {owner}. We lost the race.")
                return False

    # If we are here, we didn't find a running status?
    # That implies our write didn't make it, or something is wrong.
    print(f"No running status found for {job_id} after claim attempt.")
    return False

def main():
    parser = argparse.ArgumentParser(description="Distributed Optimization Worker")
    parser.add_argument("--loop", action="store_true", help="Run continuously until queue is empty")
    parser.add_argument("--id", type=str, default=None, help="Worker ID")
    parser.add_argument("--dry-run", action="store_true", help="Skip actual simulation execution")
    parser.add_argument("--scad-file", type=str, default="corkscrew.scad")
    parser.add_argument("--case-dir", type=str, default="corkscrewFilter")
    parser.add_argument("--poll-interval", type=int, default=10, help="Seconds to wait between polls in loop mode")
    args = parser.parse_args()

    worker_id = args.id if args.id else get_default_worker_id()
    print(f"Worker started with ID: {worker_id}")

    # Initialize components
    store = DataStore()
    manager = JobManager(store)
    scad = ScadDriver(args.scad_file)
    foam = FoamDriver(args.case_dir)

    while True:
        # 1. Sync
        print("\n--- Syncing with remote ---")
        success, msg = git_pull_rebase()
        if not success:
            print("Sync failed. Retrying in 10s...")
            time.sleep(10)
            continue

        # 2. Check Queue
        pending_jobs = manager.get_pending_jobs()
        if not pending_jobs:
            print("No queued jobs found.")
            if args.loop:
                time.sleep(args.poll_interval)
                continue
            else:
                break

        # 3. Claim Job
        target_job = pending_jobs[0]
        job_id = target_job["id"]
        print(f"Attempting to claim Job {job_id}...")

        manager.claim_job(job_id, worker_id)

        # Commit Claim
        if not git_commit("optimization_log.jsonl", f"Worker {worker_id} claims job {job_id}"):
            print("Failed to commit claim. Retrying loop.")
            continue

        # Push Claim
        if not git_push_with_retry():
            print("Failed to push claim. Retrying loop (pull will happen next).")
            continue

        # 4. Verify Claim (Did we win?)
        # Read the file from disk (which has merged content now)
        if not verify_claim_leadership(store, job_id, worker_id):
            print("Claim verification failed. Dropping job.")
            continue

        print(f"Claim verified. Executing Job {job_id}...")

        # 5. Run Simulation
        params = target_job["parameters"]
        output_prefix = os.path.join("exports", f"job_{job_id}")

        try:
            # Unpack all 5 return values
            metrics, png_paths, solid_stl, fluid_stl, vtk_zip = run_simulation(
                scad, foam, params,
                output_stl_name="corkscrew_fluid.stl", # Standard name for Foam
                dry_run=args.dry_run,
                output_prefix=output_prefix
            )

            # Check for critical failures in metrics
            if metrics.get("error"):
                print(f"Job failed with error: {metrics['error']}")
                manager.fail_job(job_id, metrics['error'])
            else:
                print("Job completed successfully.")
                manager.complete_job(job_id, metrics)

        except Exception as e:
            print(f"Unexpected error during simulation: {e}")
            manager.fail_job(job_id, str(e))

        # 6. Commit Results
        # If we failed, we still record the fail status.
        commit_msg = f"Worker {worker_id} completed job {job_id}"
        if not git_commit("optimization_log.jsonl", commit_msg):
            print("Failed to commit results. Leaving local changes.")
            # If we fail here, the job is completed locally but not on remote.
            # Next loop will pull.
            # If we don't push, others won't see it.
            # We should try to push.

        if not git_push_with_retry():
            print("Failed to push results. Please check git status.")
            # If push fails after retries, we are in a tough spot.
            # But the loop continues.

        if not args.loop:
            break

    print("Worker finished.")

if __name__ == "__main__":
    main()
