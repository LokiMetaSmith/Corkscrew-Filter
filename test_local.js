const SCAD_WASM_IMPORT = async () => {
    try {
        const mod = await import('./lib/openscad-wasm/openscad.js');
        return mod.default || mod.createOpenSCAD || mod;
    } catch (e) {
        console.error("Error importing openscad-wasm:", e);
        process.exit(1);
    }
};

async function main() {
    const createOpenSCAD = await SCAD_WASM_IMPORT();
    const wrapper = await createOpenSCAD({});
    console.log('Success:', Object.keys(wrapper));
}

main().catch(console.error);
