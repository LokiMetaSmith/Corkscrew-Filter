# OpenAuto EM Live Bridge — KiCad Action Plugin

**OpenAuto EM Live Bridge** is an official KiCad Action Plugin (`pcbnew.ActionPlugin`) compatible with **KiCad 10.0**, 9.0, 8.0, and 7.0. It bridges KiCad PCB Editor directly to real-time electromagnetic (EM) and signal/power integrity (SI/PI) simulation.

Whenever you modify and save a board in KiCad (`Ctrl+S`), the plugin automatically re-evaluates high-speed trace physics, exports simulation handoff files (Siemens HyperLynx `.hyp`, openEMS 3D FDTD `.py`, and OpenSCAD `.scad`), and broadcasts live metrics to an interactive WebGL HUD with **<100 ms feedback latency**.

---

## Key Capabilities

* **Zero-Lag Interactive Editing Loop**: Modifying microstrip trace width ($w$) or differential pair spacing ($s$) and saving in KiCad instantly updates impedance gauges and S-parameter plots in your browser.
* **Controlled Impedance Physics ($<5\text{ ms}$)**:
  * **Single-Ended Microstrip**: Wheeler and Hammerstad conformal mapping with finite copper thickness ($t$) corrections.
  * **Coupled Differential Pairs**: Odd/even mode impedances ($Z_{odd}, Z_{even}$) and differential impedance ($Z_{diff} = 2 Z_{odd}$) with edge-to-edge spacing ($s$).
  * **Frequency-Dependent Loss**: Skin depth attenuation ($\delta = \sqrt{1/\pi f \mu \sigma}$), conductor loss ($\alpha_c$), dielectric loss ($\alpha_d$), and return loss ($S_{11}$).
* **Multi-Solver Simulation Export**:
  * **Siemens HyperLynx (`.hyp`)**: Native high-end EDA intermediate format for HyperLynx, Ansys HFSS, and Keysight ADS.
  * **openEMS FDTD (`.py`)**: Ready-to-run 3D finite-difference time-domain simulation script with excitation ports and absorbing boundary conditions (PML).
  * **OpenSCAD Solid Geometry (`.scad`)**: Full 3D solid model of dielectric substrate and etched copper traces.
* **Decoupled Pure-Python S-Expression Parser**: Tokenizes `.kicad_pcb` files with zero external C++ dependencies, extracting board outlines (`Edge.Cuts`), layer dielectric stackups, and net geometries.
* **KiCad 10.0 Native Compatibility**: Built-in `wx.GetApp()` GUI guards preventing wxWidgets C++ assertion faults (`assert "PgmOrNull()"`), bundled physics engine running on KiCad 10's internal Python 3.11 + NumPy runtime.

---

## Directory Structure

```
kicad_plugin/
├── __init__.py                # KiCad package entry point & GUI registration
├── action_openauto_em.py      # pcbnew.ActionPlugin implementation & toolbar button
├── em_live_watcher.py         # On-save file watcher daemon (<50ms response)
├── kicad_parser.py            # Pure-Python .kicad_pcb S-expression parser
├── eda_rf_driver.py           # Wheeler/Hammerstad & S-parameter physics engine
├── metadata.json              # Official KiCad PCM manifest (v1.0.0 for KiCad 10.0)
├── icon.png                   # 26x26 toolbar icon with RF microstrip wave symbol
├── install_plugin.py          # Cross-platform CLI auto-installer script
└── README.md                  # This documentation
```

---

## Installation

### Method 1: Automatic Installer (Recommended)

From the project root directory, run the Python auto-installer:

```bash
# On Windows (PowerShell)
python kicad_plugin/install_plugin.py

# Or with live development symlink (no file copying)
python kicad_plugin/install_plugin.py --symlink
```

You can also use the convenience scripts from the root:
```powershell
# Windows PowerShell
.\install_kicad_plugin.ps1
```
```bash
# Linux / macOS
./install_kicad_plugin.sh
```

The installer automatically searches standard KiCad user directories in order of priority:
1. **Windows**: `%APPDATA%\kicad\10.0\scripting\plugins\openauto_em_live`
   *(fallbacks: `9.0`, `8.0`, `7.0`, `6.0`)*
2. **Linux**: `~/.local/share/kicad/10.0/scripting/plugins/openauto_em_live`
3. **macOS**: `~/Library/Preferences/kicad/10.0/scripting/plugins/openauto_em_live`

#### Custom Installation Directory
To install into a specific path:
```bash
python kicad_plugin/install_plugin.py --dir "C:\custom\path\to\kicad\plugins"
```

---

### Method 2: Manual Installation

Copy the entire `kicad_plugin/` folder into your KiCad user scripting directory and rename it to `openauto_em_live`:

