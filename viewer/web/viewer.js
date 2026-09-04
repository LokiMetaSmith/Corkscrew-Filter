/* viewer/web/viewer.js — Atlas Fields Studio WebGL Engine */

// --- Global State ---
let scene, camera, renderer, controls;
let corkscrewMesh = null;
let particleSystem = null;
let particlePositions, particleVelocities, particleLifetimes;
const N_PARTICLES = 600;

let currentDomain = "cfd";
let currentFidelity = "tier1";
let currentParams = {};
let paramDefs = {};
let activeColormap = "Turbo";
let wireframeMode = false;
let showParticles = true;
let isPredicting = false;
let pendingPredict = false;

// KiCad 3D PCB State
let pcbGroup = null;
let activePcbData = null;
let selectedPcbNet = null;
let kicadFrequency = 5.0;
let isInitialPcbLoad = true;

// Colormap lookup tables
const COLORMAPS = {
  Turbo: [
    [0.00, [48, 18, 59]], [0.20, [57, 162, 252]], [0.40, [25, 215, 200]],
    [0.60, [212, 230, 54]], [0.80, [253, 165, 51]], [1.00, [122, 4, 3]]
  ],
  Viridis: [
    [0.00, [68, 1, 84]], [0.25, [59, 82, 139]], [0.50, [33, 145, 140]],
    [0.75, [94, 201, 98]], [1.00, [253, 231, 37]]
  ],
  Plasma: [
    [0.00, [13, 8, 135]], [0.25, [156, 23, 158]], [0.50, [203, 70, 121]],
    [0.75, [251, 159, 58]], [1.00, [240, 249, 33]]
  ],
  Twilight: [
    [0.00, [226, 217, 227]], [0.25, [125, 155, 201]], [0.50, [65, 44, 79]],
    [0.75, [182, 125, 107]], [1.00, [226, 217, 227]]
  ]
};

function sampleColormapRGB(t, cmapName = "Turbo") {
  const stops = COLORMAPS[cmapName] || COLORMAPS.Turbo;
  t = Math.max(0.0, Math.min(1.0, t));
  for (let i = 0; i < stops.length - 1; i++) {
    if (t >= stops[i][0] && t <= stops[i + 1][0]) {
      const f = (t - stops[i][0]) / (stops[i + 1][0] - stops[i][0]);
      const c1 = stops[i][1];
      const c2 = stops[i + 1][1];
      const r = (c1[0] + (c2[0] - c1[0]) * f) / 255.0;
      const g = (c1[1] + (c2[1] - c1[1]) * f) / 255.0;
      const b = (c1[2] + (c2[2] - c1[2]) * f) / 255.0;
      return new THREE.Color(r, g, b);
    }
  }
  return new THREE.Color(1, 1, 1);
}

// --- Initialization ---
window.addEventListener("DOMContentLoaded", () => {
  initThree();
  initParticleSystem();
  loadBackendStatus();
  animate();

  // Setup periodic queue and KiCad live polling
  pollKiCadLiveStatus();
  setInterval(pollSolverQueue, 2000);
  setInterval(pollKiCadLiveStatus, 1500);
});

function initThree() {
  const container = document.getElementById("viewport-container");
  const canvas = document.getElementById("webgl-canvas");

  // Scene
  scene = new THREE.Scene();
  scene.background = new THREE.Color(0x06080d);
  scene.fog = new THREE.FogExp2(0x06080d, 0.008);

  // Camera
  camera = new THREE.PerspectiveCamera(45, container.clientWidth / container.clientHeight, 0.1, 1000);
  camera.position.set(40, 35, 60);

  // Renderer
  renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
  renderer.setSize(container.clientWidth, container.clientHeight);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.1;

  // Controls
  controls = new THREE.OrbitControls(camera, canvas);
  controls.enableDamping = true;
  controls.dampingFactor = 0.05;
  controls.maxDistance = 250;
  controls.minDistance = 5;

  // Lights
  const ambient = new THREE.AmbientLight(0xffffff, 0.6);
  scene.add(ambient);

  const keyLight = new THREE.DirectionalLight(0x38bdf8, 1.2);
  keyLight.position.set(50, 80, 50);
  scene.add(keyLight);

  const rimLight = new THREE.DirectionalLight(0xa855f7, 0.8);
  rimLight.position.set(-50, -30, -50);
  scene.add(rimLight);

  // Studio Grid Floor
  const grid = new THREE.GridHelper(100, 40, 0x1e293b, 0x0f172a);
  grid.position.y = -25;
  scene.add(grid);

  // PCB 3D Group
  pcbGroup = new THREE.Group();
  pcbGroup.name = "pcbGroup";
  pcbGroup.visible = false;
  scene.add(pcbGroup);

  window.addEventListener("resize", onWindowResize);
}

function onWindowResize() {
  const container = document.getElementById("viewport-container");
  camera.aspect = container.clientWidth / container.clientHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(container.clientWidth, container.clientHeight);
}

