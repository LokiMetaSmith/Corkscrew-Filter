Wait, my local copy has `\n`. But the user's copy might have `\r\n`!
Because they are on `MINGW64 ~/Documents/projects/ThirstyCorkscrew` (Git Bash on Windows).
So `replace("divSchemes\n{")` is brittle and fails. I should use `re.sub` instead!
```python
        elif turbulence == "RNGkEpsilon":
            content = re.sub(r"div\(phi,omega\).*?;", "", content)
            content = re.sub(r"div\(phi,R\).*?;", "", content)

            # Robustly inject if missing due to prior corrupted files
            if "div(phi,k)" not in content and "divSchemes" in content:
                content = re.sub(r"(divSchemes\s*\{)", r"\1\n    div(phi,k)      bounded Gauss upwind;", content, count=1)
            if "div(phi,epsilon)" not in content and "divSchemes" in content:
                content = re.sub(r"(divSchemes\s*\{)", r"\1\n    div(phi,epsilon) bounded Gauss upwind;", content, count=1)
```
This is MUCH better.

What about `_execute` in `run_solver`?
If `_execute()` fails at time `1` because of `epsilonWallFunction` divergence, OpenFOAM might have already written the `1` directory.
When we call `_execute()` again:
```python
            print("Solver failed on standard mesh. Attempting to recover by applying fallback wall functions...")
            self._apply_fallback_wall_functions()
            success = _execute()
```
If `1` exists, `simpleFoam` (which has `startFrom latestTime;` in `controlDict`) will start from `1` instead of `0`.
If it starts from `1`, the fields in `1` might be broken (e.g. `epsilon` might contain `NaN`s from the previous FPE crash).
So `simpleFoam` will immediately crash AGAIN!
Wait, but if it crashed before finishing Time 1, it might not have written `1/`.
Wait, look at Iteration 1 log:
```
[2026-03-08 01:37:05] Time = 1
...
[2026-03-08 01:37:21] time step continuity errors : sum local = 0.00166026, global = -0.000581683, cumulative = -0.000581683
[2026-03-08 01:37:22] --> FOAM FATAL IO ERROR: (openfoam-2512)
[2026-03-08 01:37:22] Entry 'div(phi,epsilon)' not found in dictionary "system/fvSchemes/divSchemes"
```
It crashed at Time 1 BEFORE it finished. OpenFOAM writes the output at `writeInterval` (e.g., 50 or 100), not at Time 1, UNLESS it's configured to write every step.
But wait! Does it write `1` if it crashes?
Usually, no. BUT if there is a `processor*` directory and it crashed, wait, maybe `simpleFoam` continues from `0`.

Wait, in Iteration 2 of the prompt:
```
Finished Meshing in 1486.37s
Starting Solver...
Error executing simpleFoam: ... returned non-zero exit status 136.
...
[2026-03-08 03:02:53] #1  Foam::sigFpe::sigHandler(int) in ...
--------------------------------------------------
Solver failed on standard mesh. Attempting to recover by applying fallback wall functions...
Applied fallback wall function nutkWallFunction to nut due to mesh scaling.
Applied fallback wall function zeroGradient to epsilon due to mesh scaling.
Applied fallback wall function zeroGradient to k due to mesh scaling.
```
And then what happened? The log ends!
Why does the log end? Because the user truncated it?
Or because `_execute()` in the retry failed the SAME WAY?
If it failed the same way (with `sigFpe` in `epsilonWallFunctionFvPatchScalarField::calculate`), then the fallback wall functions WERE NOT APPLIED correctly or `simpleFoam` loaded the old broken fields from `1/`!
But wait, `_apply_fallback_wall_functions` applies the replacements to ALL `0` directories:
```python
        # Find all 0 directories (base + processor)
        zero_dirs = [os.path.join(self.case_dir, "0")]
        zero_dirs.extend(glob.glob(os.path.join(self.case_dir, "processor*", "0")))
```
If `simpleFoam` starts from `0`, it WILL use the updated `zeroGradient`.
BUT if there are `processor*/0` directories, are there also `processor*/1` directories?
No, it crashed before writing `1`.
Wait! If it applied `zeroGradient` to `epsilon`, why would it crash in `epsilonWallFunction` again?
Because maybe `_apply_fallback_wall_functions` FAILED to replace `epsilonWallFunction`!
Let's check `_apply_fallback_wall_functions`.
```python
                if old_wall_func:
                    content = content.replace(f"type            {old_wall_func};", f"type            {new_wall_func};")
```
What is `old_wall_func`?
```python
                initial_fields = cfd_settings.get('initial_fields', {})
                old_wall_func = None
                if field_name in initial_fields:
                    old_wall_func = initial_fields[field_name].get('wallFunction')
```
For `epsilon`, `old_wall_func` is `epsilonWallFunction`.
So it replaces `type            epsilonWallFunction;` with `type            zeroGradient;`.
Let's check `corkscrewFilter/0.orig/epsilon`:
```
    walls
    {
        type            epsilonWallFunction;
        value           uniform 14.8;
    }
```
If it replaces `type            epsilonWallFunction;` with `type            zeroGradient;`, it works.
But wait! What about the `value uniform 14.8;` line?
Does `zeroGradient` allow a `value` field?
Yes, OpenFOAM ignores the `value` field for `zeroGradient`, but sometimes prints a warning. It does not crash.
So it SHOULD have applied `zeroGradient`.
Why did it crash? Wait, the log doesn't show the retry crashing! The user just said "is this the right approach? discuss". The user just gave me the log up to that point.
Wait! In the first log snippet, Iteration 1:
```
[2026-03-08 01:37:22] --> FOAM FATAL IO ERROR: (openfoam-2512)
[2026-03-08 01:37:22] Entry 'div(phi,epsilon)' not found in dictionary "system/fvSchemes/divSchemes"
--------------------------------------------------
Finished Solver in 41.94s
```
This was Iteration 1 of the NEW run. Iteration 1 did NOT print "Solver failed on standard mesh. Attempting to recover...".
Why? Because `mesh_scaled_for_memory` was TRUE!
"Warning: Estimated cell count 1976000 exceeds 1560501 limit (RAM: 15.6GB)."
Ah!!!
In Iteration 1, the mesh WAS scaled!
Because it was scaled, `run_solver` was called with `mesh_scaled_for_memory=True`.
```python
        if not success and not mesh_scaled_for_memory:
            print("Solver failed on standard mesh. Attempting to recover by applying fallback wall functions...")
```
So it did NOT retry!
And because it didn't retry, it just failed!
Why did it fail?
Because `Entry 'div(phi,epsilon)' not found in dictionary "system/fvSchemes/divSchemes"`!
And why was it missing? Because `_update_fvSchemes` failed to inject it because of `\r\n` line endings in the user's template file from their previous run!

And in Iteration 2:
Mesh was NOT scaled!
`Calculated blockMesh resolution: (57 85 194)` -> `939930` cells. Less than `1560501` limit!
So it did NOT scale the mesh!
Then `simpleFoam` ran, and crashed with FPE (`#1  Foam::sigFpe::sigHandler`).
Then it PRINTED:
```
Solver failed on standard mesh. Attempting to recover by applying fallback wall functions...
Applied fallback wall function nutkWallFunction to nut due to mesh scaling.
...
```
And then the user probably stopped the script, or it crashed again because `div(phi,epsilon)` was missing in the retry!

So the ROOT CAUSE of the ongoing crashes is INDEED the brittle `content.replace("divSchemes\n{", ...)` not working on Windows line endings (`\r\n`), so `div(phi,epsilon)` stays missing!
