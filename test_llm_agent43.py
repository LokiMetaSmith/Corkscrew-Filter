# NO! It is NOT marked as constant.

# SO, WHAT IF `random.uniform(1.5, 3.92)` DID NOT GENERATE 4.85, BUT `validate_parameters` DID NOT RETURN TRUE, AND SO `new_params` WAS NOT RETURNED.
# And it looped 100 times.
# AND NO ATTEMPT RETURNED `is_valid == True`.
# So it reached the end of the loop!
# And it printed `print("Warning: Could not generate valid random parameters after 100 attempts.")`
# And returned the LAST `new_params`!
# The last `new_params` WOULD HAVE HAD `helix_profile_radius_mm` < `helix_path_radius_mm`!
# WHY would the last `new_params` have 4.85 and 3.93?!

# IF AND ONLY IF `ordered_params` DID NOT OVERWRITE `helix_profile_radius_mm` IN THE LAST ATTEMPT!
# BUT the loop over `ordered_params` ALWAYS runs for EVERY parameter.
# So `helix_profile_radius_mm` IS OVERWRITTEN in EVERY ATTEMPT!

# IS THERE ANY OTHER WAY?
