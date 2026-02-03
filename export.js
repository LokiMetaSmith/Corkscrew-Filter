const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');
const { stl2png } = require('@scalenc/stl-to-png');

const SCAD_WASM_IMPORT = async () => {
    try {
        const mod = await import('openscad-wasm');
        return mod.default || mod.createOpenSCAD || mod;
    } catch (e) {
        console.error("Error importing openscad-wasm:", e);
        process.exit(1);
    }
};

const LIB_DIR = 'BOSL2';
const CONFIGS_DIR = 'configs';
const OUTPUT_DIR = 'exports';

// Helper: Calculate rotated camera position (around Z axis)
function getRotatedCamera(angleDeg) {
    const defaultPos = [0, -25, 20];
    const rad = (angleDeg * Math.PI) / 180;
    const cos = Math.cos(rad);
    const sin = Math.sin(rad);

    // Rotate (x, y)
    const x = defaultPos[0];
    const y = defaultPos[1];

    // x' = x cos θ - y sin θ
    // y' = x sin θ + y cos θ
    const newX = x * cos - y * sin;
    const newY = x * sin + y * cos;

    return [newX, newY, defaultPos[2]];
}

// Helper: Generate 3 PNGs for a given STL
async function generatePngs(stlPath) {
    if (!fs.existsSync(stlPath)) {
        console.error(`  PNG Error: STL file not found: ${stlPath}`);
        return;
    }

    console.log(`  Generating PNGs for ${path.basename(stlPath)}...`);
    const stlData = fs.readFileSync(stlPath);
    const angles = [0, 120, 240];

    for (let i = 0; i < angles.length; i++) {
        const angle = angles[i];
        const camPos = getRotatedCamera(angle);
        const pngPath = stlPath.replace(/\.stl$/i, `_view${i}.png`);

        try {
            const pngData = stl2png(stlData, {
                width: 800,
                height: 600,
                cameraPosition: camPos
            });
            fs.writeFileSync(pngPath, pngData);
            console.log(`    Saved view ${i} (${angle}°): ${path.basename(pngPath)}`);
        } catch (e) {
            console.error(`    Failed to generate view ${i}: ${e.message}`);
        }
    }
}

