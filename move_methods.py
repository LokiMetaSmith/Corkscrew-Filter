import re

with open("optimizer/foam_driver.py", "r", encoding="utf-8") as f:
    content = f.read()

# 1. Extract everything after `print("FoamDriver initialized.")\n\n`
split_marker = "    print(\"FoamDriver initialized.\")\n\n"
parts = content.split(split_marker)

if len(parts) == 2:
    main_class_body = parts[0]
    appended_methods = parts[1]

    # The appended methods are indented by 4 spaces. We need to make sure they are placed right before the `if __name__ == "__main__":` block.
    # The `if __name__ == "__main__":` block should be at the very end of the file.

    # 2. Re-construct the file:
    # Everything up to `if __name__ == "__main__":` (which is at the end of parts[0])

    main_class_body = main_class_body.replace("if __name__ == \"__main__\":\n    driver = FoamDriver(\"corkscrewFilter\")\n", "")

    new_content = main_class_body.rstrip() + "\n\n" + appended_methods + "\n" + "if __name__ == \"__main__\":\n    driver = FoamDriver(\"corkscrewFilter\")\n    print(\"FoamDriver initialized.\")\n"

    with open("optimizer/foam_driver.py", "w", encoding="utf-8") as f:
        f.write(new_content)
    print("Methods moved inside the class.")
else:
    print("Could not split by FoamDriver initialized marker.")
