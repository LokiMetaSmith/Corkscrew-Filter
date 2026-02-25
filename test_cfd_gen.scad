include <modules/cfd_helpers.scad>

// Test Inlet
translate([50, 0, 0]) InletCap(30, 50, "circle");

// Test Outlet
translate([-50, 0, 0]) OutletCap(30, 50, "square");

// Test Wall
translate([0, 50, 0]) CFDWall(30, 50, "hex");
