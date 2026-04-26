# Ah! If `base_params` is `full_history[-1]["parameters"]` and it misses `tube_od_mm` (because the previous run didn't save it for some reason), then `tube_od_mm` is missing from `base_params`.
# Then `_generate_random_parameters(base_params, parameters_def)`:
# `new_params = current_params.copy()`
# Since `tube_od_mm` is MISSING in `base_params`, `tube_od_mm` is MISSING in `new_params`.
# Then `ordered_params` loop:
# `tube_od_mm` has `constant: True`.
# So it `continue`s!
# So `tube_od_mm` is STILL MISSING in `new_params`!
# Then `validate_parameters(new_params)`:
# if "tube_od_mm" in params or "tube_wall_mm" in params:
# Since NEITHER are in `params`, it skips tube validation!
# AND IT RETURNS TRUE!
# So `_generate_random_parameters` DOES NOT FAIL!

# If it does not fail, what happens?
# It generates a VALID parameter set, but WITHOUT `tube_od_mm`!
# And it returns it!

# SO WHY DID IT FAIL FOR THE USER AND RETURN THE LAST INVALID PARAMETERS?!
