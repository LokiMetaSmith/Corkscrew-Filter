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

// Questions for John:
// Should the ports have barbs?
// Should the ouutput ports have barb?


// Params (mm), degrees 
filter_height_mm = 30;
// filter_twist_degrees = 360*6;
number_of_complete_revolutions = 4;
filter_twist_degrees = 360*number_of_complete_revolutions;
screw_OD_mm = 2;
screw_ID_mm = 1;
slit_axial_length_mm = 2;
cell_wall_mm = 1;
hex_cell_diam_mm = 10;
FN_RES = 40;
bin_height_z_mm = 30;
num_screws = 1;
num_bins = 3;
screw_center_separation_mm = 10;
bin_breadth_x_mm = (num_screws -1) * screw_center_separation_mm + screw_center_separation_mm*2;

pitch_mm = filter_height_mm / number_of_complete_revolutions; // Is the the axial distance in mm per degree


bin_wall_thickness_mm = 1;

// CONTROL_VARIABLES
USE_SCREW_ONLY          = 0;
USE_FULL_BINS           = 1;
USE_KNIFE_THRU_SCREWS   = 1;
USE_KNIFE_LOW           = 0;
USE_SCREW_KNIFE         = 0;

// coordinate system: Gravity points in the -Z direction. +Z is up.abs
// The left-right dimentions is considered X. Air flow is in the positive Y
// direction. The is a right-handed coordinate system.

module Corkscrew(h,twist) {
    rotate([90,0,0])
    linear_extrude(height = h, center = true, convexity = 10, twist = twist, $fn = FN_RES)
    translate([screw_OD_mm, 0, 0])
    circle(r = screw_OD_mm);
}

// This is a little complicated. The slit position
// depends on the number of bins, we want one slit in each 
// screw in each bin, near the end of the bin. The slit should
// "open", so that if a particle can enter it, it can't get "wedged".
// Ideally we would also make the slit point "down" for testing in 
// a gravity environment, althought in zero-g there is no "down".
// Down is -z in this geometry, however.
module CorkscrewSlitKnife(twist,depth,num_bins) {
    de = depth/num_bins;
    // this rotates each individual knife into position  
    yrot = 360*(1 / pitch_mm)*de;
    // this puts us on the x axis
    rotate([90,0,0])
    for(i = [0:num_bins -1]) {
        j = -(num_bins-1)/2 + i;
        // Now the only way to make this math work out is to know the 
        // "pitch" of the helix, which is the axial length of one 
        // revolution, and use it to compute how to rotate the knife,
        // by computing rotation per mm...
        rotate([0,0,-yrot*(j+1)])
        translate([0,0,(j+1)*de])
        difference() {
            linear_extrude(height = depth, center = true, convexity = 10, twist = twist, $fn = FN_RES)
            translate([screw_OD_mm,0,0])
            rotate([0,0,0])
            polygon(points = [[0,0],[4,-2],[4,2]]);
        // now we cut this corkscrew slit down to size...
            translate([0,0,slit_axial_length_mm])
            cube([15,15,depth],center=true);
        }
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

module CorkscrewWithoutVoid(h,twist) {
    rotate([90,0,0])
    linear_extrude(height = h, center = true, convexity = 10, twist = twist, $fn = FN_RES)
    translate([screw_OD_mm, 0, 0])
    difference() {
        circle(r = screw_OD_mm);
    }
}



module CorkscrewWithSlit(depth,numbins) {
      difference() {
        CorkscrewWithVoid(depth,filter_twist_degrees);
        CorkscrewSlitKnife(filter_twist_degrees,depth,numbins);
    }
}
module regular_polygon(order = 4, r=1){
     angles=[ for (i = [0:order-1]) i*(360/order) ];
     coords=[ for (th=angles) [r*cos(th), r*sin(th)] ];
     polygon(coords);
 }

//// Rather complicated here is how to cut the ports... 
//module HexCell() {
//    color("pink",alpha=0.8)
//    difference() {
//        scale([hex_cell_diam_mm, hex_cell_diam_mm ,filter_height_mm])
//        regular_polygon(6);
//        
//        inner = hex_cell_diam_mm - cell_wall_mm*2;
//        scale([inner,inner,filter_height_mm - cell_wall_mm*2])
//        regular_polygon(6);
//        
// // now cut out the port. It would be nice if this was a little tighter
//       Corkscrew(filter_height_mm*3,filter_twist_degrees*3);
//    }
//}
//
//module HexCellWithCorkScrew() {
////    HexCell();
//    CorkscrewWithSlit(depth,num_bins);
//}

module Bins(depth,numbins,height,width,height_above_port_line) {
    // first create outer bin
    b = bin_wall_thickness_mm*2;
    // Now I try to do this math to create multiple bins
    // These will be cubes; orifices will have to be cut
    // in them later.
    de = depth/numbins; // w = width of one bin

    for(i = [0:numbins -1]) {
        j = -(numbins-1)/2 + i;
        translate([0,j*de,0])
        translate([0,0,height_above_port_line - height/2])
        difference() {
            cube([width,de,height],center = true);
            cube([width-b,de-b,height-b],center=true);
        } 
    }
}

module Screws(num_screws,num_bins,depth) {
    echo("Screws Called");
    d = (num_screws-1)*screw_center_separation_mm;
    union() {
            // now we must cut the ports
            for (i = [0:num_screws-1]) {
                x =  -d/2+ i * screw_center_separation_mm;
                translate([x,0,0])
               CorkscrewWithSlit(depth,num_bins);
            } 
        }      
}
module ScrewsKnife(num_screws,num_bins,depth) {
    echo("ScrewsKnife Called");
    d = (num_screws-1)*screw_center_separation_mm;
    union() {
            // now we must cut the ports
            for (i = [0:num_screws-1]) {
                x =  -d/2+ i * screw_center_separation_mm;
                translate([x,0,0])
               CorkscrewWithoutVoid(depth,filter_twist_degrees);
            } 
        }      
}
module BinsWithScrew(nums_screws,num_bins) {
    d = (num_screws-1)*screw_center_separation_mm;
    difference() {
        Bins(filter_height_mm,num_bins,bin_height_z_mm,bin_breadth_x_mm, screw_center_separation_mm);
        ScrewsKnife(num_screws,num_bins,filter_height_mm);    
    } 

    // For cutting holes in outer bin walls.
    for (i = [0:num_screws-1]) {
        x =  -d/2 + i * screw_center_separation_mm;
        echo(filter_height_mm);
        translate([x,0,0])
        CorkscrewWithSlit(filter_height_mm,num_bins);
    }  
}

if (USE_FULL_BINS) {
    difference() {
        BinsWithScrew(num_screws,num_bins);
        // viewing knife
        if (USE_KNIFE_THRU_SCREWS) {
            translate([0,0,-50])
            cube([100,100,100],center = true);
        }
        if (USE_KNIFE_LOW) {
            translate([0,0,-50+-10])
            cube([100,100,100],center = true);
        }
    }
}

if (USE_SCREW_ONLY) {
    Screws(num_screws,num_bins,filter_height_mm);
}
if (USE_SCREW_KNIFE) {
    ScrewsKnife(num_screws,num_bins,filter_height_mm);
}
