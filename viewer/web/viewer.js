/* viewer/web/viewer.js — Atlas Fields Studio WebGL Engine */

// --- Global State ---
let scene, camera, renderer, controls;
let corkscrewMesh = null;
let particleSystem = null;
let particlePositions, particleVelocities, particleLifetimes;
const N_PARTICLES = 600;

let currentDomain = "cfd";
let currentParams = {};
let paramDefs = {};
let activeColormap = "Turbo";
let wireframeMode = false;
let showParticles = true;
let isPredicting = false;
let pendingPredict = false;

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

  // Setup periodic queue polling
  setInterval(pollSolverQueue, 2000);
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
  if (!particleSystem || !showParticles) return;

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

  // Slow subtle rotation
  if (corkscrewMesh) {
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
  isPredicting = true;
  try {
    const t0 = performance.now();
    const res = await fetch("/api/predict", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ params: currentParams })
    });
    const data = await res.json();
    const tElapsed = Math.round(performance.now() - t0);

    document.getElementById("backend-status").innerText = `Surrogate Live (${tElapsed}ms)`;
    updateTelemetryHUD(data.metrics, data.uncertainty);
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

function updateTelemetryHUD(metrics, uncertainty) {
  if (!metrics) return;

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

function resetCamera() {
  camera.position.set(40, 35, 60);
  controls.target.set(0, 0, 0);
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
