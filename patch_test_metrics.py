with open('test/test_foam_metrics.py', 'r') as f:
    content = f.read()

# The error occurs because FoamDriver maps self.case_dir to /dev/shm... but we need to ensure the directory is created if we are writing directly to it.
# We just need to make sure the case_dir exists before writing to the log_file.
# Or better, we can modify the setUp to just create self.driver.case_dir

new_setup = """    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.driver = FoamDriver(self.test_dir)
        os.makedirs(self.driver.case_dir, exist_ok=True)
        # Create dummy log file
        with open(self.driver.log_file, 'w') as f:"""

content = content.replace("    def setUp(self):\n        self.test_dir = tempfile.mkdtemp()\n        self.driver = FoamDriver(self.test_dir)\n        # Create dummy log file\n        with open(self.driver.log_file, 'w') as f:", new_setup)

with open('test/test_foam_metrics.py', 'w') as f:
    f.write(content)
