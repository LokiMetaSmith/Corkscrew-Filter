"""
verify_viewer_api.py

Automated programmatic test suite for Atlas Fields Studio WebGL Viewer Server.
Verifies all REST API endpoints and static asset delivery.
"""

import os
import sys
import time
import json
import threading
import urllib.request
import urllib.error

sys.path.insert(0, os.path.abspath("viewer"))
sys.path.insert(0, os.path.abspath("optimizer"))

from server import create_server


def test_viewer_server_apis():
    print("\n--- Test: Viewer Server REST APIs & Static Assets ---")
    port = 8899
    server, opt = create_server(port=port, domain="cfd")

    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    time.sleep(0.3)

    base_url = f"http://127.0.0.1:{port}"

    try:
        # 1. Test Static Index Delivery
        req = urllib.request.Request(f"{base_url}/")
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200
            html = resp.read().decode("utf-8")
            assert "Atlas Fields Studio" in html
            print("  [PASS] GET / served HTML successfully.")

        # 2. Test CSS & JS Assets
        with urllib.request.urlopen(f"{base_url}/viewer.css") as resp:
            assert resp.status == 200
            print("  [PASS] GET /viewer.css served successfully.")

        with urllib.request.urlopen(f"{base_url}/viewer.js") as resp:
            assert resp.status == 200
            print("  [PASS] GET /viewer.js served successfully.")

        # 3. Test GET /api/status
        with urllib.request.urlopen(f"{base_url}/api/status") as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode("utf-8"))
            assert data["status"] == "ready"
            assert data["domain"] == "cfd"
            assert "number_of_complete_revolutions" in data["param_defs"]
            print(f"  [PASS] GET /api/status: domain={data['domain']}, samples={data['surrogate_samples']}")

        # 4. Test POST /api/predict (Sub-20ms surrogate evaluation)
        p_query = {
            "number_of_complete_revolutions": 2.5,
            "helix_path_radius_mm": 2.2,
            "blade_chamfer_mm": 0.6
        }
        t0 = time.time()
        req = urllib.request.Request(
            f"{base_url}/api/predict",
            data=json.dumps({"params": p_query}).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode("utf-8"))
            t_ms = (time.time() - t0) * 1000.0
            assert "metrics" in data
            assert "delta_p" in data["metrics"]
            assert "separation_efficiency" in data["metrics"]
            print(f"  [PASS] POST /api/predict in {t_ms:.2f} ms: delta_p={data['metrics']['delta_p']:.1f}, eff={data['metrics']['separation_efficiency']:.2f}%")

        # 5. Test POST /api/optimize (Sub-50ms analytic gradient inverse design)
        t0 = time.time()
        req = urllib.request.Request(
            f"{base_url}/api/optimize",
            data=json.dumps({"seed_params": p_query}).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode("utf-8"))
            t_ms = (time.time() - t0) * 1000.0
            assert "optimal_params" in data
            print(f"  [PASS] POST /api/optimize in {t_ms:.2f} ms: optimal_revolutions={data['optimal_params'].get('number_of_complete_revolutions'):.2f}")

        # 6. Test POST /api/dispatch & GET /api/poll
        req = urllib.request.Request(
            f"{base_url}/api/dispatch",
            data=json.dumps({"params": p_query, "mock": True}).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode("utf-8"))
            job_id = data.get("job_id")
            assert job_id is not None
            print(f"  [PASS] POST /api/dispatch: enqueued job {job_id}")

        # Wait briefly for worker and poll
        time.sleep(0.2)
        with urllib.request.urlopen(f"{base_url}/api/poll") as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode("utf-8"))
            print(f"  [PASS] GET /api/poll: retrieved {len(data['completed'])} completed jobs.")

    finally:
        opt.shutdown()
        server.shutdown()
        print("  Server stopped cleanly.")


if __name__ == "__main__":
    print("=================================================================")
    print("Starting Viewer Server Verification...")
    print("=================================================================")
    test_viewer_server_apis()
    print("\n=================================================================")
    print("ALL VIEWER API TESTS PASSED SUCCESSFULLY!")
    print("=================================================================")
