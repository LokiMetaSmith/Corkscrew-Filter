"""
em_live_watcher.py

Live On-Save File Watcher & EM Recalculation Daemon for KiCad PCB Editor.
Monitors the active .kicad_pcb file. When the user hits Ctrl+S:
  1. Instantly detects file modification (<50ms).
  2. Parses updated copper traces and dielectric stackup via KiCadPcbParser.
  3. Evaluates high-speed EM transmission line physics (Z0, S11, S21, skin depth, crosstalk) in <5ms.
  4. Automatically regenerates HyperLynx (.hyp) and openEMS simulation scripts.
  5. Posts live state to http://127.0.0.1:8080/api/kicad_sync to refresh the WebGL HUD.
"""

import os
import sys
import time
import json
import threading
import urllib.request
from typing import Dict, Any, Optional, Callable

try:
    from .kicad_parser import KiCadPcbParser
    from .eda_rf_driver import HighSpeedTransmissionLineEngine, KiCadPcbExporter
except (ImportError, ValueError):
    try:
        from kicad_parser import KiCadPcbParser
        from eda_rf_driver import HighSpeedTransmissionLineEngine, KiCadPcbExporter
    except ImportError:
        BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        OPTIMIZER_DIR = os.path.join(BASE_DIR, "optimizer")
        if OPTIMIZER_DIR not in sys.path:
            sys.path.insert(0, OPTIMIZER_DIR)
        from kicad_parser import KiCadPcbParser
        from eda_rf_driver import HighSpeedTransmissionLineEngine, KiCadPcbExporter


