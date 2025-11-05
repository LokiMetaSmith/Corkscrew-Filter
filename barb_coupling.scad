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
inset_height = 18.9; //18.53
inset_width = 12.55; //12.37
inner_inlet = 9.5; //9.1
inner_height = 2.37;
inner_outlet = 5.2;

//offset (0.042 + 0.014 + 0.019 + 0.014)/4 = 0.02225 or scale increase 2.225%

// Super-Duper Parametric Hose Barb
$fn = 90;
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

difference(){
    union(){
        translate([0,0,(inset_height+lip_height)/2])
        cylinder(h=inset_height,d = inset_width,center=true,$fn=30);
        cylinder(h=lip_height,d = lip_width,center=true,$fn=30);
        translate([0,0,-(outer_coupling_height+lip_height)/2])
        cylinder(h=outer_coupling_height,d = outer_coupling,center=true,$fn=30);
    }
    union(){
        translate([0,0,(inset_height+lip_height)/2])
        cylinder(h=inset_height+0.1,d2=inner_inlet,     d1=inner_outlet,center=true,$fn=30);
        cylinder(h=lip_height+0.1,d=inner_outlet,center=true,$fn=30);
        translate([0,0,-(outer_coupling_height+lip_height)/2])
        cylinder(h=outer_coupling_height+0.1,d1=barb_input_diameter,     d2=inner_outlet,center=true,$fn=30);
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