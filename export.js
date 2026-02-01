const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const SCAD_WASM_IMPORT = async () => {
    const mod = await import('openscad-wasm');
    return mod.default || mod.createOpenSCAD || mod;
};

const LIB_DIR = 'BOSL2';
const CONFIGS_DIR = 'configs';
const OUTPUT_DIR = 'exports';

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
    let directParams = [];

    if (args.includes('-o')) {
        directMode = true;
        const oIndex = args.indexOf('-o');
        if (oIndex + 1 < args.length) {
            outputDirect = args[oIndex + 1];
        } else {
            console.error("Error: -o requires an output filename.");
            process.exit(1);
        }

        // Find input file (argument that doesn't start with - and is not the output file)
        for (let i = 0; i < args.length; i++) {
            if (args[i] === '-o') { i++; continue; }
            if (args[i] === '-D') { i++; continue; } // Skip param values
            if (!args[i].startsWith('-')) {
                inputDirect = args[i];
                break; // Assuming first non-flag arg is input
            }
        }

        // Collect parameters
        for (let i = 0; i < args.length; i++) {
             if (args[i] === '-D') {
                 if (i + 1 < args.length) {
                     directParams.push('-D');
                     directParams.push(args[i+1]);
                 }
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
        const wrapper = await createOpenSCAD({ noInitialRun: true });
        const instance = wrapper.getInstance();

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
                fs.writeFileSync(outputFile, data);
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
        const success = await renderFile(inputDirect, outputDirect, directParams);
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

            const success = await renderFile(inputPath, outputPath);
            if (success) successCount++;
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