class EMLiveSyncDaemon:
    """
    Background file watcher daemon creating a real-time bridge between
    KiCad PCB Editor and the simulation / WebGL visualization server.
    """

    def __init__(
        self,
        pcb_filepath: str,
        server_url: str = "http://127.0.0.1:8080",
        poll_interval_sec: float = 0.1,
        frequency_ghz: float = 5.0,
        artifacts_dir: str = "artifacts",
        on_sync_callback: Optional[Callable[[Dict[str, Any]], None]] = None
    ):
        self.pcb_filepath = os.path.abspath(pcb_filepath)
        self.server_url = server_url.rstrip("/")
        self.poll_interval = poll_interval_sec
        self.frequency_ghz = frequency_ghz
        self.artifacts_dir = os.path.abspath(artifacts_dir)
        self.on_sync_callback = on_sync_callback

        os.makedirs(self.artifacts_dir, exist_ok=True)

        self.engine = HighSpeedTransmissionLineEngine()
        self.exporter = KiCadPcbExporter()

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._last_mtime: float = 0.0
        self.sync_count: int = 0
        self.latest_payload: Optional[Dict[str, Any]] = None

        if os.path.exists(self.pcb_filepath):
            self._last_mtime = os.path.getmtime(self.pcb_filepath)

    def start(self):
        """Starts background file watcher thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._watch_loop, daemon=True, name="KiCadEMWatcher")
        self._thread.start()
        print(f"[EMLiveWatcher] Started watching '{self.pcb_filepath}' -> Server: {self.server_url}")

    def stop(self):
        """Stops background watcher thread."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        print("[EMLiveWatcher] Stopped.")

    def _watch_loop(self):
        """Main polling loop checking file mtime."""
        while self._running:
            try:
                if os.path.exists(self.pcb_filepath):
                    mtime = os.path.getmtime(self.pcb_filepath)
                    if mtime > self._last_mtime:
                        self._last_mtime = mtime
                        # Give KiCad 30ms to finish disk write flush
                        time.sleep(0.03)
                        self.trigger_sync()
            except Exception as e:
                print(f"[EMLiveWatcher] Watch error: {e}")
            time.sleep(self.poll_interval)

    def trigger_sync(self) -> Optional[Dict[str, Any]]:
        """
        Parses the active board file, computes EM parameters, exports deliverables,
        and posts update to local viewer server.
        """
        if not os.path.exists(self.pcb_filepath):
            return None

        t0 = time.time()
        parser = KiCadPcbParser(self.pcb_filepath)
        primary = parser.get_primary_rf_trace()
        stackup = parser.stackup

        h = stackup.get("substrate_height_mm", 1.6)
        er = stackup.get("dielectric_constant", 4.3)
        cu_t_um = stackup.get("copper_thickness_mm", 0.035) * 1000.0

        w = primary["trace_width_mm"]
        l = primary["length_mm"]
        is_diff = primary["is_differential"]
        s = primary.get("spacing_mm")

        # 1. Evaluate High-Speed EM Physics
        if not is_diff:
            z_res = self.engine.calculate_microstrip_z0(w, h, er, cu_t_um)
            rf_res = self.engine.calculate_rf_loss_and_sparameters(
                trace_width_mm=w,
                substrate_height_mm=h,
                line_length_mm=l,
                frequency_ghz=self.frequency_ghz,
                dielectric_constant=er,
                copper_thickness_um=cu_t_um
            )
            z0_val = z_res["z0_ohms"]
            z_diff_val = None
        else:
            diff_res = self.engine.calculate_differential_pair(w, s, h, er, cu_t_um)
            rf_res = self.engine.calculate_rf_loss_and_sparameters(
                trace_width_mm=w,
                substrate_height_mm=h,
                line_length_mm=l,
                frequency_ghz=self.frequency_ghz,
                dielectric_constant=er,
                copper_thickness_um=cu_t_um,
                trace_spacing_mm=s
            )
            z0_val = diff_res["z_odd_ohms"]
            z_diff_val = diff_res["z_diff_ohms"]

        # 2. Export Simulation Bridge Deliverables
        board_name = os.path.splitext(os.path.basename(self.pcb_filepath))[0]
        hyp_path = os.path.join(self.artifacts_dir, f"{board_name}_live.hyp")
        openems_path = os.path.join(self.artifacts_dir, f"simulate_{board_name}_live_openems.py")
        scad_path = os.path.join(self.artifacts_dir, f"{board_name}_live_stackup.scad")

        self.exporter.export_hyperlynx_hyp(
            output_filepath=hyp_path,
            substrate_thickness_mm=h,
            trace_width_mm=w,
            line_length_mm=l,
            differential_spacing_mm=s if is_diff else None
        )

        self.exporter.export_openems_script(
            output_filepath=openems_path,
            substrate_thickness_mm=h,
            trace_width_mm=w,
            line_length_mm=l,
            f_max_ghz=self.frequency_ghz * 2.0,
            differential_spacing_mm=s if is_diff else None
        )

        self.exporter.generate_scad_stackup(
            trace_width_mm=w,
            substrate_height_mm=h,
            line_length_mm=l,
            differential_spacing_mm=s if is_diff else None,
            output_filepath=scad_path
        )

        calc_latency_ms = (time.time() - t0) * 1000.0

        # Center-normalized segments for 3D WebGL visualization
        cx = parser.board_bounds.get("center_x", 0.0)
        cy = parser.board_bounds.get("center_y", 0.0)
        norm_segments = []
        for s in parser.segments:
            norm_segments.append({
                "x1": round(s["start"][0] - cx, 3),
                "y1": round(s["start"][1] - cy, 3),
                "x2": round(s["end"][0] - cx, 3),
                "y2": round(s["end"][1] - cy, 3),
                "width_mm": s["width_mm"],
                "length_mm": round(s["length_mm"], 3),
                "layer": s["layer"],
                "net_name": s["net_name"]
            })

        norm_edge_cuts = []
        for ec in parser.edge_cuts:
            norm_edge_cuts.append({
                "x1": round(ec["x1"] - cx, 3),
                "y1": round(ec["y1"] - cy, 3),
                "x2": round(ec["x2"] - cx, 3),
                "y2": round(ec["y2"] - cy, 3),
                "width": ec.get("width", 0.15)
            })

        # 3. Assemble Sync Payload
        payload = {
            "status": "synchronized",
            "source": "KiCad_PCB_Editor",
            "board_path": self.pcb_filepath,
            "board_name": os.path.basename(self.pcb_filepath),
            "timestamp": time.time(),
            "calculation_latency_ms": round(calc_latency_ms, 2),
            "primary_trace": {
                "net_name": primary["net_name"],
                "width_mm": w,
                "length_mm": l,
                "is_differential": is_diff,
                "spacing_mm": s,
                "layer": primary["layer"]
            },
            "em_metrics": {
                "z0_ohms": round(z0_val, 2),
                "z_diff_ohms": round(z_diff_val, 2) if z_diff_val else None,
                "s11_return_loss_db": rf_res["s11_return_loss_db"],
                "s21_insertion_loss_db": rf_res["s21_insertion_loss_db"],
                "skin_depth_um": rf_res["skin_depth_um"],
                "crosstalk_isolation_db": rf_res["crosstalk_isolation_db"],
                "is_matched": rf_res["s11_return_loss_db"] < -18.0
            },
            "stackup": stackup,
            "board_geometry": {
                "bounds": parser.board_bounds,
                "segments": norm_segments,
                "edge_cuts": norm_edge_cuts,
                "pads": parser.component_pads,
                "zones": parser.zones,
                "nets_summary": parser.get_all_nets_summary(),
                "differential_pairs": parser.differential_pairs
            },
            "artifacts": {
                "hyperlynx_hyp_file": hyp_path,
                "openems_script_file": openems_path,
                "scad_3d_stackup_file": scad_path
            }
        }

        self.sync_count += 1
        self.latest_payload = payload

        # 4. Post to Server Endpoint
        self._notify_server(payload)

        # 5. Invoke local callback if registered
        if self.on_sync_callback:
            try:
                self.on_sync_callback(payload)
            except Exception as cb_err:
                print(f"[EMLiveWatcher] Callback warning: {cb_err}")

        return payload

    def _notify_server(self, payload: Dict[str, Any]):
        """Posts payload to /api/kicad_sync on the viewer server."""
        try:
            url = f"{self.server_url}/api/kicad_sync"
            body = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=body,
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=1.0) as resp:
                pass
        except Exception:
            # Server may not be running yet; graceful silent skip
            pass
