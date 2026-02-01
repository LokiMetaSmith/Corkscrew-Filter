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
        // Ignore if exists
    }

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

                let localPath = outputFile;
                if (path.isAbsolute(localPath) && process.platform !== 'win32') {
                     localPath = localPath.substring(1);
                }

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

    // Factory for creating fresh instances
    const createInstance = async () => {
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

        loadProject(instance);
        return instance;
    };

    // Parse Arguments
    const args = process.argv.slice(2);

    let outputFile = null;
    let defineArgs = [];
    let inputFile = null;

    if (args.length > 0) {
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
             if (!outputFile) {
                 console.error("Direct mode requires -o <output_file>");
                 process.exit(1);
             }

             let vfsInput = inputFile.replace(/\\/g, '/');
             if (!vfsInput.startsWith('/')) vfsInput = '/' + vfsInput;

             let vfsOutput = outputFile.replace(/\\/g, '/');
             if (!vfsOutput.startsWith('/')) vfsOutput = '/' + vfsOutput;

             try {
                const instance = await createInstance();
                await runRender(instance, vfsInput, vfsOutput, defineArgs);
             } catch(e) {
                console.error("Failed to run direct export:", e);
                process.exit(1);
             }
             return;
        }
    }

    // Mode 2: Batch Export
    console.log("Running Batch Export...");

    if (!fs.existsSync(EXPORTS_DIR)) {
        fs.mkdirSync(EXPORTS_DIR, { recursive: true });
    }

    const configFiles = fs.readdirSync(CONFIGS_DIR).filter(f => f.endsWith('.scad'));
    console.log(`Found ${configFiles.length} configurations.`);

    for (const conf of configFiles) {
        const name = path.basename(conf, '.scad');
        const vfsIn = `/configs/${conf}`;
        const vfsOut = `${EXPORTS_DIR}/${name}.stl`;

        console.log(`Exporting ${conf}...`);
        try {
            const instance = await createInstance();
            // Ensure /exports exists in VFS
            try { instance.FS.mkdir(`/${EXPORTS_DIR}`); } catch(e) {}

            const success = await runRender(instance, vfsIn, vfsOut);
        } catch (e) {
             console.error(`Export failed/crashed for ${conf}:`, e);
        }
    }
}

main();
