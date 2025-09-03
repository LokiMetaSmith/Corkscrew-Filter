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

// NOTE: 1/8" NPT female threads have been added to the bins, replacing the
// original barbs.


// Questions for John:
// Should the ports have barbs?
// Should the ouutput ports have barb?
// What dimensions do we want?

// TODO: make barbs more flush
// TODO: 

TC_VERSION_NUM = 0.2;


use <BarbGenerator-v3.scad>;


// Params (mm), degrees 

filter_height_mm = 40;
number_of_complete_revolutions = 6;
filter_twist_degrees = 360*number_of_complete_revolutions;
screw_OD_mm = 2;
screw_ID_mm = 1;
cell_wall_mm = 1;
slit_axial_open_length_mm = 0.5;
slit_axial_length_mm = cell_wall_mm + slit_axial_open_length_mm;
hex_cell_diam_mm = 10;
FN_RES = 30;
bin_height_z_mm = 20;
num_screws = 1;
// WARNING! Trying to reduce this to one bin seemed to make the slit go away
num_bins = 3;
screw_center_separation_mm = 10;
bin_breadth_x_mm = (num_screws -1) * screw_center_separation_mm + screw_center_separation_mm*2;

pitch_mm = filter_height_mm / number_of_complete_revolutions;

scale_ratio = 1.4; // This is used to acheive a more circular air path

bin_wall_thickness_mm = 1;

// CONTROL_VARIABLES
USE_SCREW_ONLY          = 0;
USE_VOIDLESS_SCREW      = 0;
USE_FULL_BINS           = 1;
USE_KNIFE_THRU_SCREWS   = 0;
USE_KNIFE_LOW           = 0;
USE_KNIFE_SIDE          = 0;
USE_KNIFE_TOP_HALF      = 0;
USE_SCREW_KNIFE         = 0;

USE_BINCAP              = 0;

USE_BARB                = 0;
ROBS_ORIGINAL_BARBS = 1;


module Barb(input_diameter,output_diameter) {
   jheight = -6;
   output_barb( input_diameter, output_diameter, jheight );
}


if (USE_BARB) {
    input_diameter = 3;
    output_diameter = 5;
    jheight = 0;
 //   input_barb( input_diameter );
    
 //   output_barb( input_diameter, output_diameter, jheight );
    Barb(input_diameter,output_diameter);
}

// Standalone BinCap generation
if (USE_BINCAP) {
    translate([0,0,-bin_height_z_mm+8])
    BinCap(filter_height_mm,num_bins,bin_height_z_mm,bin_breadth_x_mm, screw_center_separation_mm);
}

// coordinate system: Gravity points in the -Z direction. +Z is up.abs
// The left-right dimentions is considered X. Air flow is in the positive Y
// direction. The is a right-handed coordinate system.

module Corkscrew(h,twist) {
    rotate([90,0,0])
    linear_extrude(height = h, center = true, convexity = 10, twist = twist, $fn = FN_RES)
    translate([screw_OD_mm, 0, 0])
    scale([1,scale_ratio])
    circle(r = screw_OD_mm);
}

module CorkscrewSlitKnife(twist,depth,num_bins) {
    de = depth/num_bins;
    yrot = 360*(1 / pitch_mm)*de;

    rotate([90,0,0])
    for(i = [0:num_bins -1]) {
        j = -(num_bins-1)/2 + i;
        rotate([0,0,-yrot*(j+1)])
        translate([0,0,(j+1)*de])
        difference() {
            linear_extrude(height = depth, center = true, convexity = 10, twist = twist, $fn = FN_RES)
            translate([screw_OD_mm,0,0])
            rotate([0,0,0])
            polygon(points = [[0,0],[4,-2],[4,2]]);
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
        scale([1,scale_ratio])
        circle(r = screw_OD_mm);
        scale([1,scale_ratio])
        circle(r = screw_ID_mm);
    }
}

module CorkscrewWithoutVoid(h,twist) {
    echo("CorkscrewWithoutTwist");
    echo(scale_ratio);
    rotate([90,0,0])
    linear_extrude(height = h, center = true, convexity = 10, twist = twist, $fn = FN_RES)
    translate([screw_OD_mm, 0, 0])
    scale([1,scale_ratio])
    circle(r = screw_OD_mm);
}


module CorkscrewWithoutVoidExcess(h,twist) {
    CorkscrewWithoutVoid(h*2,twist*2);
}


module CorkscrewWithSlit(depth,numbins) {
      difference() {
        CorkscrewWithVoid(depth,filter_twist_degrees);
        CorkscrewSlitKnife(filter_twist_degrees,depth,numbins);
    }
}

// Bins module now generates 1/8" NPT female threads instead of barbs.
module Bins(depth,numbins,height,width,height_above_port_line) {
    b = bin_wall_thickness_mm*2;

