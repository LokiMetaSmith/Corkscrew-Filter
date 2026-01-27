include <modules/barbs.scad>
include <modules/primitives.scad>
// We need primitives for O-ring cutters if we want to reproduce the cartridge logic exactly.

// =============================================================================
// --- Custom Coupling Generator ---
// =============================================================================
// This module generates the specific coupling geometries defined in the legacy files.
// It relies on variables being set (likely from a config file).

module CustomCoupling() {

    // --- Main Body Construction ---
    difference(){
        union(){
            // Inset Cylinder
            translate([0,0,(coupling_inset_height+coupling_lip_height)/2])
                cylinder(h=coupling_inset_height, d=coupling_inset_width, center=true, $fn=$fn);

            // Lip Cylinder
            cylinder(h=coupling_lip_height, d=coupling_lip_width, center=true, $fn=$fn);

            // Outer Coupling Cylinder
            translate([0,0,-(coupling_outer_coupling_height+coupling_lip_height)/2])
                cylinder(h=coupling_outer_coupling_height, d=coupling_outer_coupling_od, center=true, $fn=$fn);
        }

        union(){
            // Inner Bore (Complex Taper)
            translate([0,0,(coupling_inset_height+coupling_lip_height)/2])
                cylinder(h=coupling_inset_height+0.1, d2=coupling_inner_inlet, d1=coupling_inner_outlet, center=true, $fn=$fn);

            cylinder(h=coupling_lip_height+0.1, d=coupling_inner_outlet, center=true, $fn=$fn);

            translate([0,0,-(coupling_outer_coupling_height+coupling_lip_height)/2])
                cylinder(h=coupling_outer_coupling_height+0.1, d1=barb_input_diameter, d2=coupling_inner_outlet, center=true, $fn=$fn);

            // --- Cartridge Specific: O-Ring Grooves ---
            if (custom_coupling_type == "cartridge") {
                translate([0,0,(coupling_inset_height+coupling_lip_height)*4/5])
                    OringGroove_OD_Cutter(coupling_inset_width, 2.2);
                translate([0,0,(coupling_inset_height+coupling_lip_height)/2])
                    OringGroove_OD_Cutter(coupling_inset_width, 2.2);
                translate([0,0,(coupling_inset_height+coupling_lip_height)/4])
                    OringGroove_OD_Cutter(coupling_inset_width, 2.2);
            }
        }
    }

    // --- Barb Attachment ---
    translate([0,0,-(coupling_outer_coupling_height+coupling_lip_height/2)])
        translate([0,0,0.09])
            rotate([180, 0, 0])
            Barb(
                hose_id = barb_input_diameter,
                hose_od = barb_output_diameter,
                barb_count = barb_count,
                barb_length = barb_length,
                swell = barb_swell,
                wall_thickness = barb_wall_thickness,
                bore = true,
                shell = true
            );
}
