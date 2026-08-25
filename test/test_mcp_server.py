import os
import json
import unittest
import tempfile
from unittest.mock import patch, MagicMock

import optimizer.mcp_server as mcp_server


class TestMCPServer(unittest.TestCase):
    def test_list_available_configs(self):
        configs = mcp_server.list_available_configs()
        self.assertIsInstance(configs, list)
        self.assertGreater(len(configs), 0)
        # Verify corkscrew config is present
        paths = [c.get("path") for c in configs]
        self.assertTrue(any("corkscrew" in p for p in paths))

    def test_resources_and_prompts(self):
        # Test config resource
        config_text = mcp_server.read_corkscrew_config_resource()
        self.assertIsInstance(config_text, str)
        self.assertIn("geometry", config_text)

        # Test log resource
        log_text = mcp_server.read_latest_log_resource()
        self.assertIsInstance(log_text, str)

        # Test notes resource
        notes_text = mcp_server.read_schema_notes_resource()
        self.assertIsInstance(notes_text, str)

        # Test prompts
        prompt1 = mcp_server.analyze_simulation_results()
        self.assertIn("INSTRUCTIONS", prompt1)

        prompt2 = mcp_server.schema_surrogate_reasoning()
        self.assertIn("PHYSICIST NOTES", prompt2)

    def test_get_harness_status_empty(self):
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as tf:
            temp_db = tf.name

        try:
            status = mcp_server.get_harness_status(db_path=temp_db)
            self.assertEqual(status["total_runs"], 0)
            self.assertEqual(status["top_runs"], [])
            self.assertIsNone(status["latest_run"])
        finally:
            if os.path.exists(temp_db):
                os.remove(temp_db)

    def test_get_harness_status_with_history(self):
        with tempfile.NamedTemporaryFile(mode='w+', suffix=".jsonl", delete=False) as tf:
            run_data = {
                "id": "test_run_123",
                "iteration": 0,
                "parameters": {"screw_OD_mm": 50},
                "metrics": {"separation_efficiency": 95.0, "pressure_drop": 0.5},
                "timestamp": 1234567890
            }
            tf.write(json.dumps(run_data) + "\n")
            temp_db = tf.name

        try:
            status = mcp_server.get_harness_status(db_path=temp_db)
            self.assertEqual(status["total_runs"], 1)
            self.assertIsNotNone(status["latest_run"])
            self.assertEqual(status["latest_run"]["id"], "test_run_123")

            details = mcp_server.get_run_details("test_run_123", db_path=temp_db)
            self.assertEqual(details["status"], "success")
            self.assertEqual(details["run"]["id"], "test_run_123")

            not_found = mcp_server.get_run_details("nonexistent_id", db_path=temp_db)
            self.assertEqual(not_found["status"], "error")
        finally:
            if os.path.exists(temp_db):
                os.remove(temp_db)

    @patch("optimizer.mcp_server.run_simulation")
    @patch("optimizer.mcp_server.PhysicsEngineFactory.get_driver")
    @patch("optimizer.mcp_server.ScadDriver")
    def test_run_simulation_tool(self, mock_scad_driver, mock_get_driver, mock_run_sim):
        mock_run_sim.return_value = (
            {"separation_efficiency": 99.0},
            ["render1.png"],
            "solid.stl",
            "fluid.stl",
            "vtk.zip"
        )

        res = mcp_server.run_simulation_tool(
            config_file="configs/corkscrew_config.yaml",
            params={"screw_OD_mm": 40.0},
            dry_run=True
        )

        self.assertEqual(res["status"], "success")
        self.assertEqual(res["parameters"], {"screw_OD_mm": 40.0})
        self.assertEqual(res["metrics"], {"separation_efficiency": 99.0})
        self.assertEqual(res["images"], ["render1.png"])

    def test_validate_parameters_tool(self):
        valid_res = mcp_server.validate_parameters_tool({
            "helix_path_radius_mm": 12.0,
            "helix_profile_radius_mm": 5.0,
            "helix_void_profile_radius_mm": 3.0
        })
        self.assertTrue(valid_res["is_valid"])

        invalid_res = mcp_server.validate_parameters_tool({
            "helix_path_radius_mm": 5.0,
            "helix_profile_radius_mm": 12.0
        })
        self.assertFalse(invalid_res["is_valid"])
        self.assertIsNotNone(invalid_res["error"])

    @patch("optimizer.mcp_server.LLMAgent.suggest_parameters")
    def test_suggest_parameters_tool(self, mock_suggest):
        mock_suggest.return_value = {"helix_path_radius_mm": 10.0}
        res = mcp_server.suggest_parameters_tool(config_file="configs/corkscrew_config.yaml", count=1)
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["suggestions"], [{"helix_path_radius_mm": 10.0}])

    def test_generate_training_dataset_tool(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = os.path.join(temp_dir, "test_log.jsonl")
            out_path = os.path.join(temp_dir, "dataset.jsonl")

            with open(log_path, "w") as f:
                f.write(json.dumps({
                    "id": "run1",
                    "iteration": 0,
                    "timestamp": 100,
                    "parameters": {"helix_path_radius_mm": 10.0},
                    "metrics": {"separation_efficiency": 90.0}
                }) + "\n")
                f.write(json.dumps({
                    "id": "run2",
                    "iteration": 1,
                    "timestamp": 200,
                    "parameters": {"helix_path_radius_mm": 12.0},
                    "metrics": {"separation_efficiency": 95.0}
                }) + "\n")

            res = mcp_server.generate_training_dataset_tool(
                config_file="configs/corkscrew_config.yaml",
                log_file=log_path,
                output_file=out_path,
                format_type="openai"
            )

            self.assertEqual(res["status"], "success")
            self.assertEqual(res["exported_examples"], 1)
            self.assertTrue(os.path.exists(out_path))

    def test_get_schema_state(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            res = mcp_server.get_schema_state(workspace_dir=temp_dir)
            self.assertEqual(res["status"], "success")
            self.assertIn("state", res)
            self.assertIn("timeline_events_count", res)
            self.assertIn("notes", res)

    @patch("optimizer.harness.engine.SchemaEngine.run_one_iteration")
    @patch("optimizer.mcp_server.run_simulation")
    def test_run_schema_step(self, mock_run_sim, mock_engine_run):
        from optimizer.harness.state import State

        mock_run_sim.return_value = (
            {"separation_efficiency": 99.0, "pressure_drop": 0.2},
            [],
            "", "", ""
        )
        dummy_state = State()
        mock_engine_run.return_value = (dummy_state, {"action": "mutate"}, dummy_state, 1.2)

        with tempfile.TemporaryDirectory() as temp_dir:
            res = mcp_server.run_schema_step(
                config_file="configs/corkscrew_config.yaml",
                workspace_dir=temp_dir,
                dry_run=True
            )

            self.assertEqual(res["status"], "success")
            self.assertEqual(res["discrepancy"], 1.2)
            self.assertIn("updated_state", res)


if __name__ == "__main__":
    unittest.main()
