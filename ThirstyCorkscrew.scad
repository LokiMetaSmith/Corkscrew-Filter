// This file is Copyright Robert L. Read 2025.
// Although Public Invention does everything open source, this file is an 
// exception.

// This is a work in progress. There are a number of tasks:
// *) Create any empty chamber (for collecting particulates)
// *) Create the Corkscrew voids
// *) Add ejectiong slits to the Coorkscrews
// *) desideratum: make the internal shape circular from the POV of the tunnel.
// *) desideratom: design an "ice cream cone shape" with the point pointing out.
//    we desire to do A-B testing on this.
// *) Have 10 cells, each of which has a gravity feed into a particulate bin.
// *) The number of particulate bins should be 1 or up to 3.
// *) 6 turns is desired.

// Note: The shape may be as simple as the shadow of a rotated circle,
// which seems likely to be no more complicated than scaling a circle by
// cos(pitch angle)

// Params (mm), degrees 
filter_height_mm = 30;
// filter_twist_degrees = 360*6;
filter_twist_degrees = 360*4;
screw_OD_mm = 2;
screw_ID_mm = 1;
slit_start_mm = 0;
slit_finish_mm = 10;
cell_wall_mm = 1;
hex_cell_diam_mm = 10;
FN_RES = 40;
bin_height_z_mm = 30;
num_screws = 4;
screw_center_separation_mm = 10;
bin_breadth_x_mm = (num_screws -1) * screw_center_separation_mm + screw_center_separation_mm*2;

bin_wall_thickness_mm = 1;

// coordinate system: Gravity points in the -Z direction. +Z is up.abs
// The left-right dimentions is considered X. Air flow is in the positive Y
// direction. The is a right-handed coordinate system.

module Corkscrew(h,twist) {
    rotate([90,0,0])
    linear_extrude(height = h, center = true, convexity = 10, twist = twist, $fn = FN_RES)
    translate([screw_OD_mm, 0, 0])
    circle(r = screw_OD_mm);
}

module CorkscrewSlitKnife(h,twist,start,finish) {
    d = finish - start;
    rotate([90,0,0])
    difference() {
        linear_extrude(height = h, center = true, convexity = 10, twist = twist, $fn = FN_RES)
        translate([screw_OD_mm,0,0])
        rotate([0,0,0])
        polygon(points = [[0,0],[5,-2],[5,2]]);
        echo("ddddd");
        echo(d);
        // WARNING!! THis is not correct!
        translate([0,0,-d]) // This puts it at the bottom level
       cube([10,10,h],center=true);
    }
}


module CorkscrewWithVoid(h,twist) {
    rotate([90,0,0])
    linear_extrude(height = h, center = true, convexity = 10, twist = twist, $fn = FN_RES)
    translate([screw_OD_mm, 0, 0])
    difference() {
        circle(r = screw_OD_mm);
        circle(r = screw_ID_mm);
    }
}


module CorkscrewWithSlit() {
      difference() {
        CorkscrewWithVoid(filter_height_mm,filter_twist_degrees);
        CorkscrewSlitKnife(filter_height_mm,filter_twist_degrees,slit_start_mm,slit_finish_mm);
    }
}
module regular_polygon(order = 4, r=1){
     angles=[ for (i = [0:order-1]) i*(360/order) ];
     coords=[ for (th=angles) [r*cos(th), r*sin(th)] ];
     polygon(coords);
 }

// Rather complicated here is how to cut the ports... 
module HexCell() {
    color("pink",alpha=0.8)
    difference() {
        scale([hex_cell_diam_mm, hex_cell_diam_mm ,filter_height_mm])
        regular_polygon(6);
        
        inner = hex_cell_diam_mm - cell_wall_mm*2;
        scale([inner,inner,filter_height_mm - cell_wall_mm*2])
        regular_polygon(6);
        
 // now cut out the port. It would be nice if this was a little tighter
       Corkscrew(filter_height_mm*3,filter_twist_degrees*3);
    }
}

module HexCellWithCorkScrew() {
//    HexCell();
    CorkscrewWithSlit();
}

module Bins(depth,numbins,height,width,height_above_port_line) {
    // first create outer bin
    d = bin_wall_thickness_mm*2;
    translate([0,0,height_above_port_line - height/2])
    difference() {
        cube([width,depth,height],center = true);
        cube([width-d,depth-d,height-d],center=true);
    } 
}

module BinsWithScrew(nums_screws) {
    d = (num_screws-1)*screw_center_separation_mm;
    difference() {
        union() {
            Bins(filter_height_mm,1,bin_height_z_mm,bin_breadth_x_mm, screw_center_separation_mm);
        }
   
        union() {
            // now we must cut the ports
            for (i = [0:num_screws-1]) {
                x =  -d/2+ i * screw_center_separation_mm;
                translate([x,0,0])
               Corkscrew(filter_height_mm,filter_twist_degrees);
            } 
        }      
    } 
    for (i = [0:num_screws-1]) {
        x =  -d/2 + i * screw_center_separation_mm;
        translate([x,0,0])
        CorkscrewWithSlit();
    }  
}

difference() {
    BinsWithScrew(num_screws);
    // viewing knife
   translate([0,0,-50])
    cube([100,100,100],center = true);
}

// HexCellWithCorkScrew();