    // Now I try to do this math to create multiple bins
    // These will be cubes; orifices will have to be cut
    // in them later.
    de = depth/numbins; // w = width of one bin
    // TODO: Move these parameters out where they will be more accessible.
    input_diameter = 1;
    output_diameter = 3;

    for(i = [0:numbins -1]) {
        j = -(numbins-1)/2 + i;
        translate([0,j*de,0])
        translate([0,0,height_above_port_line - height/2])
        if (ROBS_ORIGINAL_BARBS) {
            union() {
 
                difference() {
                    cube([width,de,height],center = true);
                    // I want the bottom to be opened and then "capped"
                    translate([0,0,-(b+1)])
                    cube([width-b,de-b,height-bin_wall_thickness_mm],center=true);
                    translate([width/2,0,0])
                    rotate([0,90,0])
                    cylinder(b,input_diameter,     input_diameter,center=true,$fn=30);
                } 
                // WARNING! This math seems to 
                // have no rhyme or reason and is just fudged....
                translate([width/2 -1 ,0,0])
                rotate([0,90,0])
                Barb(input_diameter,output_diameter);
            } 
        } else {  
            difference() {
                // Create the solid bin wall
                cube([width,de,height],center = true);

                // Hollow out the inside of the bin
                translate([0,0,-(b+1)])
                cube([width-b,de-b,height-bin_wall_thickness_mm],center=true);

                // Cut 1/8" NPT female thread into the side wall
                translate([width/2, 0, 0])
                rotate([0, 90, 0])
                metric_thread(
                    diameter = 10.287,  // 1/8" NPT major diameter in mm (0.405 in)
                    pitch = 25.4 / 27,  // 27 TPI converted to mm pitch
                    length = 10,        // Length of the threaded section
                    internal = true,    // Make internal threads for cutting
                    taper = 0.0625,     // Standard 1:16 NPT taper
                    leadin = 3          // Chamfer at the start of the thread
                );
            }
        }
    }
}

module BinCap(depth,numbins,height,width,height_above_port_line) {
    b = bin_wall_thickness_mm*2;
    difference() {
        cube([width+b,depth+b,3],center=true);
        translate([0,0,bin_wall_thickness_mm])
        cube([width,depth,3],center=true);
    }
}

module Screws(num_screws,num_bins,depth) {
    d = (num_screws-1)*screw_center_separation_mm;
    union() {
        for (i = [0:num_screws-1]) {
            x =  -d/2+ i * screw_center_separation_mm;
            translate([x,0,0])
            CorkscrewWithSlit(depth,num_bins);
        }
    }
}
module ScrewsKnife(num_screws,num_bins,depth) {
    d = (num_screws-1)*screw_center_separation_mm;
    union() {
        // now we must cut the ports
        for (i = [0:num_screws-1]) {
             x =  -d/2+ i * screw_center_separation_mm;
             translate([x,0,0])
             CorkscrewWithoutVoidExcess(depth,filter_twist_degrees);
        } 
    }      
}
module BinsWithScrew(nums_screws,num_bins) {
    d = (num_screws-1)*screw_center_separation_mm;
    difference() {
        Bins(filter_height_mm,num_bins,bin_height_z_mm,bin_breadth_x_mm, screw_center_separation_mm);
        ScrewsKnife(num_screws,num_bins,filter_height_mm);
    }

