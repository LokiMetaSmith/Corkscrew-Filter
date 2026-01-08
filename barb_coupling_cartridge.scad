//auth. L.Kincheloe


barb_input_diameter = 5; //2.14
barb_output_diameter = 6.5;
barb_wall_thickness = 1;
barb_length=2;
barbs = 4;
// Wall thickness of the barb.
wall_thickness = 1.31;
lip_height = 2.4;
lip_width = 16.9; //16.66
outer_coupling = 14.91; //measured 14.6
outer_coupling_height = 10;
inset_height = 23.5; //18.53
inset_width = 30.312598673823808020208399115883; //12.37
inner_inlet = 29; //9.1
inner_height = 2.37;
inner_outlet = 5.2;

//offset (0.042 + 0.014 + 0.019 + 0.014)/4 = 0.02225 or scale increase 2.225%

// Super-Duper Parametric Hose Barb
$fn = 200;
//include <BarbGenerator-v3.scad>;
module barb(hose_od = barb_output_diameter, hose_id = barb_input_diameter, swell = 1, wall_thickness = 1.31, barbs = 4, barb_length = 3, shell = true, bore = true, ezprint = false) {
    echo("hose_id", hose_id);
    id = hose_id - (2 * wall_thickness);
    translate([0, 0, -((barb_length * (barbs + 1)) )])
    difference() {
        union() {
            if (shell == true) {

                for (z = [1 : 1 : barbs]) {
                    translate([0, 0, z * barb_length]) cylinder(d1 = hose_od, d2 = hose_od + swell, h = barb_length);
                }
                //translate([0, 0, barb_length * (barbs + 1)]) cylinder(d = hose_od, h = 4.5 + (hose_od - hose_id));
            }
        
            if (bore == true) {
                echo("hose wall thickness", hose_id-id)
                translate([0, 0, -1]) cylinder(d = id, h = 1+ (barb_length * (barbs + 1)) + 4.5 + (hose_od - hose_id) );
            }
            else if (ezprint == true) {
                difference() {
                    cylinder(d = hose_id + (swell * 3), h = (barb_length * (barbs + 1)));
                    translate([swell, 0, 0]) cylinder(d = hose_id + (swell ), h = (barb_length * (barbs + 1)));
                }
            }
        }
        #translate([0,0,-2])cylinder(d = hose_id, h = (barb_length * (barbs + 1)) + 6.5 + (hose_od - hose_id) + 1);
    }
}

module OringGroove_OD_Cutter(object_dia, oring_cs) {
    groove_depth = oring_cs * 0.8;
    groove_width = oring_cs * 1.1;
    difference() {
        cylinder(d = object_dia + 0.2, h = groove_width, center = true);
        cylinder(d = object_dia - 2 * groove_depth, h = groove_width + 0.2, center = true);
    }
}

module OringVisualizer(object_dia, oring_cs) {
    groove_depth = oring_cs * 0.8;
    torus_radius = object_dia/2 - groove_depth/2;
    color("IndianRed")
    rotate_extrude(convexity=10)
        translate([torus_radius, 0, 0])
        circle(r = oring_cs / 2);
}

// Creates the cutting tool for an internal O-ring groove.
module OringGroove_ID_Cutter(object_id, oring_cs) {
    groove_depth = oring_cs * 0.8;
    groove_width = oring_cs * 1.1;
    rotate_extrude(convexity=10) {
        translate([object_id/2 + groove_depth, 0, 0])
            square([groove_depth, groove_width], center=true);
    }
}
difference(){
    union(){
        translate([0,0,(inset_height+lip_height)/2])
        cylinder(h=inset_height,d = inset_width,center=true,$fn=200);
        cylinder(h=lip_height,d = lip_width,center=true,$fn=200);
        translate([0,0,-(outer_coupling_height+lip_height)/2])
        cylinder(h=outer_coupling_height,d = outer_coupling,center=true,$fn=200);
    }
    union(){
        translate([0,0,(inset_height+lip_height)*4/5])
        OringGroove_OD_Cutter(inset_width,2.2);
        translate([0,0,(inset_height+lip_height)/2])
        OringGroove_OD_Cutter(inset_width,2.2);
        translate([0,0,(inset_height+lip_height)/4])
        OringGroove_OD_Cutter(inset_width,2.2);
        translate([0,0,(inset_height+lip_height)/2])
        cylinder(h=inset_height+0.1,d2=inner_inlet,     d1=inner_outlet,center=true,$fn=200);
        cylinder(h=lip_height+0.1,d=inner_outlet,center=true,$fn=200);
        translate([0,0,-(outer_coupling_height+lip_height)/2])
        cylinder(h=outer_coupling_height+0.1,d1=barb_input_diameter,     d2=inner_outlet,center=true,$fn=200);
    }
}

translate([0,0,-(outer_coupling_height+lip_height/2)])
//od = 5;
//id = 3;
//x = id + 3 * 0.9;
translate([0,0,0.09])
//rotate([180,0,0])
barb();
//output_barb(output_diameter = barb_output_diameter/2, input_diameter=barb_input_diameter/2,jheight=0);