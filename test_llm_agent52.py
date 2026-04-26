import json

# OKAY, what if `visited_params` contains ONLY VALID PARAMS?
# If `_generate_random_parameters` generates a VALID param set, `get_params_hash(random_params)` could ALREADY be in `visited_params`!
# IF IT IS, it WON'T BE APPENDED!
# `if get_params_hash(random_params) not in visited_params:`
# If it is skipped, `parameter_queue` is EMPTY.
# THEN IT BREAKS!
# But the user log DID NOT BREAK!
# "Testing parameters: {'number_of_complete_revolutions': 3.06...}"

# THIS MEANS `parameter_queue` WAS NOT EMPTY!
# IF IT WAS NOT EMPTY, `random_params` WAS APPENDED!
# Which means `random_params` WAS THAT EXACT DICTIONARY!

# HOW ON EARTH CAN `_generate_random_parameters` RETURN THAT EXACT INVALID DICTIONARY?!
