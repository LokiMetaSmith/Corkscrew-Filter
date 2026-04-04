import re

with open('optimizer/foam_driver.py', 'r') as f:
    content = f.read()

backup_restore_methods = """
    def _backup_best_run(self):
        \"\"\"
        Backs up the current results as the best run so far.
        \"\"\"
        backup_dir = os.path.join(self.case_dir, "best_run_backup")
        if os.path.exists(backup_dir):
            shutil.rmtree(backup_dir)
        os.makedirs(backup_dir)

        # Backup 0 directory
        zero_dir = os.path.join(self.case_dir, "0")
        if os.path.exists(zero_dir):
            shutil.copytree(zero_dir, os.path.join(backup_dir, "0"))

        # Backup latest time directory
        dirs = [d for d in os.listdir(self.case_dir) if os.path.isdir(os.path.join(self.case_dir, d)) and d.replace('.', '', 1).isdigit() and d != "0"]
        if dirs:
            try:
                latest_time = max(dirs, key=float)
                shutil.copytree(os.path.join(self.case_dir, latest_time), os.path.join(backup_dir, latest_time))
            except ValueError:
                pass

        # Backup configs
        os.makedirs(os.path.join(backup_dir, "system"), exist_ok=True)
        os.makedirs(os.path.join(backup_dir, "constant"), exist_ok=True)

        for f in ["system/fvSchemes", "system/fvSolution", "constant/turbulenceProperties"]:
            src = os.path.join(self.case_dir, f)
            if os.path.exists(src):
                shutil.copy2(src, os.path.join(backup_dir, f))

    def _restore_best_run(self):
        \"\"\"
        Restores the results from the best run backup.
        \"\"\"
        backup_dir = os.path.join(self.case_dir, "best_run_backup")
        if not os.path.exists(backup_dir):
            return

        print("Restoring best run from backup...")

        # Clean current results
        self._clean_results()

        # Restore 0 directory
        zero_dir = os.path.join(self.case_dir, "0")
        if os.path.exists(zero_dir):
            shutil.rmtree(zero_dir)
        if os.path.exists(os.path.join(backup_dir, "0")):
            shutil.copytree(os.path.join(backup_dir, "0"), zero_dir)

        # Restore numeric time directories
        for d in os.listdir(backup_dir):
            if os.path.isdir(os.path.join(backup_dir, d)) and d.replace('.', '', 1).isdigit() and d != "0":
                shutil.copytree(os.path.join(backup_dir, d), os.path.join(self.case_dir, d))

        # Restore configs
        for f in ["system/fvSchemes", "system/fvSolution", "constant/turbulenceProperties"]:
            src = os.path.join(backup_dir, f)
            if os.path.exists(src):
                shutil.copy2(src, os.path.join(self.case_dir, f))

        # Clean up backup
        shutil.rmtree(backup_dir)
"""

# Insert methods before `def run_solver(`
content = content.replace("    def run_solver(self, log_file=None, mesh_scaled_for_memory=False, **kwargs):", backup_restore_methods + "\n    def run_solver(self, log_file=None, mesh_scaled_for_memory=False, **kwargs):")

with open('optimizer/foam_driver.py', 'w') as f:
    f.write(content)
