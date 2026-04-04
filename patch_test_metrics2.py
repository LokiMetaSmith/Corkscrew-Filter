with open('test/test_foam_metrics.py', 'r') as f:
    content = f.read()

# The test writes to `self.test_dir` but FoamDriver uses `self.driver.case_dir` (which points to /dev/shm...).
# So `pp_dir` should be created inside `self.driver.case_dir`.

content = content.replace('pp_dir = os.path.join(self.test_dir, "postProcessing"', 'pp_dir = os.path.join(self.driver.case_dir, "postProcessing"')

with open('test/test_foam_metrics.py', 'w') as f:
    f.write(content)
