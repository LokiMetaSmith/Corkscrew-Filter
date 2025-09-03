# Bill of Materials

This document lists the required components to build the Thirsty Corkscrew filter.

## Off-the-Shelf Components

| Item                          | Description                               | Link                                      |
| ----------------------------- | ----------------------------------------- | ----------------------------------------- |
| O-Ring                        | 30mm OD, 27mm ID, 1.5mm Width             | [Amazon](https://www.amazon.com/dp/B07D24HPPW) |
| Main Tube                     | Clear, 1 3/16" (30mm) ID, 1 1/4" (32mm) OD | [Amazon](https://www.amazon.com/dp/B0DK1CNVDQ) |
| Heat Shrink Coupling (Optional) | 1-1/2" (40mm)                             | [Amazon](https://www.amazon.com/dp/B0B618769H) |
| Vacuum Hose (Example)         | 1.15" ID, 1.34" OD                        | -                                         |

## 3D Printed Components

The following parameters in `corkscrew filter.scad` should be used to generate the 3D printable parts that match the components listed above.

### Main Parameters
```openscad
num_bins = 3;
number_of_complete_revolutions = 12;
screw_OD_mm = 1.8;
screw_ID_mm = 1;
scale_ratio = 1.4;
```

### Tube Filter Parameters
```openscad
tube_od_mm = 32;
tube_wall_mm = 1;
insert_length_mm = 350/2;
oring_cross_section_mm = 1.5;
spacer_height_mm = 5;
adapter_hose_id_mm = 30;
support_rib_thickness_mm = 1.5;
support_density = 4;
flange_od = 20;
flange_height = 5;
```

### Tolerances & Fit
These values may need to be adjusted based on your specific 3D printer's calibration.
```openscad
tolerance_tube_fit = 0.2;
tolerance_socket_fit = 0.4;
tolerance_channel = 0.1;
```