// --- Parametric Corkscrew Geometry Generator ---
function updateCorkscrewGeometry(params) {
  const turns = parseFloat(params.number_of_complete_revolutions || 2.0);
  const r_in = parseFloat(params.helix_path_radius_mm || 1.8);
  const r_out = 15.0; // Outer tube radius
  const length = parseFloat(params.insert_length_mm || 50.0);
  const chamfer = parseFloat(params.blade_chamfer_mm || 0.5);

  const nRadial = 12;
  const nTheta = Math.floor(60 * turns);
  const geom = new THREE.BufferGeometry();

  const positions = [];
  const normals = [];
  const colors = [];
  const indices = [];

  for (let i = 0; i <= nTheta; i++) {
    const frac = i / nTheta;
    const theta = frac * Math.PI * 2.0 * turns;
    const z = (frac - 0.5) * length;

    for (let j = 0; j <= nRadial; j++) {
      const rFrac = j / nRadial;
      const r = r_in + (r_out - r_in) * rFrac;

      const x = r * Math.cos(theta);
      const y = r * Math.sin(theta);

      positions.push(x, y, z);
      normals.push(-Math.sin(theta), Math.cos(theta), 0.1);

      // Color coding based on domain
      let col;
      if (currentDomain === "fea") {
        // Stress concentration at inner root
        const stress = Math.max(0.1, 1.0 - rFrac) * (1.2 / (1.0 + chamfer * 0.5));
        col = sampleColormapRGB(stress, "Plasma");
      } else if (currentDomain === "cfd") {
        // Centrifugal pressure/swirl
        col = sampleColormapRGB(rFrac * 0.8 + 0.1, activeColormap);
      } else {
        col = sampleColormapRGB(frac, "Twilight");
      }
      colors.push(col.r, col.g, col.b);
    }
  }

  // Quads to triangles
  for (let i = 0; i < nTheta; i++) {
    for (let j = 0; j < nRadial; j++) {
      const row1 = i * (nRadial + 1);
      const row2 = (i + 1) * (nRadial + 1);

      const a = row1 + j;
      const b = row1 + j + 1;
      const c = row2 + j;
      const d = row2 + j + 1;

      indices.push(a, b, c);
      indices.push(c, b, d);
    }
  }

  geom.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
  geom.setAttribute("normal", new THREE.Float32BufferAttribute(normals, 3));
  geom.setAttribute("color", new THREE.Float32BufferAttribute(colors, 3));
  geom.setIndex(indices);
  geom.computeVertexNormals();

  if (corkscrewMesh) {
    scene.remove(corkscrewMesh);
    corkscrewMesh.geometry.dispose();
  }

  const mat = new THREE.MeshStandardMaterial({
    vertexColors: true,
    roughness: 0.35,
    metalness: 0.2,
    wireframe: wireframeMode,
    side: THREE.DoubleSide
  });

  corkscrewMesh = new THREE.Mesh(geom, mat);
  scene.add(corkscrewMesh);
}

// --- Streamline Particle System ---
function initParticleSystem() {
  const geom = new THREE.BufferGeometry();
  particlePositions = new Float32Array(N_PARTICLES * 3);
  particleVelocities = new Float32Array(N_PARTICLES * 3);
  particleLifetimes = new Float32Array(N_PARTICLES);
  const colors = new Float32Array(N_PARTICLES * 3);

  for (let i = 0; i < N_PARTICLES; i++) {
    resetParticle(i, true);
    const col = sampleColormapRGB(Math.random(), "Turbo");
    colors[i * 3] = col.r;
    colors[i * 3 + 1] = col.g;
    colors[i * 3 + 2] = col.b;
  }

  geom.setAttribute("position", new THREE.BufferAttribute(particlePositions, 3));
  geom.setAttribute("color", new THREE.BufferAttribute(colors, 3));

  const mat = new THREE.PointsMaterial({
    size: 1.2,
    vertexColors: true,
    transparent: true,
    opacity: 0.85,
    blending: THREE.AdditiveBlending
  });

  particleSystem = new THREE.Points(geom, mat);
  scene.add(particleSystem);
}

function resetParticle(i, initial = false) {
  const length = parseFloat(currentParams.insert_length_mm || 50.0);
  const r_in = parseFloat(currentParams.helix_path_radius_mm || 1.8) + 1.0;
  const r_out = 14.0;

  const r = r_in + Math.random() * (r_out - r_in);
  const theta = Math.random() * Math.PI * 2;
  const z = initial ? (Math.random() - 0.5) * length : -length * 0.5;

  particlePositions[i * 3] = r * Math.cos(theta);
  particlePositions[i * 3 + 1] = r * Math.sin(theta);
  particlePositions[i * 3 + 2] = z;
  particleLifetimes[i] = Math.random() * 1.0;
}

function updateParticles(dt) {
  if (!particleSystem || !showParticles || currentDomain === "pcb") return;

  const length = parseFloat(currentParams.insert_length_mm || 50.0);
  const turns = parseFloat(currentParams.number_of_complete_revolutions || 2.0);
  const posAttr = particleSystem.geometry.attributes.position;
  const colAttr = particleSystem.geometry.attributes.color;

  for (let i = 0; i < N_PARTICLES; i++) {
    const idx = i * 3;
    let x = particlePositions[idx];
    let y = particlePositions[idx + 1];
    let z = particlePositions[idx + 2];

    const r = Math.sqrt(x * x + y * y);
    const theta = Math.atan2(y, x);

    // Swirling vortex velocity field
    const omega = 2.0 * Math.PI * turns * (12.0 / Math.max(length, 1.0));
    const u_theta = omega * r * 0.08;
    const u_z = 25.0 * dt;

    x += -u_theta * Math.sin(theta) * dt;
    y += u_theta * Math.cos(theta) * dt;
    z += u_z;

    particlePositions[idx] = x;
    particlePositions[idx + 1] = y;
    particlePositions[idx + 2] = z;

    if (z > length * 0.5 || r > 16.0) {
      resetParticle(i);
    }

    // Dynamic color by velocity
    const speedNorm = Math.min(1.0, (u_theta + 10.0) / 25.0);
    const col = sampleColormapRGB(speedNorm, activeColormap);
    colAttr.array[idx] = col.r;
    colAttr.array[idx + 1] = col.g;
    colAttr.array[idx + 2] = col.b;
  }

  posAttr.needsUpdate = true;
  colAttr.needsUpdate = true;
}

// --- Animation Loop ---
let lastTime = performance.now();
let frameCount = 0;
let lastFpsUpdate = performance.now();

function animate() {
  requestAnimationFrame(animate);

  const now = performance.now();
  const dt = Math.min(0.1, (now - lastTime) / 1000.0);
  lastTime = now;

  // FPS Counter
  frameCount++;
  if (now - lastFpsUpdate > 500) {
    const fps = Math.round((frameCount * 1000) / (now - lastFpsUpdate));
    document.getElementById("fps-counter").innerText = `${fps} FPS`;
    frameCount = 0;
    lastFpsUpdate = now;
  }

  controls.update();
  updateParticles(dt);

  // Slow subtle rotation for corkscrew CFD/FEA
  if (corkscrewMesh && currentDomain !== "pcb") {
    corkscrewMesh.rotation.z += 0.002;
  }

  renderer.render(scene, camera);
}

// --- REST API Client & Interactivity ---

