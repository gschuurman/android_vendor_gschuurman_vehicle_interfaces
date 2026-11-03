// Stencil jig for the car radio main board rev 0.6 (100 x 100 mm, 1.6 mm).
// The board and the same-size frameless stencil drop into one pocket, so their edges line up.
pcb       = 100;   // board (and stencil) size
clr       = 0.15;  // pocket clearance per side
pcb_t     = 1.60;  // board thickness
stencil_t = 0.12;  // stencil thickness
depth     = pcb_t + stencil_t - 0.03;  // stencil ends up a hair above the surround
floor_t   = 3;     // floor under the board
outer     = 140;   // jig size
relief    = 1.2;   // corner relief radius, so a square-cornered stencil fits too
notch_w   = 16;    // finger notches left and right
notch_l   = 10;
$fn = 48;

p = pcb + 2*clr;
difference() {
  linear_extrude(floor_t + depth) offset(4) square(outer - 8, center = true);
  translate([0, 0, floor_t]) linear_extrude(depth + 1) union() {
    square(p, center = true);
    for (sx = [-1, 1], sy = [-1, 1]) translate([sx*(p/2 - 0.3), sy*(p/2 - 0.3)]) circle(relief);
  }
  for (sx = [-1, 1])
    translate([sx*(p/2 + notch_l/2 - 1), 0, floor_t - 1])
      linear_extrude(depth + 2) square([notch_l + 2, notch_w], center = true);
}