async function main() {
    // 1. Ensure BOSL2 Library exists
    if (!fs.existsSync(LIB_DIR)) {
        console.log('BOSL2 library not found. Cloning...');
        try {
            execSync('git clone --depth 1 https://github.com/BOSL2/BOSL2.git ' + LIB_DIR, { stdio: 'inherit' });
            console.log('BOSL2 cloned successfully.');
        } catch (e) {
            console.error('Failed to clone BOSL2:', e.message);
            // Fallback logic
            console.log('Attempting alternative download (zip)...');
            try {
                execSync('curl -L -o bosl2.zip https://github.com/BelfrySCAD/BOSL2/archive/refs/heads/master.zip');
                execSync('unzip -q bosl2.zip');
                if (fs.existsSync(LIB_DIR)) {
                     fs.rmSync(LIB_DIR, { recursive: true, force: true });
                }
                fs.renameSync('BOSL2-master', LIB_DIR);
                fs.unlinkSync('bosl2.zip');
            } catch(e2) {
                console.error('Failed to download BOSL2 zip:', e2.message);
                process.exit(1);
            }
        }
    }

    // 2. Parse Arguments
    const args = process.argv.slice(2);
    let directMode = false;
    let outputDirect = '';
    let inputDirect = '';
    let globalParams = [];
    let generatePng = false;

    // Check for PNG flag
    if (args.includes('--png')) {
        generatePng = true;
    }

    // Check for Direct Mode (-o)
    if (args.includes('-o')) {
        directMode = true;
        const oIndex = args.indexOf('-o');
        if (oIndex + 1 < args.length) {
            outputDirect = args[oIndex + 1];
        } else {
            console.error("Error: -o requires an output filename.");
            process.exit(1);
        }
    }

    // Parse Parameters (-D)
    for (let i = 0; i < args.length; i++) {
         if (args[i] === '-D') {
             if (i + 1 < args.length) {
                 globalParams.push('-D');
                 globalParams.push(args[i+1]);
             }
         }
    }

    // Determine Input File (for Direct Mode)
    if (directMode) {
        for (let i = 0; i < args.length; i++) {
            if (args[i] === '-o') { i++; continue; }
            if (args[i] === '-D') { i++; continue; }
            if (args[i] === '--png') { continue; }
            if (!args[i].startsWith('-')) {
                inputDirect = args[i];
                break;
            }
        }
    }

    const createOpenSCAD = await SCAD_WASM_IMPORT();

    // Helper to load directories into VFS
    function loadDir(instance, localPath, virtualPath) {
        if (!fs.existsSync(localPath)) return;
        try { instance.FS.mkdir(virtualPath); } catch(e) {}
        const items = fs.readdirSync(localPath);
        for (const item of items) {
            const loc = path.join(localPath, item);
            const virt = virtualPath === '/' ? `/${item}` : `${virtualPath}/${item}`;
            const stat = fs.statSync(loc);
            if (stat.isDirectory()) {
                loadDir(instance, loc, virt);
            } else {
                instance.FS.writeFile(virt, fs.readFileSync(loc));
            }
        }
    }

    async function renderFile(inputFile, outputFile, params = []) {
        console.log(`Rendering ${inputFile} -> ${outputFile}...`);

        // Create fresh instance for each render to avoid memory issues/state pollution
        // IMPORTANT: Increased memory limit to 512MB to handle complex models (e.g. hose_adapter_cap)
        const wrapper = await createOpenSCAD({
            noInitialRun: true,
            print: (text) => console.log("SCAD stdout:", text),
            printErr: (text) => console.error("SCAD stderr:", text),
            quit: (status, toThrow) => {
                throw new Error("OpenSCAD Quit with status " + status);
            },
            ALLOW_MEMORY_GROWTH: 1,
            INITIAL_MEMORY: 536870912 // 512MB
        });

        let instance;
        if (typeof wrapper.getInstance === 'function') {
            instance = wrapper.getInstance();
        } else {
            instance = wrapper;
        }

        // Mount Project Files
        loadDir(instance, LIB_DIR, '/BOSL2');
        loadDir(instance, 'modules', '/modules');
        loadDir(instance, 'parameters', '/parameters');

        // Mount root SCAD files
        const rootFiles = fs.readdirSync('.').filter(f => f.endsWith('.scad'));
        for(const f of rootFiles) {
            instance.FS.writeFile('/' + f, fs.readFileSync(f));
        }

        // Handle Input File
        let vfsInputPath = '';
        const normalizedInput = path.normalize(inputFile);
        const relativeDir = path.dirname(normalizedInput);

        if (relativeDir === CONFIGS_DIR || relativeDir.endsWith(path.sep + CONFIGS_DIR)) {
            // It's in configs/, so we mount configs dir
            loadDir(instance, CONFIGS_DIR, '/configs');
            vfsInputPath = '/configs/' + path.basename(inputFile);
        } else if (path.dirname(inputFile) === '.') {
            vfsInputPath = '/' + path.basename(inputFile);
        } else {
            // Arbitrary path, copy specifically
            const base = path.basename(inputFile);
            instance.FS.writeFile('/' + base, fs.readFileSync(inputFile));
            vfsInputPath = '/' + base;
        }

        const cmd = [
            vfsInputPath,
            '-o', 'output.stl', // Internal name
            ...params
        ];

        try {
            const ret = instance.callMain(cmd);
            if (ret === 0 && instance.FS.analyzePath('/output.stl').exists) {
                const data = instance.FS.readFile('/output.stl');

                // Determine local path logic
                let localPath = outputFile;
                const outDir = path.dirname(localPath);
                if (outDir && !fs.existsSync(outDir)) fs.mkdirSync(outDir, { recursive: true });

                fs.writeFileSync(localPath, data);
                console.log(`  Success: ${outputFile}`);
                return true;
            } else {
                console.error(`  Failure: OpenSCAD exited with ${ret}`);
                return false;
            }
        } catch (e) {
            console.error(`  Exception: ${e.message}`);
            // Explicitly trigger garbage collection if possible or just rely on V8
            return false;
        }
    }

    if (directMode) {
        // DIRECT MODE
        if (!inputDirect) {
            console.error("No input file specified.");
            process.exit(1);
        }
        const success = await renderFile(inputDirect, outputDirect, globalParams);
        if (success && generatePng) {
            await generatePngs(outputDirect);
        }
        if (!success) process.exit(1);

    } else {
        // BATCH MODE
        if (!fs.existsSync(OUTPUT_DIR)) {
            fs.mkdirSync(OUTPUT_DIR, { recursive: true });
        }

        const files = fs.readdirSync(CONFIGS_DIR).filter(f => f.endsWith('.scad'));
        console.log(`Found ${files.length} config files in ${CONFIGS_DIR}`);

        let successCount = 0;
        let failCount = 0;

        for (const file of files) {
            const inputPath = path.join(CONFIGS_DIR, file);
            const outputPath = path.join(OUTPUT_DIR, file.replace('.scad', '.stl'));

            const success = await renderFile(inputPath, outputPath, globalParams);
            if (success) {
                successCount++;
                if (generatePng) {
                    await generatePngs(outputPath);
                }
            }
            else failCount++;
        }

        console.log(`\nExport Summary: ${successCount} succeeded, ${failCount} failed.`);
        if (failCount > 0) process.exit(1);
    }
}

main().catch(err => {
    console.error(err);
    process.exit(1);
});