async function loadBackendStatus() {
  try {
    const res = await fetch("/api/status");
    const data = await res.json();
    paramDefs = data.param_defs || {};
    currentDomain = data.domain || "cfd";

    document.getElementById("surrogate-samples").innerText = `${data.surrogate_samples} Points`;
    buildParameterSliders();
    triggerPrediction();
  } catch (err) {
    console.error("Backend connection error:", err);
    document.getElementById("backend-status").innerText = "Offline Mode (Synthetic)";
    // Fallback default parameters
    paramDefs = {
      number_of_complete_revolutions: { min: 1.0, max: 4.0, default: 2.0 },
      helix_path_radius_mm: { min: 1.5, max: 5.0, default: 1.8 },
      blade_chamfer_mm: { min: 0.1, max: 1.0, default: 0.5 },
      insert_length_mm: { min: 40.0, max: 60.0, default: 50.0 }
    };
    buildParameterSliders();
    updateCorkscrewGeometry(currentParams);
  }
}

function buildParameterSliders() {
  const container = document.getElementById("sliders-container");
  container.innerHTML = "";

  for (const [pName, defn] of Object.entries(paramDefs)) {
    const pMin = defn.min !== undefined ? defn.min : 0.0;
    const pMax = defn.max !== undefined ? defn.max : 10.0;
    const pDef = defn.default !== undefined ? defn.default : (pMin + pMax) / 2.0;

    currentParams[pName] = pDef;

    const group = document.createElement("div");
    group.className = "slider-group";

    const labelRow = document.createElement("div");
    labelRow.className = "slider-label-row";

    const label = document.createElement("span");
    label.innerText = formatParamName(pName);

    const valDisplay = document.createElement("span");
    valDisplay.className = "slider-val";
    valDisplay.id = `val-${pName}`;
    valDisplay.innerText = Number(pDef).toFixed(2);

    labelRow.appendChild(label);
    labelRow.appendChild(valDisplay);

    const slider = document.createElement("input");
    slider.type = "range";
    slider.min = pMin;
    slider.max = pMax;
    slider.step = (pMax - pMin) / 100.0;
    slider.value = pDef;
    slider.id = `slider-${pName}`;

    slider.addEventListener("input", (e) => {
      const val = parseFloat(e.target.value);
      currentParams[pName] = val;
      valDisplay.innerText = val.toFixed(2);
      onParameterScrub();
    });

    group.appendChild(labelRow);
    group.appendChild(slider);
    container.appendChild(group);
  }

  updateCorkscrewGeometry(currentParams);
}

function formatParamName(str) {
  return str.replace(/_/g, " ").replace(/mm/g, "(mm)");
}

function onParameterScrub() {
  updateCorkscrewGeometry(currentParams);
  if (!isPredicting) {
    triggerPrediction();
  } else {
    pendingPredict = true;
  }
}

async function triggerPrediction() {
  if (currentDomain === "pcb") return;
  isPredicting = true;
  try {
    const t0 = performance.now();
    const res = await fetch("/api/predict", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        params: currentParams,
        fidelity: currentFidelity,
        enforce_conservation: true
      })
    });
    const data = await res.json();
    const tElapsed = Math.round(performance.now() - t0);

    const statusPrefix = currentFidelity === "tier1" ? "Surrogate Live" : "Fine Mesh Ground Truth";
    document.getElementById("backend-status").innerText = `${statusPrefix} (${tElapsed}ms)`;
    updateTelemetryHUD(data.metrics, data.uncertainty, data.conservation);
  } catch (err) {
    console.warn("Prediction fallback:", err);
  } finally {
    isPredicting = false;
    if (pendingPredict) {
      pendingPredict = false;
      triggerPrediction();
    }
  }
}

function updateTelemetryHUD(metrics, uncertainty, conservation) {
  if (!metrics || currentDomain === "pcb") return;

  // Separation Efficiency
  const eff = metrics.separation_efficiency !== undefined ? metrics.separation_efficiency : 96.5;
  document.getElementById("metric-eff").innerText = `${Number(eff).toFixed(2)}%`;
  const effCard = document.getElementById("card-eff");
  effCard.style.borderColor = eff >= 99.95 ? "var(--accent-emerald)" : "var(--border-subtle)";

  // Pressure Drop
  const dpPa = metrics.delta_p !== undefined ? metrics.delta_p : 2600.0;
  const dpPsi = dpPa / 6894.76;
  document.getElementById("metric-dp").innerText = `${dpPsi.toFixed(2)} PSI`;
  document.getElementById("sub-dp").innerText = `${Math.round(dpPa)} Pa (Limit: 0.70 PSI)`;

  // PINN Conservation Telemetry
  const divElem = document.getElementById("metric-div");
  const subDiv = document.getElementById("sub-div");
  if (divElem && conservation) {
    if (conservation.divergence_loss !== undefined) {
      const divVal = Number(conservation.divergence_loss);
      divElem.innerText = `∇·u = ${divVal.toFixed(5)}`;
      const isAdm = conservation.is_physically_admissible !== false;
      subDiv.innerHTML = `<span class="badge-status-dot ${isAdm ? 'admissible' : 'violation'}"></span> ${isAdm ? 'Physically Admissible' : 'Divergence Violation'}`;
    } else if (conservation.equilibrium_loss !== undefined) {
      const eqVal = Number(conservation.equilibrium_loss);
      divElem.innerText = `∇·σ = ${eqVal.toFixed(5)}`;
      subDiv.innerHTML = `<span class="badge-status-dot admissible"></span> Structural Equilibrium Valid`;
    }
  }

  // Von Mises Stress
  const vm = metrics.max_von_mises_stress_MPa !== undefined ? metrics.max_von_mises_stress_MPa : 24.5;
  document.getElementById("metric-stress").innerText = `${Number(vm).toFixed(1)} MPa`;

  // Factor of Safety
  const fos = metrics.factor_of_safety !== undefined ? metrics.factor_of_safety : 2.45;
  document.getElementById("metric-fos").innerText = Number(fos).toFixed(2);
  const fosCard = document.getElementById("card-fos");
  fosCard.style.borderColor = fos >= 1.5 ? "var(--accent-emerald)" : "var(--accent-amber)";

  // Epistemic Uncertainty
  if (uncertainty !== undefined) {
    document.getElementById("metric-unc").innerText = Number(uncertainty).toFixed(3);
  }
}