    for (i = [0:num_screws-1]) {
        x =  -d/2 + i * screw_center_separation_mm;
        translate([x,0,0])
        CorkscrewWithSlit(filter_height_mm,num_bins);
    }
}

if (USE_FULL_BINS) {
    difference() {
        BinsWithScrew(num_screws,num_bins);
        if (USE_KNIFE_THRU_SCREWS) {
            translate([0,0,-50])
            cube([100,100,100],center = true);
        }
        if (USE_KNIFE_LOW) {
            translate([0,0,-50+-10])
            cube([100,100,100],center = true);
        }
        if (USE_KNIFE_SIDE) {
            translate([50+5,0,0])
            cube([100,100,100],center = true);
            translate([-(50+5),0,0])
            cube([100,100,100],center = true);
        }   
        if (USE_KNIFE_TOP_HALF) {
            translate([0,0,50])
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
if (USE_VOIDLESS_SCREW) {
    CorkscrewWithoutVoid(filter_height_mm,filter_twist_degrees);
}


// --- START: ISO METRIC THREAD LIBRARY ---
// ISO-standard metric threads, http://en.wikipedia.org/wiki/ISO_metric_screw_thread
// Copyright 2016 Dan Kirshner - dan_kirshner@yahoo.com, GNU GPLv3
// Version 2.2

function segments (diameter) = min (50, ceil (diameter*6));

module metric_thread (diameter=8, pitch=1, length=1, internal=true, n_starts=1,
                      thread_size=-1, groove=false, square=false, rectangle=0,
                      angle=30, taper=0, leadin=1, leadfac=1.0)
{
   local_thread_size = thread_size == -1 ? pitch : thread_size;
   local_rectangle = rectangle ? rectangle : 1;

   n_segments = segments (diameter);
   h = (square || rectangle) ? local_thread_size*local_rectangle/2 : local_thread_size / (2 * tan(angle));

   h_fac1 = (square || rectangle) ? 0.90 : 0.625;
   h_fac2 = (square || rectangle) ? 0.95 : 5.3/8;

   tapered_diameter = diameter - length*taper;

   difference () {
       union () {
           if (! groove) {
               metric_thread_turns (diameter, pitch, length, internal, n_starts,
                                    local_thread_size, groove, square, rectangle, angle,
                                    taper);
           }

           difference () {
               if (groove) {
                   cylinder (r1=diameter/2, r2=tapered_diameter/2,
                             h=length, $fn=n_segments);
               } else if (internal) {
                   cylinder (r1=diameter/2 - h*h_fac1, r2=tapered_diameter/2 - h*h_fac1,
                             h=length, $fn=n_segments);
               } else {
                   cylinder (r1=diameter/2 - h*h_fac2, r2=tapered_diameter/2 - h*h_fac2,
                             h=length, $fn=n_segments);
               }

               if (groove) {
                   metric_thread_turns (diameter, pitch, length, internal, n_starts,
                                        local_thread_size, groove, square, rectangle,
                                        angle, taper);
               }
           }
       }
       if (leadin == 2 || leadin == 3) {
           difference () {
               cylinder (r=diameter/2 + 1, h=h*h_fac1*leadfac, $fn=n_segments);
               cylinder (r2=diameter/2, r1=diameter/2 - h*h_fac1*leadfac, h=h*h_fac1*leadfac,
                         $fn=n_segments);
           }
       }
       if (leadin == 1 || leadin == 2) {
           translate ([0, 0, length + 0.05 - h*h_fac1*leadfac]) {
               difference () {
                   cylinder (r=diameter/2 + 1, h=h*h_fac1*leadfac, $fn=n_segments);
                   cylinder (r1=tapered_diameter/2, r2=tapered_diameter/2 - h*h_fac1*leadfac, h=h*h_fac1*leadfac,
                             $fn=n_segments);
               }
           }
       }
   }
}

module metric_thread_turns (diameter, pitch, length, internal, n_starts,
                            thread_size, groove, square, rectangle, angle,
                            taper)
{
   n_turns = floor (length/pitch);
   intersection () {
     for (i=[-1*n_starts : n_turns+1]) {
         translate ([0, 0, i*pitch]) {
             metric_thread_turn (diameter, pitch, internal, n_starts,
                                 thread_size, groove, square, rectangle, angle,
                                 taper, i*pitch);
         }
     }
     translate ([0, 0, length/2]) {
         cube ([diameter*3, diameter*3, length], center=true);
     }
   }
}

module metric_thread_turn (diameter, pitch, internal, n_starts, thread_size,
                           groove, square, rectangle, angle, taper, z)
{
   n_segments = segments (diameter);
   fraction_circle = 1.0/n_segments;
   for (i=[0 : n_segments-1]) {
     rotate ([0, 0, i*360*fraction_circle]) {
         translate ([0, 0, i*n_starts*pitch*fraction_circle]) {
             thread_polyhedron ((diameter - taper*(z + i*n_starts*pitch*fraction_circle))/2,
                                 pitch, internal, n_starts, thread_size, groove,
                                 square, rectangle, angle);
         }
     }
   }
}

module thread_polyhedron (radius, pitch, internal, n_starts, thread_size,
                           groove, square, rectangle, angle)
{
   n_segments = segments (radius*2);
   fraction_circle = 1.0/n_segments;
   local_rectangle = rectangle ? rectangle : 1;
   h = (square || rectangle) ? thread_size*local_rectangle/2 : thread_size / (2 * tan(angle));
   outer_r = radius + (internal ? h/20 : 0);
   h_fac1 = (square || rectangle) ? 1.1 : 0.875;
   inner_r = radius - h*h_fac1;
   translate_y = groove ? outer_r + inner_r : 0;
   reflect_x   = groove ? 1 : 0;
   x_incr_outer = (! groove ? outer_r : inner_r) * fraction_circle * 2 * PI * 1.02;
   x_incr_inner = (! groove ? inner_r : outer_r) * fraction_circle * 2 * PI * 1.02;
   z_incr = n_starts * pitch * fraction_circle * 1.005;
   z0_outer = (outer_r - inner_r) * tan(angle);
   bottom = internal ? 0.235 : 0.25;
   top    = internal ? 0.765 : 0.75;

   translate ([0, translate_y, 0]) {
     mirror ([reflect_x, 0, 0]) {
         if (square || rectangle) {
             polyhedron (
                 points = [
                     [-x_incr_inner/2, -inner_r, bottom*thread_size],[-x_incr_outer/2, -outer_r, bottom*thread_size],
                     [x_incr_inner/2, -inner_r, bottom*thread_size + z_incr],[x_incr_outer/2, -outer_r, bottom*thread_size + z_incr],
                     [x_incr_inner/2, -inner_r, top*thread_size + z_incr],[-x_incr_inner/2, -inner_r, top*thread_size],
                     [x_incr_outer/2, -outer_r, top*thread_size + z_incr],[-x_incr_outer/2, -outer_r, top*thread_size]
                 ],
                 faces = [ [0,5,7,1],[2,3,6,4],[0,2,4,1],[5,0,1,7],[3,2,5,6],[4,6,7,3] ]
             );
         } else {
             polyhedron (
                 points = [
                     [-x_incr_inner/2, -inner_r, 0],[-x_incr_outer/2, -outer_r, z0_outer],
                     [x_incr_inner/2, -inner_r, z_incr],[x_incr_outer/2, -outer_r, z0_outer + z_incr],
                     [x_incr_inner/2, -inner_r, thread_size + z_incr],[-x_incr_inner/2, -inner_r, thread_size],
                     [x_incr_outer/2, -outer_r, thread_size - z0_outer + z_incr],[-x_incr_outer/2, -outer_r, thread_size - z0_outer]
                 ],
                 faces = [ [0,5,7,1],[2,3,6,4],[0,2,4,1],[5,0,1,7],[3,2,5,6],[4,6,7,3] ]
             );
         }
     }
   }
}
// --- END: ISO METRIC THREAD LIBRARY ---