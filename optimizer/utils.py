import subprocess
import sys
import time
import os
import datetime
import threading
import json
import shutil

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

        import re

        # Object to share state between thread and main loop
        class ProgressState:
            def __init__(self):
                self.current_time = 0.0
                self.total_time = 0.0
                self.start_wall_time = time.time()
                self.is_openfoam = any("Foam" in arg or "Mesh" in arg or "topoSet" in arg or "createPatch" in arg for arg in cmd)

        state = ProgressState()

        # Try to parse endTime from controlDict if this looks like a solver
        if state.is_openfoam and cwd and any("Foam" in arg for arg in cmd):
            control_dict_path = os.path.join(cwd, "system", "controlDict")
            if os.path.exists(control_dict_path):
                try:
                    with open(control_dict_path, 'r') as f:
                        cd_content = f.read()
                        m = re.search(r"endTime\s+([\d\.\-\+e]+);", cd_content)
                        if m:
                            state.total_time = float(m.group(1))
                except Exception:
                    pass

        # Thread function to read from stdout and write to log
        def log_reader(proc, file_handle, state):
            try:
                for line in proc.stdout:
                    timestamp = datetime.datetime.now().strftime("[%Y-%m-%d %H:%M:%S] ")
                    file_handle.write(f"{timestamp}{line}")
                    file_handle.flush()

                    if state.is_openfoam:
                        m = re.match(r"^Time = ([\d\.]+)", line.strip())
                        if m:
                            try:
                                state.current_time = float(m.group(1))
                            except ValueError:
                                pass
            except Exception as e:
                file_handle.write(f"\nError reading output: {e}\n")

        reader_thread = threading.Thread(target=log_reader, args=(process, log_f, state))
        reader_thread.start()

        spinner = ["|", "/", "-", "\\"]
        idx = 0

        try:
            while process.poll() is None:
                if state.is_openfoam and state.total_time > 0 and state.current_time > 0:
                    elapsed = time.time() - state.start_wall_time
                    progress = state.current_time / state.total_time

                    if progress > 0.001 and progress < 1.0:
                        total_estimated = elapsed / progress
                        remaining = total_estimated - elapsed

                        mins, secs = divmod(int(remaining), 60)
                        hours, mins = divmod(mins, 60)

                        time_str = f"{hours:02d}:{mins:02d}:{secs:02d}" if hours > 0 else f"{mins:02d}:{secs:02d}"

                        progress_str = f" [{state.current_time:g}/{state.total_time:g} | Est. remaining: {time_str}]"
                        sys.stdout.write(f"\r{spinner[idx]} {description}{progress_str}" + " " * 10)
                    else:
                        progress_str = f" [{state.current_time:g}/{state.total_time:g}]"
                        sys.stdout.write(f"\r{spinner[idx]} {description}{progress_str}" + " " * 20)
                else:
                    sys.stdout.write(f"\r{spinner[idx]} {description}..." + " " * 30)

                sys.stdout.flush()
                idx = (idx + 1) % len(spinner)
                time.sleep(0.1)

            # Wait for reader to finish processing remaining output
            reader_thread.join()

            # Clear spinner line
            sys.stdout.write(f"\r{' ' * (len(description) + 60)}\r")
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

def get_container_memory_gb(container_tool=None):
    """
    Estimates the available memory for the container engine in GB.
    If container_tool is None (Native), returns host available memory.
    """
    try:
        import psutil
        # Use available memory for native execution (safer than total)
        mem_gb = psutil.virtual_memory().available / (1024**3)
    except ImportError:
        print("Warning: psutil not installed. Assuming 4GB RAM.")
        mem_gb = 4.0
    except Exception as e:
        print(f"Warning: Error getting host memory: {e}. Assuming 4GB.")
        mem_gb = 4.0

    if container_tool == "podman":
        try:
            # podman info --format json
            # Returns huge JSON. Look for host.memTotal
            result = subprocess.run(
                ["podman", "info", "--format", "json"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                info = json.loads(result.stdout)
                # Structure varies by version, but usually host -> memTotal (in bytes)
                mem_bytes = info.get("host", {}).get("memTotal")
                if mem_bytes:
                    mem_gb = float(mem_bytes) / (1024**3)
        except Exception as e:
            print(f"Warning: Failed to query Podman memory: {e}")

    elif container_tool == "docker":
        try:
            # docker info --format '{{.MemTotal}}'
            # Returns bytes, e.g. 8364236800
            result = subprocess.run(
                ["docker", "info", "--format", "{{.MemTotal}}"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                output = result.stdout.strip()
                # Sometimes output includes units or formatting? usually raw bytes if specified
                # If raw bytes, just int()
                if output.isdigit():
                    mem_bytes = int(output)
                    mem_gb = float(mem_bytes) / (1024**3)
        except Exception as e:
            print(f"Warning: Failed to query Docker memory: {e}")

    return mem_gb
