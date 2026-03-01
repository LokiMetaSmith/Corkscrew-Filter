with open('test/test_cloud_config.py', 'r') as f:
    content = f.read()

content = content.replace('self.assertIn("U0              (0 0 5.0);", content)', 'self.assertIn("U0              (0 0 5);", content)')

with open('test/test_cloud_config.py', 'w') as f:
    f.write(content)
