import subprocess
import sys
import time
import os
import datetime
import threading

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
    Runs a command, streaming output to a log file with timestamps, while showing a spinner on the console.
    """
    # Ensure directory for log file exists
    log_dir = os.path.dirname(log_file_path)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)

    # Use a thread to read output and write to log
    # We open the file in append mode.
    # Note: process.stdout will be text mode (text=True)

    with open(log_file_path, "a") as log_f:
        timestamp = datetime.datetime.now().strftime("[%Y-%m-%d %H:%M:%S] ")
        log_f.write(f"\n{timestamp}# Executing: {' '.join(cmd)}\n")
        log_f.flush()

        try:
            process = subprocess.Popen(
                cmd,
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1 # Line buffered
            )
        except FileNotFoundError:
             # If executable not found
             sys.stdout.write(f"\rError: Executable '{cmd[0]}' not found.\n")
             raise

        # Thread function to read from stdout and write to log
        def log_reader(proc, file_handle):
            try:
                for line in proc.stdout:
                    timestamp = datetime.datetime.now().strftime("[%Y-%m-%d %H:%M:%S] ")
                    file_handle.write(f"{timestamp}{line}")
                    file_handle.flush()
            except Exception as e:
                file_handle.write(f"\nError reading output: {e}\n")

        reader_thread = threading.Thread(target=log_reader, args=(process, log_f))
        reader_thread.start()

        spinner = ["|", "/", "-", "\\"]
        idx = 0

        try:
            while process.poll() is None:
                sys.stdout.write(f"\r{spinner[idx]} {description}...")
                sys.stdout.flush()
                idx = (idx + 1) % len(spinner)
                time.sleep(0.1)

            # Wait for reader to finish processing remaining output
            reader_thread.join()

            # Clear spinner line
            sys.stdout.write(f"\r{' ' * (len(description) + 20)}\r")
            sys.stdout.flush()

            if process.returncode != 0:
                # We don't print Error here to let caller handle it, but we can hint
                # Caller usually catches CalledProcessError
                raise subprocess.CalledProcessError(process.returncode, cmd)

        except KeyboardInterrupt:
            process.kill()
            reader_thread.join()
            sys.stdout.write("\nProcess interrupted by user.\n")
            raise
