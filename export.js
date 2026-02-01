const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

// Configuration
const BOSL2_REPO = 'https://github.com/BOSL2/BOSL2.git';
const LOCAL_BOSL2_DIR = 'BOSL2'; // In the project root
const CONFIGS_DIR = 'configs';
const EXPORTS_DIR = 'exports';

// Utility: Dynamic Import for ESM module
const importOpenSCAD = async () => {
    try {
        const mod = await import('openscad-wasm');
        return mod.default || mod;
    } catch (e) {
        console.error("Error importing openscad-wasm:", e);
        process.exit(1);
    }
};

// Utility: Ensure BOSL2 exists
function ensureBOSL2() {
    if (!fs.existsSync(LOCAL_BOSL2_DIR)) {
        console.log(`BOSL2 library not found in ${LOCAL_BOSL2_DIR}. Cloning...`);
        try {
            execSync(`git clone --depth 1 ${BOSL2_REPO} ${LOCAL_BOSL2_DIR}`, { stdio: 'inherit' });
            console.log('BOSL2 cloned successfully.');
        } catch (e) {
            console.error('Failed to clone BOSL2:', e.message);
            // Fallback: Try zip download if git fails
            console.log('Attempting alternative download (zip)...');
            try {
                execSync('curl -L -o bosl2.zip https://github.com/BelfrySCAD/BOSL2/archive/refs/heads/master.zip');
                execSync(`unzip -q bosl2.zip`);
                if (fs.existsSync('BOSL2-master')) {
                    fs.renameSync('BOSL2-master', LOCAL_BOSL2_DIR);
                }
                fs.unlinkSync('bosl2.zip');
            } catch (e2) {
                console.error('Failed to download BOSL2 zip:', e2.message);
                process.exit(1);
            }
        }
    }
}

// Utility: Load directory into WASM FS
function loadDir(instance, localPath, virtualPath) {
    if (!fs.existsSync(localPath)) return;
    try { instance.FS.mkdir(virtualPath); } catch (e) {
        // Ignore if exists, but for nested paths we might need recursive mkdir
        // openscad-wasm FS (emscripten) usually needs explicit creation of parents?
        // simple mkdir might fail if parent missing.
    }

    // Simple recursive loader
    const items = fs.readdirSync(localPath);
    for (const item of items) {
        const loc = path.join(localPath, item);
        const virt = virtualPath === '/' ? `/${item}` : `${virtualPath}/${item}`;
        const stat = fs.statSync(loc);
        if (stat.isDirectory()) {
            loadDir(instance, loc, virt);
        } else {
            const data = fs.readFileSync(loc);
            instance.FS.writeFile(virt, data);
        }
    }
}

// Utility: Load the project files
function loadProject(instance) {
    // 1. Load Root .scad files
    const rootFiles = fs.readdirSync('.').filter(f => f.endsWith('.scad'));
    for (const f of rootFiles) {
        instance.FS.writeFile(`/${f}`, fs.readFileSync(f));
    }

    // 2. Load Modules
    loadDir(instance, 'modules', '/modules');

    // 3. Load Parameters
    loadDir(instance, 'parameters', '/parameters');

    // 4. Load Configs
    loadDir(instance, 'configs', '/configs');

    // 5. Load BOSL2 into /libraries/BOSL2 (Standard Library Path)
    // Create /libraries first
    try { instance.FS.mkdir('/libraries'); } catch(e){}
    loadDir(instance, LOCAL_BOSL2_DIR, '/libraries/BOSL2');
}

async function runRender(instance, inputFile, outputFile, extraArgs = []) {
    // Prepare arguments
    // openscad -o output.stl input.scad
    const args = ['-o', outputFile, ...extraArgs, inputFile];

    console.log(`Executing OpenSCAD: ${args.join(' ')}`);

    try {
        const ret = instance.callMain(args);
        if (ret === 0) {
            // Check if output file exists in VFS
            if (instance.FS.analyzePath(outputFile).exists) {
                const data = instance.FS.readFile(outputFile);

                // Determine local path. If outputFile starts with '/', strip it for local write
                // to avoid writing to root (unless user really intended absolute path, but strict mode helps).
                // Actually, simply using it as relative to CWD is safer for this script's purpose.
                let localPath = outputFile;
                if (path.isAbsolute(localPath) && process.platform !== 'win32') {
                     // If it's effectively an absolute path in VFS (starts with /), treat as relative locally
                     // to prevent EACCES errors.
                     localPath = localPath.substring(1);
                }

                // Ensure output directory exists locally
                const outDir = path.dirname(localPath);
                if (outDir && !fs.existsSync(outDir)) fs.mkdirSync(outDir, { recursive: true });

                fs.writeFileSync(localPath, data);
                console.log(`Success: ${localPath}`);
                return true;
            } else {
                console.error(`Error: Output file ${outputFile} was not created.`);
                return false;
            }
        } else {
            console.error(`OpenSCAD returned error code: ${ret}`);
            return false;
        }
    } catch (e) {
        console.error("Exception during render:", e);
        return false;
    }
}