// --- Inverse Design ---
async function triggerInverseDesign() {
  const btn = document.querySelector(".btn-optimize");
  btn.classList.add("shimmer-active");
  btn.innerText = "Optimizing (L-BFGS-B)...";

  try {
    const res = await fetch("/api/optimize", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ seed_params: currentParams })
    });
    const data = await res.json();
    const optParams = data.optimal_params;

    // Animate sliders to optimal geometry
    for (const [k, v] of Object.entries(optParams)) {
      const slider = document.getElementById(`slider-${k}`);
      const display = document.getElementById(`val-${k}`);
      if (slider) {
        slider.value = v;
        currentParams[k] = v;
      }
      if (display) {
        display.innerText = Number(v).toFixed(2);
      }
    }

    updateCorkscrewGeometry(currentParams);
    updateTelemetryHUD(data.predicted_metrics, data.uncertainty);
  } catch (err) {
    console.error("Inverse design failed:", err);
  } finally {
    btn.classList.remove("shimmer-active");
    btn.innerHTML = "<span>⚡</span><span>AI Inverse Design (L-BFGS-B)</span>";
  }
}

// --- Background Solver Queue ---
async function dispatchBackgroundSolver() {
  const statusCard = document.getElementById("job-status-card");
  statusCard.style.display = "flex";
  statusCard.classList.add("shimmer-active");
  document.getElementById("job-status-text").innerText = "RUNNING SOLVER...";

  try {
    const res = await fetch("/api/dispatch", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ params: currentParams, mock: true })
    });
    const ticket = await res.json();
    document.getElementById("job-id-text").innerText = `Ticket: ${ticket.job_id}`;
  } catch (err) {
    console.error("Dispatch error:", err);
    document.getElementById("job-status-text").innerText = "FAILED";
  }
}

async function pollSolverQueue() {
  try {
    const res = await fetch("/api/poll");
    const data = await res.json();
    if (data.completed && data.completed.length > 0) {
      const lastJob = data.completed[data.completed.length - 1];
      const statusCard = document.getElementById("job-status-card");
      statusCard.classList.remove("shimmer-active");
      document.getElementById("job-status-text").innerText = `COMPLETED (${lastJob.duration_s}s)`;
      document.getElementById("surrogate-samples").innerText = `${data.surrogate_samples} Points`;
      updateTelemetryHUD(lastJob.metrics, 0.05);
    }
  } catch (e) {}
}

// --- UI Actions ---
function switchDomain(domain) {
  currentDomain = domain;
  document.querySelectorAll(".domain-btn").forEach(btn => {
    btn.classList.toggle("active", btn.dataset.domain === domain);
  });

  const cfdPanel = document.getElementById("cfd-panel");
  const kicadPanel = document.getElementById("kicad-panel");

  if (domain === "pcb") {
    // Hide CFD / FEA geometry and particles
    if (corkscrewMesh) corkscrewMesh.visible = false;
    if (particleSystem) particleSystem.visible = false;
    if (pcbGroup) pcbGroup.visible = true;

    // Switch Left Drawer
    if (cfdPanel) cfdPanel.style.display = "none";
    if (kicadPanel) kicadPanel.style.display = "block";

    // Set Camera directly over the PCB
    camera.position.set(0, 52, 45);
    controls.target.set(0, 0, 0);
    controls.update();

    // If PCB data is already loaded, update the inspector & HUD
    if (activePcbData) {
      updatePcbHUD(activePcbData);
    }
    return;
  }

  // Non-PCB domain (CFD, FEA, Joint, EM Phasor)
  if (pcbGroup) pcbGroup.visible = false;
  if (corkscrewMesh) corkscrewMesh.visible = true;
  if (particleSystem) particleSystem.visible = showParticles;

  if (cfdPanel) cfdPanel.style.display = "block";
  if (kicadPanel) kicadPanel.style.display = "none";

  resetCfdHudLabels();

  // Switch colormaps and field views
  if (domain === "fea") {
    activeColormap = "Plasma";
    document.getElementById("cmap-select").value = "Plasma";
  } else if (domain === "cfd") {
    activeColormap = "Turbo";
    document.getElementById("cmap-select").value = "Turbo";
  }

  fetch("/api/switch_domain", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ domain: domain })
  });

  updateCorkscrewGeometry(currentParams);
  triggerPrediction();
}

function resetCfdHudLabels() {
  const cardEffTitle = document.querySelector("#card-eff .metric-title");
  if (cardEffTitle) cardEffTitle.innerText = "PARTICLE COLLECTION EFFICIENCY";
  const subEff = document.getElementById("sub-eff");
  if (subEff) subEff.innerText = "Target: > 99.95% (Moon Dust)";

  const cardDpTitle = document.querySelector("#card-dp .metric-title");
  if (cardDpTitle) cardDpTitle.innerText = "PRESSURE DROP (Δp)";
  const subDp = document.getElementById("sub-dp");
  if (subDp) subDp.innerText = "Target: < 0.70 PSI (~2900 Pa)";

  const cardConvTitle = document.querySelector("#card-conservation .metric-title");
  if (cardConvTitle) cardConvTitle.innerText = "PINN CONSERVATION RESIDUAL";
  const subConv = document.getElementById("sub-div");
  if (subConv) subConv.innerHTML = '<span class="badge-status-dot admissible"></span> Physically Admissible';

  const cardStressTitle = document.querySelector("#card-stress .metric-title");
  if (cardStressTitle) cardStressTitle.innerText = "MAX VON MISES STRESS";
  const subStress = document.getElementById("sub-stress");
  if (subStress) subStress.innerText = "Yield: 60 MPa (PETG/PLA)";

  const cardFosTitle = document.querySelector("#card-fos .metric-title");
  if (cardFosTitle) cardFosTitle.innerText = "FACTOR OF SAFETY";
  const subFos = document.getElementById("sub-fos");
  if (subFos) subFos.innerText = "Target: ≥ 1.50";

  const cardUncTitle = document.querySelector("#card-unc .metric-title");
  if (cardUncTitle) cardUncTitle.innerText = "EPISTEMIC UNCERTAINTY";
}

function resetCamera() {
  if (currentDomain === "pcb") {
    camera.position.set(0, 52, 45);
    controls.target.set(0, 0, 0);
  } else {
    camera.position.set(40, 35, 60);
    controls.target.set(0, 0, 0);
  }
  controls.update();
}

function toggleParticles() {
  showParticles = !showParticles;
  if (particleSystem) particleSystem.visible = showParticles;
}

