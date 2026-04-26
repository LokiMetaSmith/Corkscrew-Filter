# What if the user log is ACTUALLY output from `_generate_random_parameters` where it FAILED 100 times and returned the LAST attempt?!
# AND the last attempt generated 3.93 for path, and 4.85 for profile?!
# BUT HOW COULD IT DO THAT if `current_p_max` is bounded?!

# Look at this line!
# if current_p_min > current_p_max:
#    current_p_max = current_p_min

# IF `current_p_min` IS 4.85?!
# Where does `current_p_min` come from?
# `current_p_min = float(p_min)`
# `p_min = param_info.get('min')`
# Is `param_info.get('min')` 4.85?!
# IN THE CONFIG `corkscrew_config.yaml`, `min` is 1.5.
# Could the config have changed?! No, we are using the same config file.

# IS IT POSSIBLE THAT `round(random.uniform(current_p_min, current_p_max), 2)` is what generates it?!
# YES.

# IS IT POSSIBLE THAT `ordered_params` DOES NOT CONTAIN `helix_profile_radius_mm` FOR SOME WEIRD REASON?!
# No.

# WHAT IF `base_params` WAS PASSED AS `current_params` AND `base_params` WAS `last_params` (1.06, 2.76, 2.70)?
# AND `_generate_random_parameters` GENERATED A BRAND NEW SET!
# But then, WHY didn't it print "Warning: Could not generate valid random parameters after 100 attempts."?!
# ONLY if `is_valid` was TRUE!
