const { stl2png } = require('@scalenc/stl-to-png');
const fs = require('fs');
const { execSync } = require('child_process');
const path = require('path');

const STL_FILE = 'barb_test.stl';
const PNG_FILE = 'barb_test.png';
const SCAD_FILE = 'test_barb_refactor.scad';

async function main() {
    console.log("Starting verification...");

    // 1. Generate STL
    console.log(`Generating ${STL_FILE} from ${SCAD_FILE}...`);
    try {
        // Use reduced resolution ($fn=20) for speed during verification
        execSync(`node export.js -o ${STL_FILE} ${SCAD_FILE} -D '$fn=20'`, { stdio: 'inherit' });
    } catch (e) {
        console.error("Failed to generate STL via export.js");
        process.exit(1);
    }

    if (!fs.existsSync(STL_FILE)) {
        console.error("STL file was not created.");
        process.exit(1);
    }

    // 2. Convert to PNG
    console.log(`Converting ${STL_FILE} to ${PNG_FILE}...`);
    try {
        const stlData = fs.readFileSync(STL_FILE);
        const pngData = await stl2png(stlData, { width: 800, height: 600 });
        fs.writeFileSync(PNG_FILE, pngData);
        console.log(`PNG created at ${PNG_FILE}`);
    } catch (e) {
        console.error("Failed to convert STL to PNG:", e);
        process.exit(1);
    }
}

main();
