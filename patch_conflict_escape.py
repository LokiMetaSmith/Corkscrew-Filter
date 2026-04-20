with open("optimizer/foam_driver.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if "/*--------------------------------*- C++ -*----------------------------------*\\" in line:
        continue
    if "| \\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox           |" in line:
        lines[i] = "| \\\\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox           |\n"
    if "|  \\    /   O peration     | Version:  v2512                                 |" in line:
        lines[i] = "|  \\\\    /   O peration     | Version:  v2512                                 |\n"
    if "|   \\  /    A nd           | Website:  www.openfoam.com                      |" in line:
        lines[i] = "|   \\\\  /    A nd           | Website:  www.openfoam.com                      |\n"
    if "|    \\/     M anipulation  |                                                 |" in line:
        lines[i] = "|    \\\\/     M anipulation  |                                                 |\n"
    if "\\*---------------------------------------------------------------------------*/" in line:
        lines[i] = "\\\\*---------------------------------------------------------------------------*/\n"

with open("optimizer/foam_driver.py", "w", encoding="utf-8") as f:
    f.writelines(lines)
