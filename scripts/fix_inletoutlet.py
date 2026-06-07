with open("optimizer/foam_driver.py", "r") as f:
    content = f.read()

old_code = """                    if field in ['k', 'epsilon', 'omega', 'nut'] and "type            calculated;" in block_content:
                        default_val = '1e-7' if field == 'nut' else '1e-6'
                        blocks[patch_name] = f"type            inletOutlet;\\n        inletValue      uniform {default_val};\\n        value           uniform {default_val};\""""

new_code = """                    if field in ['k', 'epsilon', 'omega', 'nut'] and ("type            calculated;" in block_content or "type            zeroGradient;" in block_content):
                        default_val = '1e-7' if field == 'nut' else '1e-6'
                        blocks[patch_name] = f"type            inletOutlet;\\n        inletValue      uniform {default_val};\\n        value           uniform {default_val};\""""

if old_code in content:
    content = content.replace(old_code, new_code)
    with open("optimizer/foam_driver.py", "w") as f:
        f.write(content)
    print("Successfully replaced.")
else:
    print("Old code not found.")