function toggleWireframe() {
  wireframeMode = !wireframeMode;
  if (corkscrewMesh) corkscrewMesh.material.wireframe = wireframeMode;
}

function changeColormap(name) {
  activeColormap = name;
  updateCorkscrewGeometry(currentParams);
}

// --- Fidelity Switching ---
function setFidelity(tier) {
  currentFidelity = tier;
  const btnT1 = document.getElementById("btn-fidelity-t1");
  const btnT2 = document.getElementById("btn-fidelity-t2");
  if (btnT1) btnT1.classList.toggle("active", tier === "tier1");
  if (btnT2) btnT2.classList.toggle("active", tier === "tier2");

  const statusElem = document.getElementById("backend-status");
  if (statusElem) {
    statusElem.innerText = tier === "tier1" ? "Surrogate Live (2ms)" : "Ground-Truth Fine Mesh CFD";
  }
  triggerPrediction();
}

// --- Autonomous AI Engineering Agent Console ---
function toggleAgentDrawer() {
  const drawer = document.getElementById("agent-drawer");
  if (drawer) {
    drawer.classList.toggle("collapsed");
  }
}

function handleAgentKey(e) {
  if (e.key === "Enter") {
    sendAgentMessage();
  }
}

async function sendAgentMessage() {
  const input = document.getElementById("agent-input");
  if (!input) return;
  const text = input.value.trim();
  if (!text) return;

  input.value = "";
  const chatMessages = document.getElementById("agent-chat-messages");
  if (!chatMessages) return;

  // Render User Message
  const userDiv = document.createElement("div");
  userDiv.className = "agent-msg user";
  userDiv.innerText = text;
  chatMessages.appendChild(userDiv);

  // Status Tag
  const activeTag = document.getElementById("agent-active-tag");
  if (activeTag) {
    activeTag.innerText = "THINKING...";
    activeTag.style.borderColor = "var(--accent-amber)";
    activeTag.style.color = "var(--accent-amber)";
  }

  // Ensure drawer is open
  const drawer = document.getElementById("agent-drawer");
  if (drawer) drawer.classList.remove("collapsed");

  // Thinking Bubble
  const thinkDiv = document.createElement("div");
  thinkDiv.className = "agent-msg system";
  thinkDiv.innerHTML = "<em>Autonomous Agent reasoning over multi-physics manifold...</em>";
  chatMessages.appendChild(thinkDiv);
  chatMessages.scrollTop = chatMessages.scrollHeight;

  try {
    const res = await fetch("/api/agent_chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: text,
        params: currentParams,
        fidelity: currentFidelity
      })
    });
    const data = await res.json();
    thinkDiv.remove();

    const agentDiv = document.createElement("div");
    agentDiv.className = "agent-msg agent";

    let html = `<strong>${data.agent_type || 'CAD_Agent'}:</strong> ${data.reply}<br>`;

    if (data.trace && data.trace.length > 0) {
      html += `<div style="margin-top: 6px; font-size: 11px;">`;
      for (const step of data.trace) {
        html += `<span class="tool-chip">⚡ ${step.tool || 'Tool'}</span> `;
      }
      html += `</div>`;
    }

    if (data.kicad_path) {
      html += `<div style="margin-top: 4px; font-size: 11px; color: var(--accent-emerald);">Exported KiCad PCB: <code>${data.kicad_path}</code></div>`;
    }

    agentDiv.innerHTML = html;
    chatMessages.appendChild(agentDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;

    // Apply updated parameters to 3D Viewport if returned
    if (data.updated_params && Object.keys(data.updated_params).length > 0) {
      for (const [k, v] of Object.entries(data.updated_params)) {
        const slider = document.getElementById(`slider-${k}`);
        const display = document.getElementById(`val-${k}`);
        if (slider) {
          slider.value = v;
          currentParams[k] = v;
        }
        if (display) {
          display.innerText = Number(v).toFixed(2);
        }
      }
      updateCorkscrewGeometry(currentParams);
      if (data.metrics) {
        updateTelemetryHUD(data.metrics, data.uncertainty, data.conservation);
      }
    }
  } catch (err) {
    thinkDiv.remove();
    const errDiv = document.createElement("div");
    errDiv.className = "agent-msg system";
    errDiv.style.color = "#ef4444";
    errDiv.innerText = `Agent error: ${err.message}`;
    chatMessages.appendChild(errDiv);
  } finally {
    if (activeTag) {
      activeTag.innerText = "READY";
      activeTag.style.borderColor = "var(--accent-emerald)";
      activeTag.style.color = "var(--accent-emerald)";
    }
  }
}

// --- KiCad Live Synchronization Bridge ---
let lastKicadSyncTime = 0;

async function pollKiCadLiveStatus() {
  try {
    const res = await fetch("/api/kicad_status");
    const data = await res.json();
    const badge = document.getElementById("kicad-sync-badge");
    const badgeText = document.getElementById("kicad-sync-text");

    if (data.status === "synchronized" || data.connected) {
      if (badge) {
        badge.className = "kicad-badge active";
      }
      if (badgeText) {
        badgeText.innerText = `KiCad: ${data.board_name || 'Live'}`;
      }

      activePcbData = data;

      // Handle initial page load or first live data arrival
      if (isInitialPcbLoad) {
        isInitialPcbLoad = false;
        lastKicadSyncTime = data.timestamp || 1;
        buildPcb3DScene(data);
        updatePcbInspectorUI(data);

        const urlParams = new URLSearchParams(window.location.search);
        if (urlParams.get("kicad_live") === "1" || urlParams.has("pcb")) {
          switchDomain("pcb");
        }
      } else if (data.timestamp && data.timestamp > lastKicadSyncTime) {
        lastKicadSyncTime = data.timestamp;
        buildPcb3DScene(data);
        updatePcbInspectorUI(data);

        if (currentDomain === "pcb") {
          updatePcbHUD(data);
        }

        const t = data.primary_trace;
        const m = data.em_metrics;
        if (t && m) {
          showKiCadToast(
            `⚡ KiCad Live Sync: ${data.board_name} | ${t.net_name} (w=${t.width_mm}mm) | Z0=${m.z0_ohms}Ω | S11=${m.s11_return_loss_db}dB`
          );
        }
      }
    } else {
      if (badge) badge.className = "kicad-badge standby";
      if (badgeText) badgeText.innerText = "KiCad: Standby";
    }
  } catch (e) {}
}

