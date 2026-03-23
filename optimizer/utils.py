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

def run_command_with_spinner(cmd, log_file_path, cwd=None, description="Processing", timeout=None):
    """
    Runs a command, streaming output to a log file with timestamps, while showing a spinner on the console.
    Includes an optional timeout (in seconds) that will forcefully terminate the process.
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
                self.is_meshing = any("snappyHexMesh" in arg for arg in cmd)
                self.current_phase = ""
                self.phase_start_time = time.time()

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

                        if state.is_meshing:
                            phase_match = re.search(r"^(Refinement phase|Feature refinement iteration|Surface refinement iteration|Shell refinement iteration|Snapping phase|Morphing phase|Layer addition phase)", line.strip())
                            if phase_match:
                                new_phase = phase_match.group(1).strip()
                                # Handle cases like "Feature refinement iteration X"
                                iter_match = re.search(r"iteration (\d+)", line.strip())
                                if iter_match:
                                    new_phase += f" {iter_match.group(1)}"

                                if new_phase != state.current_phase:
                                    if state.current_phase:
                                        # When phase changes, print a newline so the previous phase's block progress remains on screen
                                        sys.stdout.write("\n")
                                    state.current_phase = new_phase
                                    state.phase_start_time = time.time()

            except ValueError:
                # File was closed by the main thread before the process finished.
                pass
            except Exception as e:
                try:
                    file_handle.write(f"\nError reading output: {e}\n")
                except ValueError:
                    pass

        reader_thread = threading.Thread(target=log_reader, args=(process, log_f, state))
        reader_thread.start()

        spinner = ["|", "/", "-", "\\"]
        idx = 0

        import shutil

        try:
            while process.poll() is None:
                elapsed_wall = time.time() - state.start_wall_time
                if timeout and elapsed_wall > timeout:
                    process.kill()
                    reader_thread.join()
                    sys.stdout.write(f"\nCommand timed out after {timeout} seconds: {' '.join(cmd)}\n")
                    log_f.write(f"\n[ERROR] Command timed out after {timeout} seconds.\n")
                    raise subprocess.TimeoutExpired(cmd, timeout)

                output_str = f"{spinner[idx]} {description}..."

                if state.is_openfoam and state.total_time > 0 and state.current_time > 0:
                    elapsed = elapsed_wall
                    progress = state.current_time / state.total_time

                    if progress > 0.001 and progress < 1.0:
                        total_estimated = elapsed / progress
                        remaining = total_estimated - elapsed

                        mins, secs = divmod(int(remaining), 60)
                        hours, mins = divmod(mins, 60)

                        time_str = f"{hours:02d}:{mins:02d}:{secs:02d}" if hours > 0 else f"{mins:02d}:{secs:02d}"

                        progress_str = f" [{state.current_time:g}/{state.total_time:g} | Est. remaining: {time_str}]"
                        output_str = f"{spinner[idx]} {description}{progress_str}"
                    else:
                        progress_str = f" [{state.current_time:g}/{state.total_time:g}]"
                        output_str = f"{spinner[idx]} {description}{progress_str}"
                elif state.is_meshing and state.current_phase:
                    # Meshing block characters representation
                    elapsed_phase = time.time() - state.phase_start_time

                    # 1 block per 2 seconds, cap at 30 blocks
                    interval = 2.0
                    max_blocks = 30

                    full_blocks = min(int(elapsed_phase / interval), max_blocks)
                    remainder = (elapsed_phase % interval) / interval

                    # Animation frames for the "filling" block
                    fill_chars = ["_", "▃", "▄", "▆", "█"]
                    fallback_chars = ["_", ".", "-", "=", "#"]

                    if full_blocks >= max_blocks:
                        blocks_str = "." * max_blocks
                        fallback_blocks_str = blocks_str
                    else:
                        # Determine which partial block to show based on the remainder
                        fill_idx = min(int(remainder * len(fill_chars)), len(fill_chars) - 1)
                        blocks_str = "." * full_blocks + fill_chars[fill_idx]
                        blocks_str = blocks_str.ljust(max_blocks, ' ')

                        fallback_idx = min(int(remainder * len(fallback_chars)), len(fallback_chars) - 1)
                        fallback_blocks_str = "." * full_blocks + fallback_chars[fallback_idx]
                        fallback_blocks_str = fallback_blocks_str.ljust(max_blocks, ' ')

                    # Also show elapsed time in seconds
                    time_str = f"{int(elapsed_phase)}s"
                    progress_str = f" [{state.current_phase}: {blocks_str} {time_str}]"
                    output_str = f"{spinner[idx]} {description}{progress_str}"

                    try:
                        encoding = sys.stdout.encoding or 'utf-8'
                        output_str.encode(encoding)
                    except UnicodeEncodeError:
                        progress_str = f" [{state.current_phase}: {fallback_blocks_str} {time_str}]"
                        output_str = f"{spinner[idx]} {description}{progress_str}"

                # Calculate terminal width and pad/truncate to exactly fit one line
                # Default to 80 if it can't be determined
                term_width = shutil.get_terminal_size((80, 20)).columns

                # We leave 1 char buffer to prevent implicit wrapping on exact width
                max_len = term_width - 1

                if len(output_str) > max_len:
                    output_str = output_str[:max_len-3] + "..."

                # Pad to overwrite any trailing characters from previous longer lines
                padded_output = output_str.ljust(max_len)

                sys.stdout.write(f"\r{padded_output}")
                sys.stdout.flush()

                idx = (idx + 1) % len(spinner)
                time.sleep(0.1)

            # Wait for reader to finish processing remaining output
            reader_thread.join()

            # Clear spinner line
            term_width = shutil.get_terminal_size((80, 20)).columns
            sys.stdout.write(f"\r{' ' * (term_width - 1)}\r")
            sys.stdout.flush()

            if process.returncode != 0:
                # We don't print Error here to let caller handle it, but we can hint
                # Caller usually catches CalledProcessError
                raise subprocess.CalledProcessError(process.returncode, cmd)

        except (Exception, KeyboardInterrupt) as e:
            # Catch all exceptions so we can safely kill the process and join the thread
            # before the file descriptor is closed.
            process.kill()
            try:
                reader_thread.join()
            except Exception:
                pass
            if isinstance(e, KeyboardInterrupt):
                sys.stdout.write("\nProcess interrupted by user.\n")
            elif not isinstance(e, (subprocess.CalledProcessError, subprocess.TimeoutExpired)):
                sys.stdout.write(f"\nUnexpected error executing {' '.join(cmd)}: {e}\n")
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

def safe_print(text: str):
    """
    Safely prints text containing emojis or special characters.
    Gracefully degrades to the terminal encoding if it (like cp1252 on Windows)
    does not support them, preventing UnicodeEncodeError crashes.
    """
    try:
        encoding = sys.stdout.encoding or 'utf-8'
        text.encode(encoding)
        print(text)
    except UnicodeEncodeError:
        # Strip characters that can't be encoded
        safe_text = text.encode(encoding, 'ignore').decode(encoding)
        print(safe_text)
