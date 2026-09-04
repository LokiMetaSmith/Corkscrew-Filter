"""
action_openauto_em.py

KiCad Action Plugin: "OpenAuto EM Live Bridge"
Installs directly into KiCad 10 / 9 / 8 / 7 PCB Editor.
Clicking the toolbar button launches live EM simulation tracking and the WebGL HUD.
"""

import os
import sys
import webbrowser
import threading
from typing import Optional

# Try importing pcbnew; provide clean mock if running in external Python
try:
    import pcbnew
    HAS_PCBNEW = True
except ImportError:
    HAS_PCBNEW = False
    class _MockActionPlugin:
        def __init__(self):
            self.name = ""
            self.category = ""
            self.description = ""
            self.show_toolbar_button = False
            self.icon_file_name = ""
        def defaults(self): pass
        def Run(self): pass
        def register(self): pass

    class pcbnew:
        ActionPlugin = _MockActionPlugin
        @staticmethod
        def GetBoard():
            class _MockBoard:
                def GetFileName(self):
                    return os.path.abspath("artifacts/optimized_transmission_line.kicad_pcb")
            return _MockBoard()
try:
    from .em_live_watcher import EMLiveSyncDaemon
except (ImportError, ValueError):
    from em_live_watcher import EMLiveSyncDaemon


class OpenAutoEMLiveActionPlugin(pcbnew.ActionPlugin):
    """
    ActionPlugin providing one-click activation of live EM simulation
    and real-time 3D WebGL telemetry synchronization from inside KiCad PCB Editor.
    """

    daemon_instance: Optional[EMLiveSyncDaemon] = None

    def defaults(self):
        self.name = "OpenAuto EM Live Bridge"
        self.category = "Simulation & RF Analysis"
        self.description = "Real-time electromagnetic & SI/PI simulation loop on save for KiCad PCB traces"
        self.show_toolbar_button = True
        self.icon_file_name = os.path.join(os.path.dirname(__file__), "icon.png")

    def Run(self):
        """Executed when user clicks the KiCad toolbar button or menu action."""
        print("\n=======================================================")
        print("  [OpenAuto-EM] Action Plugin Triggered in KiCad")
        print("=======================================================")

        board = pcbnew.GetBoard()
        if not board:
            print("[OpenAuto-EM] Error: No active board found.")
            return

        pcb_path = board.GetFileName()
        if not pcb_path or not os.path.exists(pcb_path):
            print("[OpenAuto-EM] Notice: Please save your board layout file (.kicad_pcb) first.")
            return

        print(f"[OpenAuto-EM] Active Board Layout: {pcb_path}")

        # 1. Stop any existing watcher instance
        if OpenAutoEMLiveActionPlugin.daemon_instance is not None:
            OpenAutoEMLiveActionPlugin.daemon_instance.stop()

        # 2. Launch background EMLiveSyncDaemon
        server_url = "http://127.0.0.1:8080"
        daemon = EMLiveSyncDaemon(
            pcb_filepath=pcb_path,
            server_url=server_url,
            poll_interval_sec=0.1,
            frequency_ghz=5.0
        )
        daemon.start()
        OpenAutoEMLiveActionPlugin.daemon_instance = daemon

        # 3. Perform initial immediate synchronization
        initial_sync = daemon.trigger_sync()
        if initial_sync:
            metrics = initial_sync["em_metrics"]
            trace = initial_sync["primary_trace"]
            print(f"[OpenAuto-EM] Initial Sync Complete:")
            print(f"  - Trace: {trace['net_name']} (Width: {trace['width_mm']} mm)")
            print(f"  - Z0: {metrics['z0_ohms']} Ohms | S11: {metrics['s11_return_loss_db']} dB")
            print(f"  - Artifacts: {initial_sync['artifacts']}")

        # 4. Open browser to real-time WebGL HUD with ?kicad_live=1
        viewer_url = f"{server_url}?kicad_live=1"
        print(f"[OpenAuto-EM] Opening real-time visualizer: {viewer_url}")
        try:
            webbrowser.open(viewer_url)
        except Exception as e:
            print(f"[OpenAuto-EM] Notice: Could not open browser automatically: {e}")


# Register plugin when loaded inside KiCad GUI
if HAS_PCBNEW:
    try:
        import wx
        if wx.GetApp() is not None:
            OpenAutoEMLiveActionPlugin().register()
    except Exception:
        pass