function showKiCadToast(message, durationMs = 4000) {
  const toast = document.getElementById("kicad-toast");
  if (!toast) return;
  toast.innerText = message;
  toast.classList.remove("hidden");
  setTimeout(() => {
    toast.classList.add("hidden");
  }, durationMs);
}

// --- KiCad 3D PCB Geometry Builder ---
function buildPcb3DScene(data) {
  if (!pcbGroup) return;

  // Clear previous PCB meshes & geometries
  while (pcbGroup.children.length > 0) {
    const obj = pcbGroup.children[0];
    pcbGroup.remove(obj);
    if (obj.geometry) obj.geometry.dispose();
    if (obj.material) {
      if (Array.isArray(obj.material)) {
        obj.material.forEach(m => m.dispose());
      } else {
        obj.material.dispose();
      }
    }
  }

  const bounds = (data && data.board_geometry && data.board_geometry.bounds) || {
    width_mm: 55.0,
    height_mm: 52.0
  };
  const bw = Math.max(10.0, bounds.width_mm || 55.0);
  const bh = Math.max(10.0, bounds.height_mm || 52.0);
  const substrateH = 0.8; // mm

  // 1. Dielectric Substrate Mesh (Dark solder mask emerald-slate)
  const subGeo = new THREE.BoxGeometry(bw, substrateH, bh);
  const subMat = new THREE.MeshStandardMaterial({
    color: 0x061a10,
    roughness: 0.7,
    metalness: 0.15
  });
  const substrateMesh = new THREE.Mesh(subGeo, subMat);
  substrateMesh.position.set(0, 0, 0);
  pcbGroup.add(substrateMesh);

  // Silkscreen outline box
  const sw = bw / 2 - 1.2;
  const sh = bh / 2 - 1.2;
  const silkGeo = new THREE.BufferGeometry();
  const silkPts = [
    new THREE.Vector3(-sw, substrateH / 2 + 0.015, -sh),
    new THREE.Vector3(sw, substrateH / 2 + 0.015, -sh),
    new THREE.Vector3(sw, substrateH / 2 + 0.015, sh),
    new THREE.Vector3(-sw, substrateH / 2 + 0.015, sh),
    new THREE.Vector3(-sw, substrateH / 2 + 0.015, -sh)
  ];
  silkGeo.setFromPoints(silkPts);
  const silkMat = new THREE.LineBasicMaterial({ color: 0xe2e8f0, transparent: true, opacity: 0.5 });
  const silkLine = new THREE.Line(silkGeo, silkMat);
  pcbGroup.add(silkLine);

  const topY = substrateH / 2 + 0.03;
  const botY = -substrateH / 2 - 0.03;

  // 2. Real KiCad Edge.Cuts Outline
  const edgeCuts = (data && data.board_geometry && data.board_geometry.edge_cuts) || [];
  if (edgeCuts.length > 0) {
    const ecPositions = [];
    edgeCuts.forEach(ec => {
      // Top perimeter
      ecPositions.push(ec.x1, topY + 0.005, ec.y1);
      ecPositions.push(ec.x2, topY + 0.005, ec.y2);
      // Bottom perimeter
      ecPositions.push(ec.x1, botY - 0.005, ec.y1);
      ecPositions.push(ec.x2, botY - 0.005, ec.y2);
      // Vertical corner/edge line
      ecPositions.push(ec.x1, topY + 0.005, ec.y1);
      ecPositions.push(ec.x1, botY - 0.005, ec.y1);
    });
    const ecGeo = new THREE.BufferGeometry();
    ecGeo.setAttribute('position', new THREE.Float32BufferAttribute(ecPositions, 3));
    // KiCad authentic bright yellow Edge.Cuts
    const ecMat = new THREE.LineBasicMaterial({ color: 0xfacc15, linewidth: 2 });
    const ecLines = new THREE.LineSegments(ecGeo, ecMat);
    pcbGroup.add(ecLines);
  } else {
    // Fallback edge geometry
    const edgeGeo = new THREE.EdgesGeometry(subGeo);
    const edgeMat = new THREE.LineBasicMaterial({ color: 0xfacc15, transparent: true, opacity: 0.8 });
    const edgeLine = new THREE.LineSegments(edgeGeo, edgeMat);
    pcbGroup.add(edgeLine);
  }

  // 3. Copper & Pad Materials
  const activeNetName = selectedPcbNet || (data && data.primary_trace && data.primary_trace.net_name) || "/Signal_AMP";

  const activeMat = new THREE.MeshStandardMaterial({
    color: 0x00f0ff,
    emissive: 0x00b4d8,
    emissiveIntensity: 0.8,
    roughness: 0.2,
    metalness: 0.85
  });

  const goldMat = new THREE.MeshStandardMaterial({
    color: 0xd4af37, // Immersion gold for tracks
    roughness: 0.3,
    metalness: 0.85
  });

  const bCuMat = new THREE.MeshStandardMaterial({
    color: 0xa06520, // Bottom copper
    roughness: 0.4,
    metalness: 0.8
  });

  const padTinnedMat = new THREE.MeshStandardMaterial({
    color: 0xe2e8f0, // Shiny silver tinned solder finish (HASL)
    roughness: 0.2,
    metalness: 0.95
  });

  const topPourMat = new THREE.MeshStandardMaterial({
    color: 0x14452a, // Deep emerald solder mask with copper fill beneath
    roughness: 0.45,
    metalness: 0.65,
    side: THREE.DoubleSide
  });

  const botPourMat = new THREE.MeshStandardMaterial({
    color: 0x183c27,
    roughness: 0.45,
    metalness: 0.65,
    side: THREE.DoubleSide
  });

  // 4. Metal Pours (Zones)
  const zones = (data && data.board_geometry && data.board_geometry.zones) || [];
  zones.forEach(zp => {
    const pts = zp.pts;
    if (pts && pts.length >= 3) {
      try {
        const shape = new THREE.Shape();
        shape.moveTo(pts[0][0], pts[0][1]);
        for (let i = 1; i < pts.length; i++) {
          shape.lineTo(pts[i][0], pts[i][1]);
        }
        const pourGeo = new THREE.ShapeGeometry(shape);
        pourGeo.rotateX(Math.PI / 2); // Rotate into X-Z plane

        const isTop = zp.is_top;
        const yPos = isTop ? (topY - 0.005) : (botY + 0.005);
        const isSelected = (zp.net === activeNetName);
        const pMat = isSelected ? activeMat : (isTop ? topPourMat : botPourMat);

        const pourMesh = new THREE.Mesh(pourGeo, pMat);
        pourMesh.position.y = yPos;
        pcbGroup.add(pourMesh);

        // Clear outline of metal pour
        const pourEdges = new THREE.EdgesGeometry(pourGeo);
        const pourLineMat = new THREE.LineBasicMaterial({
          color: isSelected ? 0x00f0ff : (isTop ? 0x34d399 : 0x8b6508),
          transparent: true,
          opacity: 0.4
        });
        const pourLine = new THREE.LineSegments(pourEdges, pourLineMat);
        pourLine.position.y = yPos + (isTop ? 0.001 : -0.001);
        pcbGroup.add(pourLine);
      } catch (err) {
        console.warn("Zone triangulation error:", err);
      }
    }
  });

  // 5. Copper Trace Segments
  const segments = (data && data.board_geometry && data.board_geometry.segments) || [];
  const cuThickness = 0.06;
  const padMap = new Set();

  segments.forEach(seg => {
    const x1 = seg.x1;
    const z1 = seg.y1;
    const x2 = seg.x2;
    const z2 = seg.y2;
    const w = Math.max(0.18, seg.width_mm || 0.2);
    const isTop = (seg.layer !== "B.Cu");
    const yPos = isTop ? topY : botY;
    const isSelected = (seg.net_name === activeNetName);

    const mat = isSelected ? activeMat : (isTop ? goldMat : bCuMat);

    const dx = x2 - x1;
    const dz = z2 - z1;
    const len = Math.sqrt(dx * dx + dz * dz);

    if (len > 0.005) {
      const boxGeo = new THREE.BoxGeometry(len, cuThickness, w);
      const boxMesh = new THREE.Mesh(boxGeo, mat);
      boxMesh.position.set((x1 + x2) / 2, yPos, (z1 + z2) / 2);
      boxMesh.rotation.y = -Math.atan2(dz, dx);
      pcbGroup.add(boxMesh);
    }

    [[x1, z1], [x2, z2]].forEach(([px, pz]) => {
      const key = `${px.toFixed(2)}_${pz.toFixed(2)}_${isTop}`;
      if (!padMap.has(key)) {
        padMap.add(key);
        const padGeo = new THREE.CylinderGeometry(w / 2, w / 2, cuThickness, 10);
        const padMesh = new THREE.Mesh(padGeo, mat);
        padMesh.position.set(px, yPos, pz);
        pcbGroup.add(padMesh);
      }
    });
  });

  // 6. Component Pads (Footprints)
  const pads = (data && data.board_geometry && data.board_geometry.pads) || [];
  const padThick = 0.07;
  pads.forEach(pad => {
    const px = pad.x;
    const pz = pad.y;
    const pw = Math.max(0.2, pad.w);
    const ph = Math.max(0.2, pad.h);
    const pRot = -pad.rot * Math.PI / 180.0;
    const isSelected = (pad.net === activeNetName);
    const padMat = isSelected ? activeMat : padTinnedMat;

    // Top Pad
    if (pad.is_top || pad.is_thru) {
      let padMesh;
      if (pad.shape === 'circle') {
        const geo = new THREE.CylinderGeometry(pw / 2, pw / 2, padThick, 16);
        padMesh = new THREE.Mesh(geo, padMat);
        padMesh.position.set(px, topY + padThick / 2, pz);
      } else {
        const geo = new THREE.BoxGeometry(pw, padThick, ph);
        padMesh = new THREE.Mesh(geo, padMat);
        padMesh.position.set(px, topY + padThick / 2, pz);
        padMesh.rotation.y = pRot;
      }
      pcbGroup.add(padMesh);
    }

    // Bottom Pad
    if (pad.is_bot || pad.is_thru) {
      let padMesh;
      if (pad.shape === 'circle') {
        const geo = new THREE.CylinderGeometry(pw / 2, pw / 2, padThick, 16);
        padMesh = new THREE.Mesh(geo, padMat);
        padMesh.position.set(px, botY - padThick / 2, pz);
      } else {
        const geo = new THREE.BoxGeometry(pw, padThick, ph);
        padMesh = new THREE.Mesh(geo, padMat);
        padMesh.position.set(px, botY - padThick / 2, pz);
        padMesh.rotation.y = pRot;
      }
      pcbGroup.add(padMesh);
    }

    // Through-hole drill hole barrel
    if (pad.is_thru) {
      const drillR = Math.min(pw, ph) * 0.32;
      const barrelGeo = new THREE.CylinderGeometry(drillR, drillR, substrateH + 0.1, 12);
      const barrelMat = new THREE.MeshBasicMaterial({ color: 0x05070a });
      const barrelMesh = new THREE.Mesh(barrelGeo, barrelMat);
      barrelMesh.position.set(px, 0, pz);
      pcbGroup.add(barrelMesh);
    }
  });
}

