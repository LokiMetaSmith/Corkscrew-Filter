import subprocess
import sys
import time
import os

class Timer:
    def __init__(self, description=None):
        self.description = description
        self.start_time = None
        self.end_time = None
        self.duration = 0

    def __enter__(self):
        self.start_time = time.time()
        if self.description:
            print(f"Starting {self.description}...")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = time.time()
        self.duration = self.end_time - self.start_time
        if self.description:
            print(f"Finished {self.description} in {self.duration:.2f}s")

def run_command_with_spinner(cmd, log_file_path, cwd=None, description="Processing"):
    """
    Runs a command, streaming output to a log file, while showing a spinner on the console.
    """
    # Ensure directory for log file exists
    log_dir = os.path.dirname(log_file_path)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)

    with open(log_file_path, "a") as log_f:
        log_f.write(f"\n# Executing: {' '.join(cmd)}\n")
        log_f.flush()

        try:
            process = subprocess.Popen(
                cmd,
                cwd=cwd,
                stdout=log_f,
                stderr=subprocess.STDOUT
            )
        except FileNotFoundError:
             # If executable not found
             sys.stdout.write(f"\rError: Executable '{cmd[0]}' not found.\n")
             raise

        spinner = ["|", "/", "-", "\\"]
        idx = 0

        try:
            while process.poll() is None:
                sys.stdout.write(f"\r{spinner[idx]} {description}...")
                sys.stdout.flush()
                idx = (idx + 1) % len(spinner)
                time.sleep(0.1)

            # Clear spinner line
            sys.stdout.write(f"\r{' ' * (len(description) + 20)}\r")
            sys.stdout.flush()

            if process.returncode != 0:
                # We don't print Error here to let caller handle it, but we can hint
                # Caller usually catches CalledProcessError
                raise subprocess.CalledProcessError(process.returncode, cmd)

        except KeyboardInterrupt:
            process.kill()
            sys.stdout.write("\nProcess interrupted by user.\n")
            raise