* **Windows**:
  ```powershell
  New-Item -ItemType Directory -Force "$env:APPDATA\kicad\10.0\scripting\plugins"
  Copy-Item -Recurse -Force "kicad_plugin" "$env:APPDATA\kicad\10.0\scripting\plugins\openauto_em_live"
  ```
* **Linux**:
  ```bash
  mkdir -p ~/.local/share/kicad/10.0/scripting/plugins
  cp -r kicad_plugin ~/.local/share/kicad/10.0/scripting/plugins/openauto_em_live
  ```
* **macOS**:
  ```bash
  mkdir -p ~/Library/Preferences/kicad/10.0/scripting/plugins
  cp -r kicad_plugin ~/Library/Preferences/kicad/10.0/scripting/plugins/openauto_em_live
  ```

---

### Method 3: KiCad Plugin and Content Manager (PCM)

The plugin includes an official `metadata.json` compliant with KiCad's PCM schema. To package as a ZIP for manual PCM installation:

```bash
cd kicad_plugin
zip -r ../openauto_em_live_pcm.zip . -x "__pycache__/*"
```
In KiCad main window:
1. Open **Plugin and Content Manager** (PCM).
2. Click **Install from File...**
3. Select `openauto_em_live_pcm.zip` and click **Apply Changes**.

---

## Step-by-Step Usage Guide

### 1. Launch the Simulation Server
Before or after opening KiCad, start the local simulation server from the repository root:
```bash
python run_viewer.py
```
This serves the WebGL HUD and REST synchronization endpoints at `http://127.0.0.1:8080`.

### 2. Activate the Plugin in KiCad
1. Open **KiCad 10 PCB Editor** (`pcbnew`).
2. If KiCad was already running, reload plugins via:
   **Tools** $\rightarrow$ **External Plugins** $\rightarrow$ **Refresh Plugins**.
3. A new toolbar button **OpenAuto EM Live Bridge** will appear on your top toolbar:
   ![Icon](icon.png)
4. Click the toolbar button. KiCad will:
   * Detect the currently open `.kicad_pcb` board file.
   * Start the background `EMLiveSyncDaemon` watching file modification timestamps.
   * Automatically launch your default browser to `http://127.0.0.1:8080?kicad_live=1`.
   * Display the live status pill badge in the WebGL HUD: `KiCad EM Sync: ACTIVE`.

### 3. Edit Traces with Instant Real-Time Feedback
* Select a high-speed RF trace or differential pair in KiCad.
* Adjust trace width (e.g. change $w = 3.0\text{ mm}$ to $w = 1.5\text{ mm}$) or change differential pair pitch.
* Press **Ctrl+S** to save the layout.
* Within **<100 ms**:
  * The WebGL HUD shows a slide-in toast notification:
    > **KiCad EM Sync**: `Board saved! Microstrip Z0 = 72.16 Ω | S11 = -14.83 dB`
  * The characteristic impedance meters and return loss dials update immediately.
  * Fresh simulation bridge files (`artifacts/*_live.hyp`, `artifacts/*_openems.py`) are generated in the background.

---

## REST API Integration

The simulation server (`viewer/server.py`) provides two dedicated endpoints for KiCad synchronization:

| Endpoint | Method | Payload | Description |
| :--- | :---: | :--- | :--- |
| `/api/kicad_sync` | `POST` | `{"pcb_file": str, "em_metrics": dict, "artifacts": dict}` | Ingests live board geometry and RF metrics from `EMLiveSyncDaemon`. |
| `/api/kicad_status` | `GET` | *None* | Returns `{"connected": bool, "board_file": str, "em_metrics": dict}` for WebGL HUD polling. |

---

## Verification & Testing

To run the automated verification suite covering ActionPlugin registration, S-expression parsing, live file watching, and REST synchronization:

```bash
# Run standalone test suite
python verify_kicad_plugin.py
```

### Verified Test Matrix:
* **Test 1: ActionPlugin & PCM Manifest**: Validates PCM schema versioning (`kicad_version: 10.0`), button hooks, and PNG icon asset.
* **Test 2: S-Expression Parser**: Parses stackup parameters ($h, \epsilon_r, t$) and detects differential pair traces (`RF_IN_POS` / `RF_IN_NEG`).
* **Test 3: On-Save Watcher & EM Engine**: Modifies board file from $w=3.043\text{ mm}$ ($Z_0=50.0\,\Omega$) to $w=1.5\text{ mm}$ ($Z_0=72.16\,\Omega$), detecting and recalculating in $<100\text{ ms}$.
* **Test 4: Real-Time Server Sync**: Verifies `/api/kicad_sync` and `/api/kicad_status` state transitions and WebGL telemetry formatting.
* **Test 5: Auto-Installer Discovery**: Verifies resolution of KiCad 10.0, 9.0, 8.0, and 7.0 application paths.

All tests execute with **100% pass rate** in both standard Python virtual environments and KiCad 10's native Python runtime.