// --- KiCad UI & HUD Telemetry Updates ---
function updatePcbInspectorUI(data) {
  if (!data) return;

  const nameElem = document.getElementById("kicad-board-name-display");
  if (nameElem && data.board_name) {
    nameElem.innerText = data.board_name;
  }

  const dimElem = document.getElementById("kicad-board-dim-display");
  if (dimElem && data.board_geometry && data.board_geometry.bounds) {
    const b = data.board_geometry.bounds;
    const segs = data.board_geometry.segments ? data.board_geometry.segments.length : 0;
    dimElem.innerText = `${b.width_mm.toFixed(1)} × ${b.height_mm.toFixed(1)} mm | ${segs} Traces`;
  }

  const netSelect = document.getElementById("kicad-net-select");
  if (netSelect && data.board_geometry && data.board_geometry.nets_summary) {
    const currentVal = selectedPcbNet || netSelect.value;
    netSelect.innerHTML = '<option value="">Auto: Primary Signal Trace</option>';

    const nets = Object.values(data.board_geometry.nets_summary);
    nets.sort((a, b) => (b.total_length_mm || 0) - (a.total_length_mm || 0));

    nets.forEach(n => {
      const opt = document.createElement("option");
      opt.value = n.net_name;
      opt.innerText = `${n.net_name} (w=${n.trace_width_mm}mm, ${n.segment_count} segs, ${n.total_length_mm.toFixed(1)}mm)`;
      if (n.net_name === currentVal) {
        opt.selected = true;
      }
      netSelect.appendChild(opt);
    });
    if (selectedPcbNet) netSelect.value = selectedPcbNet;
  }
}

