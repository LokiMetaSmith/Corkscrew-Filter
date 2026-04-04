import re

with open('optimizer/foam_driver.py', 'r') as f:
    content = f.read()

# Replace the run_solver loop logic to use the new backup methods.
# Locate the loop and results append part.

# We need to find:
#         best = None
#         for strategy in STRATEGIES:
#            ...
#            results.append({
#                "strategy": strategy["name"],
#                "score": score,
#                ...
#            })
#
#            print(f"Strategy {strategy['name']} completed with score={score:.1f} (success={success})")
#            if success and score > 80:
#                safe_print("✅ High quality run found, exiting early.")
#                break

old_loop_logic = """        best = None
        for strategy in STRATEGIES:"""

new_loop_logic = """        best_score_so_far = -1
        best_strategy_name = None

        for strategy in STRATEGIES:"""

content = content.replace(old_loop_logic, new_loop_logic)


old_append_logic = """            results.append({
                "strategy": strategy["name"],
                "score": score,
                "metrics": metrics,
                "success": success
            })

            print(f"Strategy {strategy['name']} completed with score={score:.1f} (success={success})")

            if success and score > 80:
                safe_print("✅ High quality run found, exiting early.")
                break

        if results:
            best = max(results, key=lambda r: r["score"])
            safe_print(f"🏆 Best run: {best['strategy']} (score={best['score']:.1f})")

            import json
            with open(os.path.join(self.case_dir, "run_results.json"), "w") as f:
                json.dump(results, f, indent=2)

            return best["success"]"""


new_append_logic = """            results.append({
                "strategy": strategy["name"],
                "score": score,
                "metrics": metrics,
                "success": success
            })

            print(f"Strategy {strategy['name']} completed with score={score:.1f} (success={success})")

            if success and score > best_score_so_far:
                best_score_so_far = score
                best_strategy_name = strategy["name"]
                self._backup_best_run()

            if success and score > 80:
                safe_print("✅ High quality run found, exiting early.")
                break

        if results:
            best = max(results, key=lambda r: r["score"])

            # If the last strategy we ran wasn't the best, we must restore the best one
            if best_strategy_name and best_strategy_name != strategy["name"]:
                safe_print(f"🔄 Restoring best strategy files: {best_strategy_name}")
                self._restore_best_run()

            safe_print(f"🏆 Best run: {best['strategy']} (score={best['score']:.1f})")

            import json
            with open(os.path.join(self.case_dir, "run_results.json"), "w") as f:
                json.dump(results, f, indent=2)

            return best["success"]"""

content = content.replace(old_append_logic, new_append_logic)

with open('optimizer/foam_driver.py', 'w') as f:
    f.write(content)
