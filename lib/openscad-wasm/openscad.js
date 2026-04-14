/// <reference types="./openscad.d.ts" />
let wasmModule;
async function OpenSCAD(options) {
    if (!wasmModule) {
        const url = new URL(`./openscad.wasm.js`, import.meta.url).href;
        const request = await fetch(url);
        wasmModule = "data:text/javascript;base64," + btoa(await request.text());
    }
    const module = {
        noInitialRun: true,
        locateFile: (path) => new URL(`./${path}`, import.meta.url).href,
        ...options,
    };
    const initPromise = new Promise((resolve, reject) => {
        const originalOnRuntimeInitialized = module.onRuntimeInitialized;
        module.onRuntimeInitialized = () => {
            if (originalOnRuntimeInitialized)
                originalOnRuntimeInitialized();
            resolve(null);
        };
        const originalOnAbort = module.onAbort;
        module.onAbort = (what) => {
            if (originalOnAbort)
                originalOnAbort(what);
            reject(new Error("Emscripten aborted: " + String(what)));
        };
    });
    // Emscripten might default to looking for 'Module' if 'EXPORT_NAME' isn't explicitly set in CMake
    globalThis.OpenSCAD = module;
    globalThis.Module = module;
    try {
        const namespace = await import(wasmModule + `#${Math.random()}`);
        // Grab the factory function. It will either be the ES6 default export or attached to the globals
        const factory = namespace.default || globalThis.OpenSCAD || globalThis.Module;
        if (typeof factory === 'function') {
            // Execute the factory function to actually start Emscripten initialization
            const instance = factory(module);
            // If the factory returns a promise (common in newer Emscripten), wait for it
            if (instance instanceof Promise) {
                await instance;
            }
        }
    }
    catch (e) {
        throw e;
    }
    finally {
        // Clean up globals
        delete globalThis.OpenSCAD;
        delete globalThis.Module;
    }
    // Wait for the specific Emscripten runtime ready event
    await initPromise;
    return module;
}

export { OpenSCAD as default };