async function main() {
    ensureBOSL2();

    const { createOpenSCAD } = await importOpenSCAD();

    // Initialize OpenSCAD WASM
    // createOpenSCAD returns a wrapper object (OpenSCAD instance factory)
    const wrapper = await createOpenSCAD({
        noInitialRun: true,
        print: (text) => console.log("SCAD stdout:", text),
        printErr: (text) => console.error("SCAD stderr:", text),
        // Attempt to increase memory limits (Emscripten options)
        ALLOW_MEMORY_GROWTH: 1,
        // INITIAL_MEMORY: 268435456 // 256MB (Commented out as strict strict standard might fail if mismatched)
    });

    // The library may require calling getInstance() or accessing the module directly depending on version.
    // Based on user snippet:
    let instance;
    if (typeof wrapper.getInstance === 'function') {
        instance = wrapper.getInstance();
    } else {
        // Fallback: maybe wrapper itself is the instance (standard emscripten)?
        instance = wrapper;
    }

    // Load Project Files
    console.log("Loading project files into virtual filesystem...");
    loadProject(instance);

    // Parse Arguments
    const args = process.argv.slice(2);

    // Helper to parse simple flags
    let outputFile = null;
    let defineArgs = [];
    let inputFile = null;

    // Check for "-o"
    // Valid format: node export.js [-o out.stl] [-D var=val]... [file.scad]

    if (args.length > 0) {
        // Mode 1: Direct Execution (CLI Wrapper)
        for (let i = 0; i < args.length; i++) {
            if (args[i] === '-o') {
                outputFile = args[i + 1];
                i++;
            } else if (args[i].startsWith('-D')) {
                if (args[i] === '-D') {
                    defineArgs.push('-D');
                    defineArgs.push(args[i + 1]);
                    i++;
                } else {
                    defineArgs.push(args[i]);
                }
            } else if (!args[i].startsWith('-')) {
                inputFile = args[i];
            }
        }

        if (inputFile) {
             // Validate inputs
             if (!outputFile) {
                 console.error("Direct mode requires -o <output_file>");
                 process.exit(1);
             }
             // NOTE: inputFile logic
             // If input is "configs/foo.scad", we should use "/configs/foo.scad" in VFS.
             // We need to ensure we map local path to VFS path correctly.
             // Since we mirrored the structure, a relative path like "configs/foo.scad" works if we prepend "/"?
             // Actually, "configs/foo.scad" as a string is just a path.
             // OpenSCAD inside WASM starts at /.
             // If we pass "configs/foo.scad", it looks for /configs/foo.scad.
             // But we need to make sure the user passed a relative path.
             // ScadDriver passes "corkscrew filter.scad" (root) or similar.
             // So simply prepending "/" usually works if valid relative path.
             // Or ensuring it starts with "/"?
             // Let's normalize.

             let vfsInput = inputFile.replace(/\\/g, '/');
             if (!vfsInput.startsWith('/')) vfsInput = '/' + vfsInput;

             // Output file also needs to be VFS path.
             // Usually output is "exports/foo.stl" or similar.
             let vfsOutput = outputFile.replace(/\\/g, '/');
             if (!vfsOutput.startsWith('/')) vfsOutput = '/' + vfsOutput;

             await runRender(instance, vfsInput, vfsOutput, defineArgs);
             return;
        }
    }

    // Mode 2: Batch Export (Default)
    console.log("Running Batch Export...");

    if (!fs.existsSync(EXPORTS_DIR)) {
        fs.mkdirSync(EXPORTS_DIR, { recursive: true });
    }

    const configFiles = fs.readdirSync(CONFIGS_DIR).filter(f => f.endsWith('.scad'));
    console.log(`Found ${configFiles.length} configurations.`);

    for (const conf of configFiles) {
        const name = path.basename(conf, '.scad');
        const vfsIn = `/configs/${conf}`;
        const vfsOut = `${EXPORTS_DIR}/${name}.stl`; // Relative path for both VFS and Local

        // Ensure /exports exists in VFS
        try { instance.FS.mkdir(`/${EXPORTS_DIR}`); } catch(e) {}

        console.log(`Exporting ${conf}...`);
        const success = await runRender(instance, vfsIn, vfsOut);
        if (success) {
            // Copy back to local FS handled by runRender logic if we pass local path?
            // runRender writes to FS using the output path.
            // If vfsOut is /exports/foo.stl, we read that.
            // But we want to write to local "exports/foo.stl".
            // runRender calls fs.writeFileSync(path.dirname(outputFile)...)
            // wait, runRender argument `outputFile` is used for BOTH VFS and Local FS?
            // If passed "/exports/foo.stl":
            // instance.FS.readFile("/exports/foo.stl") -> Works.
            // fs.writeFileSync("/exports/foo.stl") -> Fails on Linux (root).
            // We should distinguish VFS path and Local path if they differ.
            // For simplicity in runRender, I assumed they are the same relative path structure.
            // If I pass "exports/foo.stl" (no leading slash),
            // VFS: /exports/foo.stl (OpenSCAD resolves relative to cwd /)
            // Local: exports/foo.stl (Relative to cwd)
            // This works!

            // So I should pass "exports/name.stl" (no leading slash).
        }
    }
}

main();
