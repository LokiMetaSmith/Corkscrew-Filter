import subprocess
import os

def run_git_cmd(args, check=True):
    """
    Runs a git command.
    """
    if os.environ.get("MOCK_GIT"):
        print(f"[MOCK] git {' '.join(args)}")
        # Simulate clean status for commit checks
        if "status" in args:
            return True, ""
        return True, "mock success"

    try:
        result = subprocess.run(
            ["git"] + args,
            check=check,
            capture_output=True,
            text=True
        )
        return True, result.stdout.strip()
    except subprocess.CalledProcessError as e:
        return False, e.stderr.strip()

def get_git_commit():
    """Returns the current git commit hash, appending (dirty) if changes exist."""
    success, commit = run_git_cmd(["rev-parse", "HEAD"])
    if not success:
        return "unknown"

    success, status = run_git_cmd(["status", "--porcelain"])
    if success and status:
        return f"{commit} (dirty)"
    return commit

def git_pull_rebase():
    """
    Runs git pull --rebase.
    Returns (success, message).
    """
    print("Syncing: git pull --rebase...")
    success, msg = run_git_cmd(["pull", "--rebase"])
    if not success:
        print(f"Git pull failed: {msg}")
        run_git_cmd(["rebase", "--abort"], check=False)
    return success, msg

def git_commit(filepaths, message):
    """
    Adds specific files and commits them.
    filepaths: list of strings.
    """
    if isinstance(filepaths, str):
        filepaths = [filepaths]

    # Add files
    success, msg = run_git_cmd(["add"] + filepaths)
    if not success:
        print(f"Git add failed: {msg}")
        return False

    # Commit
    success, msg = run_git_cmd(["commit", "-m", message])
    if not success:
        if "nothing to commit" in msg or "clean" in msg:
            print("Nothing to commit.")
            return True
        print(f"Git commit failed: {msg}")
        return False

    return True

def git_push_with_retry(max_retries=3):
    """
    Attempts to push changes. If it fails (non-fast-forward),
    it pulls (rebase) and tries again.
    """
    for i in range(max_retries):
        print(f"Pushing attempt {i+1}/{max_retries}...")
        success, msg = run_git_cmd(["push"])
        if success:
            print("Push successful.")
            return True

        print(f"Push failed: {msg}")
        if "up-to-date" in msg:
            return True

        print("Pulling rebase to resolve...")
        success, msg = git_pull_rebase()
        if not success:
            print("Rebase failed during push retry. Aborting.")
            return False

    print("Max retries reached for git push.")
    return False
