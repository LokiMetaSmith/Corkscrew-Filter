import os
import unittest
import tempfile
import json
import shutil
from typing import Dict, Any

from optimizer.harness.state import State, Action, compute_state_distance, parse_solver_outputs_to_state
from optimizer.harness.timeline import Timeline
from optimizer.harness.notes import NotesManager
from optimizer.harness.surrogate import SurrogateManager, DEFAULT_WORLD_MODEL_TEMPLATE
from optimizer.harness.planner import BFSPlanner
from optimizer.harness.engine import SchemaEngine


class MockLLMAgent:
    def __init__(self):
        self.providers = [True]

    def _generate(self, prompt: str) -> str:
        # Mock responsive code rewrite behavior
        new_code = """
def step(state_dict, action_dict):
    import copy
    next_state = copy.deepcopy(state_dict)
    geom = next_state.setdefault('geometry', {})
    for param, val in action_dict.items():
        geom[param] = float(geom.get(param, 0.0)) + float(val)
    fluid = next_state.setdefault('fluid', {})
    fluid['separation_efficiency'] = 99.9  # Mock perfect adaptation
    fluid['pressure_drop'] = 12.0
    return next_state
"""
        return "Discovered updated physical rule for high-efficiency inertial separation.\n=== CODE ===\n" + new_code


class TestSchemaHarness(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.parameter_defs = {
            "helix_path_radius_mm": {"type": "float", "default": 2.0},
            "helix_profile_radius_mm": {"type": "float", "default": 1.5},
            "tube_wall_mm": {"type": "float", "default": 1.0}
        }

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_state_actions_and_distance(self):
        s1 = State(geometry={"tube_od_mm": 32.0}, fluid={"pressure_drop": 150.0})
        s2 = State(geometry={"tube_od_mm": 32.0}, fluid={"pressure_drop": 120.0})

        keys_schema = {
            "geometry": ["tube_od_mm"],
            "fluid": ["pressure_drop"],
            "structural": [],
            "electromagnetic": []
        }

        dist = compute_state_distance(s1, s2, keys_schema)
        # s1: [32, 150]
        # s2: [32, 120]
        # Diff vector: [0, 30] -> L2 Norm is 30.0
        self.assertEqual(dist, 30.0)

    def test_parse_solver_outputs(self):
        params = {"helix_path_radius_mm": 2.5}
        metrics = {"delta_p": 12.5, "max_von_mises_stress_MPa": 15.0, "S11": -14.2}
        state = parse_solver_outputs_to_state(params, metrics)

        self.assertEqual(state.geometry["helix_path_radius_mm"], 2.5)
        self.assertEqual(state.fluid["pressure_drop"], 12.5)
        self.assertEqual(state.structural["max_von_mises_stress_MPa"], 15.0)
        self.assertEqual(state.electromagnetic["S11"], -14.2)

    def test_timeline_serialization(self):
        timeline_path = os.path.join(self.temp_dir, "timeline.jsonl")
        timeline = Timeline(timeline_path)

        s_start = State(geometry={"tube_od_mm": 30.0})
        action = Action(mutations={"tube_od_mm": 2.0})
        s_pred = State(geometry={"tube_od_mm": 32.0})
        s_act = State(geometry={"tube_od_mm": 31.9})

        timeline.append_transition(s_start, action, s_pred, s_act)

        transitions = timeline.load_transitions()
        self.assertEqual(len(transitions), 1)
        self.assertEqual(transitions[0]["action"]["tube_od_mm"], 2.0)
        self.assertEqual(transitions[0]["actual_state"]["geometry"]["tube_od_mm"], 31.9)

    def test_notes_appending(self):
        notes_path = os.path.join(self.temp_dir, "notes.md")
        notes = NotesManager(notes_path)

        notes.append_note("First Hypothesis", "Flow follows spiral curvature.")
        notes.append_note("Second Hypothesis", "Centrifugal force separates dust.")

        content = notes.read_notes()
        self.assertIn("## First Hypothesis", content)
        self.assertIn("## Second Hypothesis", content)
        self.assertIn("Centrifugal force separates dust.", content)

    def test_surrogate_execution(self):
        model_path = os.path.join(self.temp_dir, "world_model.py")
        surrogate = SurrogateManager(model_path)

        state = State(geometry={"helix_path_radius_mm": 2.0}, fluid={"pressure_drop": 100.0})
        action = Action(mutations={"helix_path_radius_mm": 1.0})

        next_state = surrogate.run_step(state, action)
        self.assertEqual(next_state.geometry["helix_path_radius_mm"], 3.0)

    def test_planner_bfs_search(self):
        model_path = os.path.join(self.temp_dir, "world_model.py")
        surrogate = SurrogateManager(model_path)
        planner = BFSPlanner(surrogate, self.parameter_defs)

        start_state = State(geometry={"helix_path_radius_mm": 2.0}, fluid={"separation_efficiency": 90.0})

        # Define score function to maximize separation efficiency
        def score_func(s: State) -> float:
            return s.fluid.get("separation_efficiency", 0.0)

        action, expected_next, expected_score = planner.search(start_state, score_func, max_depth=2)
        self.assertIsInstance(action, Action)
        self.assertIsInstance(expected_next, State)
        self.assertGreaterEqual(expected_score, 90.0)

    def test_engine_mechanism_discovery_and_loop(self):
        engine = SchemaEngine(
            workspace_dir=self.temp_dir,
            parameter_defs=self.parameter_defs,
            llm_agent=MockLLMAgent(),
            epsilon=1.0
        )

        s_start = State(geometry={"helix_path_radius_mm": 2.0}, fluid={"separation_efficiency": 90.0})

        def score_func(s: State) -> float:
            return s.fluid.get("separation_efficiency", 0.0)

        # Mock solver returns perfect metrics
        def real_solver(params: Dict[str, Any]) -> Dict[str, Any]:
            return {"separation_efficiency": 99.9, "pressure_drop": 12.0}

        # Run first iteration
        _, action, next_state, dist = engine.run_one_iteration(s_start, score_func, real_solver)
        self.assertEqual(next_state.fluid["separation_efficiency"], 99.9)

        # Append transitions to trigger a mock backtest mismatch
        # We manually record a bad prediction transition to force backtest MSE > epsilon^2
        engine.timeline.append_transition(
            start_state=s_start,
            action=action,
            predicted_state=State(fluid={"separation_efficiency": 0.0}), # Huge error prediction
            actual_state=next_state
        )

        # Next iteration should trigger mechanism discovery due to backtest error
        engine.run_one_iteration(next_state, score_func, real_solver)

        # Verify world_model was rewritten by the MockLLMAgent
        with open(engine.world_model_path, "r") as f:
            code = f.read()
        self.assertIn("separation_efficiency'] = 99.9", code)

        # Verify notes.md updated
        notes = engine.notes.read_notes()
        self.assertIn("Discovered Discrepancy & Representation Change", notes)


if __name__ == "__main__":
    unittest.main()