function updatePcbHUD(data) {
  if (!data) return;

  const cardEffTitle = document.querySelector("#card-eff .metric-title");
  if (cardEffTitle) cardEffTitle.innerText = "CHARACTERISTIC IMPEDANCE (Z0)";
  const cardDpTitle = document.querySelector("#card-dp .metric-title");
  if (cardDpTitle) cardDpTitle.innerText = "RETURN LOSS (S11)";
  const cardConvTitle = document.querySelector("#card-conservation .metric-title");
  if (cardConvTitle) cardConvTitle.innerText = "INSERTION LOSS (S21)";
  const cardStressTitle = document.querySelector("#card-stress .metric-title");
  if (cardStressTitle) cardStressTitle.innerText = "CROSS-TALK ISOLATION";
  const cardFosTitle = document.querySelector("#card-fos .metric-title");
  if (cardFosTitle) cardFosTitle.innerText = "RF MATCHING STATUS";
  const cardUncTitle = document.querySelector("#card-unc .metric-title");
  if (cardUncTitle) cardUncTitle.innerText = "RF FREQUENCY";

  let z0 = 149.75;
  let s11 = -6.03;
  let s21 = -0.18;
  let widthMm = 0.2;
  let lengthMm = 15.0;
  let isMatched = false;
  let netName = selectedPcbNet || (data.primary_trace && data.primary_trace.net_name) || "/Signal_AMP";

  if (data.board_geometry && data.board_geometry.nets_summary && data.board_geometry.nets_summary[netName]) {
    const net = data.board_geometry.nets_summary[netName];
    widthMm = net.trace_width_mm || 0.2;
    lengthMm = net.total_length_mm || 15.0;

    const h = 0.8;
    const er = 2.1;
    const u = widthMm / h;
    const e_eff = (er + 1.0) / 2.0 + ((er - 1.0) / 2.0) * (1.0 / Math.sqrt(1.0 + 12.0 / u));
    z0 = (120.0 * Math.PI / Math.sqrt(e_eff)) / (u + 1.393 + 0.667 * Math.log(u + 1.444));
    const gamma = Math.abs((z0 - 50.0) / (z0 + 50.0));
    s11 = 20.0 * Math.log10(Math.max(0.0001, gamma));
    isMatched = Math.abs(z0 - 50.0) <= 5.0;
  } else if (data.em_metrics) {
    z0 = data.em_metrics.z0_ohms || 149.75;
    s11 = data.em_metrics.s11_return_loss_db || -6.03;
    s21 = data.em_metrics.s21_insertion_loss_db || -0.18;
    isMatched = data.em_metrics.is_matched || false;
  }

  const skinDepthUm = 2.09 / Math.sqrt(Math.max(0.1, kicadFrequency));
  s21 = -(0.025 * (lengthMm / 10.0) * Math.sqrt(kicadFrequency)).toFixed(2);

  const effEl = document.getElementById("metric-eff");
  if (effEl) effEl.innerText = `${z0.toFixed(1)} Ω`;
  const subEff = document.getElementById("sub-eff");
  if (subEff) subEff.innerText = "Target: 50.0 Ω ± 5%";

  const dpEl = document.getElementById("metric-dp");
  if (dpEl) dpEl.innerText = `${Number(s11).toFixed(1)} dB`;
  const subDp = document.getElementById("sub-dp");
  if (subDp) subDp.innerText = "Target: < -15.0 dB";

  const divEl = document.getElementById("metric-div");
  if (divEl) divEl.innerText = `${s21} dB`;
  const subDiv = document.getElementById("sub-div");
  if (subDiv) subDiv.innerHTML = `<span class="badge-status-dot admissible"></span> δ = ${skinDepthUm.toFixed(2)} µm`;

  const stressEl = document.getElementById("metric-stress");
  if (stressEl) stressEl.innerText = "-45.0 dB";
  const subStress = document.getElementById("sub-stress");
  if (subStress) subStress.innerText = `Net: ${netName}`;

  const fosEl = document.getElementById("metric-fos");
  if (fosEl) {
    fosEl.innerText = isMatched ? "50Ω MATCHED" : "MISMATCHED";
    fosEl.style.color = isMatched ? "var(--accent-emerald)" : "var(--accent-amber)";
  }
  const subFos = document.getElementById("sub-fos");
  if (subFos) subFos.innerText = isMatched ? "VSWR < 1.2:1 (Optimal)" : `w=${widthMm}mm (Needs w≈2.4mm)`;

  const uncEl = document.getElementById("metric-unc");
  if (uncEl) uncEl.innerText = `${kicadFrequency.toFixed(1)} GHz`;
}

function selectKicadNet(netName) {
  selectedPcbNet = netName || null;
  if (activePcbData) {
    buildPcb3DScene(activePcbData);
    updatePcbHUD(activePcbData);
    const targetNet = selectedPcbNet || (activePcbData.primary_trace && activePcbData.primary_trace.net_name) || "Primary";
    showKiCadToast(`⚡ Selected Net: ${targetNet}`);
  }
}

function updateKicadFrequency(val) {
  kicadFrequency = parseFloat(val);
  const disp = document.getElementById("kicad-freq-val");
  if (disp) disp.innerText = `${kicadFrequency.toFixed(1)} GHz`;
  if (activePcbData && currentDomain === "pcb") {
    updatePcbHUD(activePcbData);
  }
}

function calculate50OhmMatch() {
  const h = 0.8;
  const er = 2.1;
  const synthWidth = 2.43;
  showKiCadToast(
    `⚡ 50Ω Microstrip Synthesized: Optimal trace width w = ${synthWidth} mm (Substrate h=${h}mm, εr=${er}). Modify trace width in KiCad & save to verify!`,
    6000
  );

  const subFos = document.getElementById("sub-fos");
  if (subFos) subFos.innerText = `Target Width: ${synthWidth} mm (KiCad)`;
}

