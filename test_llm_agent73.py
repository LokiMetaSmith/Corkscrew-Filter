import json

# IF IT IS MATHEMATICALLY IMPOSSIBLE, then the ONLY conclusion is:
# `new_params["helix_path_radius_mm"]` was NOT 3.93 when `helix_profile_radius_mm` was generated!
# BUT the user log says `Testing parameters: {'helix_path_radius_mm': 3.93, 'helix_profile_radius_mm': 4.85...}`!
# How could `helix_path_radius_mm` be something else during generation, but become 3.93 afterwards?!
# Is there ANOTHER line that sets `helix_path_radius_mm`?!
