// --- MODULAR 1 DIN ENCLOSURE FOR PERIPHERAL BOARD REV 0.6 + KHADAS VIM3 / M2X ---
//
// Based on "car_radio improved_0.2.scad" (prototype case). Same parts and style:
// heat-set inserts everywhere, DIN clip pockets, removal-key slots, front plate with
// screen tray + flanged spacers, separate side/top/bottom panels, IO back plate.
//
// What changed for rev 0.6:
//  * The slide-in perfboard tray is gone. The rev 0.6 main board (100 x 100 mm, KiCad
//    PCB/rev0.6/main) sits on four M3 standoffs on the bottom panel, rear right.
//  * The VIM3 + M2X stack sits on the bottom panel, front left, beside the main board.
//  * The main board is turned so its USB-module edge (KiCad right edge, x = 100) faces
//    the REAR: the three USB-A sockets on the USB module come out through the back plate.
//    Consequences (see README_case.md): the display FPC socket J14 also faces the rear,
//    so the screen ribbon needs an extension that wraps under the board, and the HDMI
//    socket J13 faces the VIM3 side, so there is an HDMI bay behind the VIM3 stack.
//  * Back plate: USB-A x3 (RTL-SDR + 2 external), RCA (reverse camera), 3.5 mm jack
//    (car microphone), SMA bulkhead (GPS antenna), one cable slit (ISO pigtails = power).
//    The old audio jack / SPDIF cutouts are removed.
//
// Coordinate system (assembly): X = 0 at the centre, +X to the right seen from the
// front; Y = 0 at the rear face of the front plate (= front end of the side panels),
// +Y towards the rear; Z = 0 at the underside of the bottom panel.
// "Body" coordinates used by the board helpers below are the same X/Z with Y measured
// from the front end of the side panels, i.e. exactly the bottom panel's frame shifted
// by -inner_plate_w/2 in X.
//
// All main-board / USB-module positions are copied from the KiCad files (rev 0.6),
// not measured from pictures. VIM3 / M2X numbers marked ASSUMPTION need a caliper check.

/* [Print Selection] */
// Select which part to generate
part_to_print = "assembly"; // [assembly, din_front_plate, screen_tray, tray_hatch, front_hook, tray_hook_left, tray_hook_right, tray_bracket, tray_carrier, bar_front, bar_back, switch_plate, tape_plate, tape_mold, button_bar, button_caps, module_spacers, vim3_retainers, standoff_spacer, left_side, right_side, bottom, top, back_plate]

/* [Assembly view] */
explode_dist = 0;
show_boards = true;      // ghost models of main board, modules, VIM3 stack, plugs and jacks
show_lid = true;         // hide the top panel to look inside

/* [Screen Interface / Adjustment] */
mount_spacing_w = 100;
mount_spacing_h = 30;
vertical_travel = 10;
spacer_length = 15;
mount_screw_diam = 4.2;

/* [Screen Configuration (Waveshare 70H-1024600)] */
screen_outer_w = 173.00;
screen_outer_h = 103.00;
screen_radius = 3.00;
screen_tolerance = 1.25;   // was 0.5: screen pocket 1.5 mm larger in width and height (Glenn, 2026-11-04)

/* [Tray & Tape Parameters] */
tray_wall_thickness = 2.0;
tray_base_thickness = 4.0;
tray_bottom_rounding = 2.0;
ledge_depth = 1.5;
tape_ledge_width = 3.0;
lcd_wiggle_room = 1.0;
// Panel depth (Glenn, 2026-11-04: the 8 mm prototype depth let the screen flex). Waveshare spec:
// 4.2 mm total with touch glass, 3.5 mm LCD body. The LCD back now rests on a foam layer on the
// tray base instead of hanging free behind the glass.
// Waveshare STEP models (IPS-CT and QLED-CT, 2026-11-09): touch glass 0.71, glass front to LCD back 6.43
// (the wiki's 4.2 mm is wrong). A 46 x 51.5 mm board on the LCD back (ribbon connector on its top
// edge) sticks out 1.84 mm further; it gets its own opening + screwed hatch in the tray base.
panel_lcd_thickness = 5.72;    // LCD body behind the glass (6.43 - 0.71)
screen_back_pad = 1.0;         // double-sided foam tape between LCD back and tray base
screen_depth = ledge_depth + panel_lcd_thickness + screen_back_pad;   // = 8.22
// The screen sits 180 deg turned compared with the prototype file: ribbon slot at the top,
// touch relief at the bottom (seen from the front). The part prints the same, just turned.
screen_features_rot180 = true;

/* [Button Bar (separate front part under the screen)] */
// Glenn, 2026-11-04: slim bar under the screen, 9 buttons in line, embossed emblems on the caps
// (paint over the raised icons). The screen tray is one piece; only this bar comes off: solder and
// assemble the switch strip in it, then screw it to the back of the tray (M2 into tray inserts).
// Buttons: 6 mm "slim" tactile switches (Kiwi KW-1556 / Adafruit 1489) on a perfboard strip.
bar_h = 18.5;                // bar height below the tray (was 13; 18.5 for the Adafruit BH1750 board, Glenn 2026-11-09)
bar_wall = 2.0;              // bottom + end walls
bar_skin = 1.6;              // front skin
bar_back_wall = 1.5;         // back wall of the bar
tongue_t = 3.5;              // plate behind the tray (bar back face is coplanar with it)
tongue_h = 14.0;             // tongue height above the tray bottom edge
tongue_screw_xs = [-80, -40, 40, 80];
tongue_screw_y = 8.5;        // above the tray bottom edge (into the tray base, M2 inserts)
// caps: pill shape, flange top + bottom only, icon raised
cap_w = 10.0;
cap_h = 6.0;
cap_clear = 0.2;             // per side, cap to skin hole
cap_protrude = 1.5;          // cap face in front of the screen / bar face
cap_flange = 0.9;            // flange lip above and below the cap (keeps it in)
cap_flange_t = 0.9;
cap_icon_h = 0.6;            // embossed icon height (paint the tops)
// Switch: Kwan Da TC-0120 (W028) drawing from Glenn (2026-11-09): body 6 x 3.5 x 3.6, knob to 4.3,
// travel 0.25, 2 cranked legs 1.0 x 0.3, 6.8-8.0 mm apart (centre ~7.4).
btn_total_h = 4.3;           // switch body + plunger, above the board
btn_body = [6.0, 3.5];       // switch footprint (X, Y)
btn_preload = 0.1;           // cap flange presses the plunger this far when idle
btn_pcb_t = 1.6;
// Order seen from the front (left = driver side, LHD): home | vol-, mute, vol+ | screen off |
// prev, play/pause, next | voice. Positions on the 2.54 mm perfboard grid relative to each other.
btn_xs = [-78.74, -60.96, -48.26, -35.56, 0, 35.56, 48.26, 60.96, 78.74];   // groups 2.54 further out (2026-11-09) so the Adafruit board fits between screen-off and prev
btn_icons = ["home", "voldown", "mute", "volup", "power", "prev", "play", "next", "mic"];
bar_rib_xs = [-68.58, -24, 68.58];    // supports behind the strip, in the gaps
bar_wire_slot = [-11, 12, 4];           // x centre, width, height of the wire exit in the back wall
// BH1750 (GY-302 module 18.5 x 13.9, chip assumed in the centre) between screen-off and prev.
// It sits behind the skin with its header edge down; its top 2 mm reach into the tray rim.
// Adafruit BH1750 (product 4681), from Adafruit's EagleCAD file: board 25.4 x 17.78, IC1 in the centre,
// STEMMA QT (JST SH4, ~2.95 high) on the chip side at both short edges (x 2.54 / 22.86, y 8.89),
// 2.5 mm holes 2.54 in from the corners, 0.1" header row along the bottom edge (y 2.54).
bh1750_x = 17.78;
bh1750_board = [25.4, 17.78];
bh1750_chip_offset = [0, 0];  // chip position relative to the board centre (check your module)
bh1750_window_d = 3.0;
bh1750_front_gap = 3.0;       // STEMMA QT connectors (2.95) between board front and skin
bh1750_sink = 1.5;            // module sinks this far into the bar bottom wall

/* [Button bar split (Glenn, 2026-11-09)] */
// The bar is now two printed parts with the switch PCB clamped between them:
// bar_front (skin, caps, bottom + end walls, PCB pocket; prints face down) and bar_back
// (flat back plate + the tongue to the tray; prints back face down). 3x M2 x 8 from the back,
// through bar_back and the PCB into M2 inserts in bar_front. The bar then goes onto the tray
// with the 4 tongue screws as before.
bar_split = true;
bar_screws = [[-86.0, 0.0], [-25.2, 3.4], [86.0, 0.0]];   // [x, y above cap_y] = KiCad (102.35,106.4) (163.15,103.0) (274.35,106.4)
bar_boss_d = 5.5;
bar_pcb_size = [176.7, 11.5];
bar_pcb_clear = 0.25;
bar_back_ribs = [-68.58, -45.72, 33.02, 58.42];   // extra PCB supports behind the board (between solder joints)

/* [Tray mount: hook-on bracket + carrier (Glenn, 2026-11-09)] */
// Bracket: screwed once to the front plate with the 4 existing slots (screws from inside the
// case into M3 inserts in the bracket; 10 mm height adjustment kept). Carrier: plate screwed to
// the 4 existing M3 inserts in the back of the tray. The carrier's cleat hangs on the bracket's
// 45 deg cleat; 2 M3 screws from below through the bracket flange into the carrier lugs lock it.
// Removing the tray: 2 screws out, lift ~5 mm, pull forward, unplug the panel FPC at the joiner.
use_tray_mount = true;
// Glenn 2026-11-09: hooks must be modular and fit the existing front plate: 2 identical front_hook
// parts (each on one pair of the existing front-plate slots) + 2 tray_hook parts (left/right, each on
// two of the existing tray inserts) instead of the one-piece bracket and carrier.
hooks_modular = true;
hook_w = 24.0;                  // width of every hook part (X), centred on the slot / insert column
brk_t = 6.0;                    // bracket plate, against the bezel
brk_w = 124.0;
brk_y = [-40.0, 32.0];          // tray frame (y = 0 at the DIN centre); bottom lowered so the lock lug sits under the insert column
cleat_d = 4.5;                  // cleat depth = 45 deg rise = lift needed to unhook
cleat_h = 8.0;
cleat_gap = 0.3;
cleat_xs = [[-62.0, -38.0], [38.0, 62.0]];  // on the two hook columns (x +-50), clear of the hatch + ribbon
carrier_t = 3.0;
carrier_w = 169.0;
carrier_bar = 12.0;             // width of the vertical carrier bars at x +-50
carrier_top_y0 = 26.0;          // top bar of the carrier from here to the tray top
carrier_bot_y = [-40.0, -18.5];   // (one-piece carrier only) // bottom bar (clears the button-bar tongue at -40.75 and the screen hatch)
carrier_gap_x = [-22.5, 38.5];  // window in the top bar: screen hatch + panel FPC
lock_xs = [-50.0, 50.0];        // under the insert columns (modular hooks)
lock_lug = [10.0, 10.0];        // X, Y of the lugs
lock_insert = [4.2, 5.8, 5.5];  // M3 insert bore d, depth, lead-in d
// FPC joiner: dropped (Glenn 2026-11-09: one ribbon straight from J14 to the panel, no extension).
use_joiner = false;
joiner_size = [30.0, 14.0];
joiner_c = [12.0, 5.0];
joiner_rim = 1.5;
// Sun-visor mount (Glenn, 2026-11-09): 4 M3 heat-set inserts straight into the left and right side
// faces of the screen tray, 2 per side, axis along X. The 2 mm side wall is too thin, so each side
// gets a solid pad on the tray back (also fills the back-edge chamfer there); the insert sits below
// the LCD pocket floor so it can't break through to the panel.
visor_hole_ys = [25.0, 45.0];        // hole centres, from the glass centre (tray top edge at +54.75)
visor_hole_z = 0.5;                  // insert axis height (tray back = 0, pocket floor = 4)
visor_pad = [10.0, 19.0, 49.5, -3.0];     // X width in from the side face, Y from, Y to, Z of its back face
visor_insert = [4.2, 6.0, 5.5];      // M3 insert: bore, depth, guide (pad version)
// Flush version (Glenn, 2026-11-09: no pad, flat tray back prints better): SHORT M3 inserts (3 mm long)
// in the 4.5 mm solid strip between the LCD pocket and the side face, above the pocket floor.
visor_flush = true;
visor_flush_z = 6.0;                 // insert axis height (pocket floor 4.0, glass seat 10.72)
visor_flush_insert = [4.0, 4.0, 5.0];   // bore, depth (0.5 mm skin to the pocket), guide

/* [Screen hatch in the tray base (Glenn, 2026-11-09)] */
// Opening over the board on the LCD back (STEP, both versions: x -15.4..31.0, y -11.96..39.6 from the
// glass centre) + 1 mm, closed from the back by a flush lid (tray_hatch) with M2 x 6 self-tapping screws.
// Glenn, 2026-11-09: the ribbon slot may sit in the lid, so the opening now reaches up over the old
// tray slot and the slot is cut in the lid instead of the tray base.
ribbon_in_hatch = true;
// Lid slot straight behind the panel's FPC connector (Glenn 13:32: keep the ribbon short). Connector from the
// Waveshare CT drawing (not a separate STEP body): 28 mm wide incl. tabs, x -6..22, y 33.4..38.85, mouth facing
// up at the board's top edge (y 39.6). Slot centre 2 mm above the mouth for the bend.
ribbon_lid_c = [8.0, 41.0];
hatch_open = [-16.4, 32.0, -13.0, 45.0];   // x0, x1, y0, y1 (tray frame = glass centre)
hatch_rim = 3.2;
hatch_t = 1.5;                  // lid thickness = rebate depth
hatch_clear = 0.2;
hatch_screws = [[-18.2, -4.0], [33.8, -4.0], [-18.2, 40.0], [33.8, 40.0]];   // 4 now the lid is taller
hatch_pilot = 1.7;              // M2 self-tapping pilot

/* [Heat-Set Insert (Melt Nut) Parameters] */
// M3 inserts (side panel assembly, screen tray, main board standoffs)
insert_hole_diameter = 4.2;
insert_clearance_hole = 3.4;
insert_hole_depth = 3.5;
insert_guide_diameter = 5.5;

/* [Side Panel Assembly Inserts] */
side_insert_hole_depth = 6.2;
// The side wall + ledge is only 7 mm thick, too thin for a 4.2 mm insert bore (the bore
// broke through the ledge face). Every insert now sits in a local boss: a 9 mm round
// pad around the insert axis, blended into the wall, reaching 2.5 mm past the ledge.
// Walls around the bore: >= 2.1 mm inside, 2.9 mm to the outer face.
side_boss_d = 9.0;
side_boss_extra = 1.5;          // boss length beyond the insert depth (vertical inserts)
front_boss_length = 11.0;       // front bosses carry the front plate + display: longer
rear_boss_length = 9.0;

/* [Top / Bottom panels] */
// Panels now run the full chassis width and sit ON the side panels (wall + ledge), so the
// screws can sit 4.5 mm from the edge: countersunk heads (6 mm) stay 1.5 mm inside the
// panel edge instead of breaking out of it (they used to sit 1.8 mm from the edge).
panel_screw_inset = 4.5;     // from the outer face of the side wall
panel_lip_h = 2.5;           // locating lip along both long edges, against the ledge face
panel_lip_w = 1.5;
panel_rib_h = 3.0;           // stiffening ribs under the top panel
panel_rib_w = 2.0;
top_rib_xs = [-16, 20, 55];
// Extra screws from the panels into the front and back plate: a boss on the panel end
// with a horizontal M3 insert; the screw goes in through the front / back plate.
// [assembly X, boss height]
front_top_bosses = [[-25, 9], [70, 9]];
front_bottom_bosses = [[36, 9], [65, 9]];
rear_top_bosses = [[-30, 9], [50, 9]];
rear_bottom_bosses = [[55, 7.5]];   // under the main board (clears the screen ribbon); X -60/-30 dropped: the M2X runs to the back plate there
panel_boss_w = 10.0;
panel_boss_depth = 9.0;      // along Y

/* [M2 Heat-Set Insert Standoffs (VIM3 / M2X)] */
m2_insert_hole_diameter = 3.2;
m2_insert_hole_depth = 3.0;
m2_insert_guide_diameter = 4.2;
m2_standoff_outer_diam = 5.5;

/* [Main Ribbon Cutout] */
ribbon_slot_width = 25.0;
ribbon_slot_thickness = 3.0;
ribbon_slot_offset_y = 7.0;
// Front plate slot and screen tray cutout stay independently adjustable (as before).
// The screen extension ribbon now arrives from under the main board at about
// X = +1.4 (J14 centre, see echo output); fold it 45 deg once to reach the slot.
front_ribbon_slot_offset_x = 12.0;  // follows the tray slot (at +12 now the screen is turned 180 deg); clears the VIM3 post
tray_ribbon_slot_offset_x = -12.0;

/* [Touch Ribbon Relief] */
touch_relief_width = 45.0;
touch_relief_depth = 12.0;
touch_relief_offset_x = -55.0;

/* [Main Chassis Dimensions] */
// Deeper than the prototype (110): VIM3 stack (front left) + HDMI bay (rear left)
// have to fit one behind the other next to the 100 mm main board. See echo check.
enclosure_depth = 134;
lid_thickness = 3;
side_wall_thickness = 3;
ledge_width = 4;

/* [Front Panel Config] */
front_wall_thickness = 5;
bezel_depth = 4;
bezel_width = 188;
bezel_height = 58;
bezel_corner_radius = 5;

/* [Front Slot Settings] */
add_front_slot = true;
slot_offset_z = -15.0;
slot_bevel_size = 1.5;

/* [Front Panel - UART Pogo Connector (Heat Staked)] */
// rev 0.6 has no UART header yet (planned for the next revision); keep or disable.
add_uart_pogo = false;     // disabled (Glenn, 2026-11-04)
pogo_front_hole_w = 18.5;
pogo_front_hole_h = 4.5;
pogo_recess_w = 26.0;
pogo_recess_h = 6.0;
pogo_peg_spacing = 22.0;
pogo_peg_diam = 1.5;
pogo_peg_height = 3.0;
pogo_face_thickness = 1.5;
pogo_offset_x = 20.0;
pogo_offset_z = -18.0;

/* [Main Board rev 0.6 (from KiCad)] */
mb_size = 100.0;            // Edge.Cuts 0..100 x 0..100, 2 mm corner radius
mb_corner_r = 2.0;
mb_thickness = 1.6;
mb_standoff_min = 8.0;      // floor to board underside (raised further below so the J13 HDMI head clears the VIM3)
mb_side_clear = 0.75;       // gap between board edge (KiCad y = 100) and the right side ledge
mb_rear_gap = 1.0;          // gap between board edge (KiCad x = 100) and the back plate
// EVERY hole on the main board gets a post with a heat-set insert, melted in from the
// top of the post before the board goes in. Positions and drills checked against the
// KiCad footprints AND the Gerber drill file (fab/main, PTH): all eight agree.
// H1-H4: M3 board screws. H5/H6/H7: M2.5, the USB / audio / GNSS module holes land
// exactly on these (checked by matching the module header pins to the main-board
// sockets). H8: M2, for the future K-line module on J10.
// H5-H8: a printed 11 mm spacer sleeve (part "module_spacers") sits between the main board
// and the module; one long screw goes through the module, the sleeve and the main board
// into the insert (M2.5 x 18 for H5-H7, M2 x 18 for H8). An 11 mm M-F brass standoff also works.
// [KiCad x, KiCad y, insert bore d, insert depth, lead-in d, post OD, screw clearance d, label]
mb_mounts = [
    [ 4.5,  4.5, 4.2, 6.0, 5.5, 8.0, 3.4, "H1 M3"],
    [95.5,  4.5, 4.2, 6.0, 5.5, 8.0, 3.4, "H2 M3"],
    [ 4.5, 95.5, 4.2, 6.0, 5.5, 8.0, 3.4, "H3 M3"],
    [95.5, 95.5, 4.2, 6.0, 5.5, 8.0, 3.4, "H4 M3"],
    [67.8, 83.7, 3.6, 5.0, 4.6, 7.0, 2.9, "H5 M2.5 USB module"],
    [31.0, 16.5, 3.6, 5.0, 4.6, 7.0, 2.9, "H6 M2.5 audio module"],
    [ 3.2, 34.3, 3.6, 5.0, 4.6, 7.0, 2.9, "H7 M2.5 GNSS module"],
    [69.6, 18.5, 3.2, 4.0, 4.2, 6.0, 2.4, "H8 M2 K-line module"]
];
// The screw clearance bore continues below the insert so a long screw or a standoff's
// male thread never bottoms out; it stops this far above the underside of the panel.
mb_screw_relief_floor = 0.6;

/* [Module spacer sleeves (printed)] */
// [screw label, inner d, outer d, how many to print (incl. one spare)]
module_spacer_types = [["M2.5", 2.9, 5.0, 4], ["M2", 2.4, 4.5, 2]];

/* [Stacked modules (from KiCad)] */
module_stack_height = 11.0; // main board top to module underside (8.5 mm socket + 2.5 mm male header body)
module_thickness = 1.6;
// USB module rev 0.6: 36 x 55 mm at main-board (64, 32.5), not rotated
usbmod_origin = [64.0, 32.5];
usbmod_size = [36.0, 55.0];
// USB-A (Molex 67643) socket centres along the module's y axis: J17 RTL-SDR, J19 Ext 1, J20 Ext 2
usb_a_centres_my = [9.63, 27.83, 46.03];
usb_a_labels = ["SDR", "USB1", "USB2"];
usb_a_shell_w = 13.2;
usb_a_shell_h = 5.2;
usb_a_center_above_module = 2.6; // ASSUMPTION: shell sits on the module PCB; check after stacking

/* [Khadas VIM3 + New M2X stack] (from Khadas VIM3 V11 DXF/STEP + New M2X STEP, 2026-11-04) */
// VIM3 local frame = Khadas DXF top view: lx along the port edge (0..82), ly across
// (0 = port edge, 56.64 = 40-pin header edge). Placed with the ports facing +X (main
// board) and lx running to the rear, so header pin 1 is at the FRONT, like J2 pin 1.
vim3_l = 82.0;              // along Y (lx)
vim3_w = 56.64;             // across X (ly)
vim3_pcb_t = 1.2;
vim3_holes = [[2.5, 53.51], [16.5, 8.01], [65.5, 8.01], [79.5, 53.51]];   // M2, DXF
vim3_hdr_lx = [7.37, 55.63];       // pin 1 .. pin 20 (row 1-20 inner, 21-40 at the edge)
vim3_hdr_ly = 52.83;               // header centre line
vim3_hdmi_lx = 38.5;               // HDMI centre (STEP), opening 0.06..5.66 above PCB top
vim3_hdmi_z = 2.86;                // HDMI centre above the VIM3 PCB top
vim3_port_overhang = 2.47;         // USB-A shells stick out past the port edge
// tallest parts on top: USB-A 7.4 (lx 0-15 and 67-82), RJ45 6.7 (lx 47-64.5)
vim3_usba_lx = [[0, 15.3], [67.1, 82.4]];
vim3_usba_h = 7.4;
vim3_usba_depth = 15.3;
vim3_heatsink_height = 10.0;       // ASSUMPTION: official heatsink, over the SoC
// New M2X (93.55 x 56 x 0.8), M.2 sockets + SSD on its UNDERSIDE (away from the VIM3;
// Glenn's photo of the stack from below, 2026-11-05). The VIM3 sits straight on the
// M2X bosses (they stick out 1.5 mm on the VIM3 side).
// Its four bosses land on the VIM3 holes with lx = 94.0 - M2X x, ly = 56.01 - M2X z;
// then the M2X cut-out (M2X x 17.5-27.5, z 19.5-42) sits exactly under the VIM3's own
// bottom M.2 slot, which drops into it (Glenn). Front edges flush (lx 0.45), the M.2
// socket end overhangs 12 mm at the REAR (lx 82..94).
m2x_l = 93.55;
m2x_w = 56.0;
m2x_pcb_t = 0.8;
m2x_front_lx = 0.45;        // M2X front edge in VIM3 lx
m2x_vim_gap = 1.5;          // M2X PCB to VIM3 PCB underside = boss height (STEP), no spacers (Glenn)
m2x_under = 3.7;            // below the M2X: M.2 sockets 3.15 (STEP) and the SSD on 1.5 mm standoffs (~3.7)
m2x_support_h = 4.5;        // floor to M2X PCB underside (two edge ledges), 0.8 mm under the SSD
vim3_side_clear = 0.8;      // header edge of the VIM3 to the left side ledge (HDMI head needs the room on the other side)
// Header alignment: the VIM3 header centre sits exactly opposite the J2 centre (Y)
vim3_ribbon_offset = 0.0;   // + moves the VIM3 to the rear
// Pocket + two printed retainer strips, screwed down with M3 into heat-set inserts
// (Glenn, 2026-11-04: no snap clips; the strips leave 0.3 mm air above the boards)
pocket_clear = 0.4;
pocket_wall = 2.0;
ret_w = 9.0;                // strip width (Y)
ret_t = 3.0;                // strip thickness
ret_air = 0.3;              // gap between strip and board top
ret_overlap = 2.0;          // how far the strip reaches over the board edge
ret_post_d = 8.0;
ret_post_gap = 1.0;         // post to board edge
ret_insert = [4.2, 5.5, 5.5];   // M3 insert bore d, depth, lead-in d
ret_screw_d = 3.4;
// strip X span (between the two screws) and where the lip may touch (clear of parts)
use_front_retainer = false;   // Glenn 2026-11-06: strip sits too low and pinches the fan wires; front hold TBD
rj45_gap = [45.5, 66.0];      // port-side ledge gap, mm from the VIM3 front edge
ret_front_xs = [-74.0, -44.0];  // over the VIM3 front edge (clear of the front USB-A)
// rear: the M2X ends 0.7 mm from the back plate; a tongue on the back plate holds it down
back_tongue_xs = [-72.0, -40.0];
back_tongue_depth = 2.5;

// Right-angle FPV HDMI heads (ribbon goes up), Glenn's cable "A2"
fpv_plug_len = 8.0;         // plug length in front of the square head PCB (Glenn)
fpv_head_t = 3.0;           // head PCB + solder side, behind the plug
fpv_head_sq = 20.0;         // square head PCB 20 x 20 (Glenn)
fpv_plug_to_bottom = 1.0;   // plug centre to bottom edge of the head PCB (Glenn: 1 mm down, 10 up)
fpv_seat_gap = 0.5;         // plug shoulder to the socket face when fully in
j13_centre_above_pcb = 3.2; // J13 HDMI centre above the main-board top. Glenn measured 2026-11-05: J13 top 6 mm above PCB -> centre ~3.05; with the 1.0 mm margin the FPV head clears the VIM3 USB-A by ~0.85 mm

// Main board height: the FPV head in J13 hangs over the VIM3's rear USB-A, so the
// board goes up until the head PCB clears it by 0.5 mm.
mb_standoff_height = max(mb_standoff_min,
    m2x_support_h + m2x_pcb_t + m2x_vim_gap + vim3_pcb_t + vim3_usba_h + 1.0
    + fpv_plug_to_bottom - j13_centre_above_pcb - mb_thickness);

/* [Backplate (IO) Configuration] */
add_back_plate = true;
back_plate_thickness = 3.0;
io_row_z = 34.0;            // height of the jack row (above the HDMI plug)
// Panel jacks, X positions (assembly X)
gps_x = 6.0;     gps_hole_diam = 6.6;  gps_flat = true;  // SMA bulkhead 1/4"-36 with anti-rotation flat
// GPS sits next to the USB row (left of the SDR port seen from behind), at USB height;
// behind it is only the low J14 corner of the main board.
gps_z = -1;                 // -1 = same height as the USB-A centres
mic_x = -60.0;   mic_hole_diam = 6.2;                     // 3.5 mm panel jack, M6 thread (e.g. PJ-392)
rca_x = -45.0;   rca_hole_diam = 10.0;                    // RCA panel jack (same size as the prototype)
// USB-A cutouts
usb_hole_w = 15.0;
usb_hole_h = 8.0;
usb_hole_r = 1.0;
usb_pocket_web = 1.0;       // plate left at the sockets, so plug overmolds can seat
usb_pocket_margin = 2.0;
// Cable slit for the ISO A + C1 pigtails (12 V power and speakers), open to the top
// edge so the loom can be laid in before the lid goes on.
wire_slit_x = 76.0;
wire_slit_w = 8.0;
wire_slit_h = 16.0;
// Inner relief for the screen ribbon wrapping around the main board edge at J14
ffc_relief_w = 28.0;
ffc_relief_h = 16.0;
ffc_relief_depth = 2.0;
// Ribbon route under the main board (assembly X / body Y), folds 45 deg at each corner
ffc_lane_x = 31.0;          // post-free lane under the board: H7 post ends at X 18.8, H5 starts at X 61
ffc_turn_y = 118.0;         // first turn, between H8 (Y 102.6) and H2/H4 (Y 128.5)
ffc_front_y = 20.0;         // second turn, in the free strip in front of the board
// Text
io_text_size = 3.0;
io_text_depth = 0.8;

/* [Global Standoff Settings] */
standoff_outer_diam = 6.0;
standoff_screw_diam = 2.8;

/* [Assembly Hardware] */
assem_screw_diam = 3.2;
assem_screw_head_diam = 6.0;
assem_screw_head_height = 3.0;
front_mount_inset_z = 12;
// Back plate / rear inserts: the lower one is raised so its boss clears the main board
// corner (board z 11..12.6 reaches the right-hand ledge at the rear).
rear_mount_z = [20, 37.5];
// Raised main board (2026-11-04): its rear right corner now sits where the RIGHT side's
// lower rear insert pad was. That pad and its back-plate screw are dropped, so the
// already printed right side can be reused after sawing that pad off.
right_drop_low_rear = true;

/* [DIN Retainer Clip Pockets] */
add_din_clip_pockets = true;
clip_length = 130.0;
clip_width = 10.0;
clip_thickness = 1.0;
clip_pocket_clearance = 0.4;
clip_height_z = 25.0;
clip_catch_offset_from_front = 15.0;

/* [DIN Removal Key Slots] */
add_key_slots = false;     // release-key holes removed (Glenn, 2026-11-04)
key_slot_width = 7.0;
key_slot_height = 7.0;

/* [Ventilation] */
add_ventilation = true;      // side slots
add_lid_vents = true;        // slots in the top panel over the VIM3
lid_vent_w = 3.0;
lid_vent_pitch = 7.0;

/* [Fine Tuning] */
iso_width = 178;
iso_height = 50;
fit_tolerance = 0.5;


// --- CALCULATIONS & COORDINATE SYSTEM ---

chassis_w = iso_width - fit_tolerance;
chassis_h = iso_height - fit_tolerance;
inner_plate_w = chassis_w - (side_wall_thickness * 2) - 0.4;
clear_interior_w = inner_plate_w - (ledge_width * 2);
side_total_thickness = side_wall_thickness + ledge_width;
ledge_face_x = chassis_w/2 - side_total_thickness;   // inner face of the side ledges (+/-)

// Screen tray derived vars
inner_w = screen_outer_w + (screen_tolerance * 2);
inner_h = screen_outer_h + (screen_tolerance * 2);
outer_w = inner_w + (tray_wall_thickness * 2);
outer_h = inner_h + (tray_wall_thickness * 2);
outer_d = tray_base_thickness + screen_depth;
outer_r = screen_radius + tray_wall_thickness;

// Heights
floor_z = lid_thickness;
lid_z = chassis_h - lid_thickness;                   // underside of the top panel
mb_bottom_z = floor_z + mb_standoff_height;
mb_top_z = mb_bottom_z + mb_thickness;
module_bottom_z = mb_top_z + module_stack_height;
module_top_z = module_bottom_z + module_thickness;
usb_a_z = module_top_z + usb_a_center_above_module;
gps_zz = (gps_z < 0) ? usb_a_z : gps_z;

// Main board placement: KiCad (bx, by) -> body (X, Y).
// Rotated 90 deg so KiCad x = 100 (USB / FPC edge) faces the rear and KiCad y = 0
// (VIM3 ribbon, HDMI, VIN, power key) faces the VIM3 on the left.
mb_x0 = ledge_face_x - mb_side_clear - mb_size;      // X of KiCad y = 0
mb_y0 = enclosure_depth - mb_rear_gap - mb_size;     // Y of KiCad x = 0
function mb2body(p) = [mb_x0 + p[1], mb_y0 + p[0]];
function usb2body(p) = mb2body([usbmod_origin[0] + p[0], usbmod_origin[1] + p[1]]);

// VIM3 stack placement (body coordinates)
vim3_xr = -ledge_face_x + vim3_side_clear + vim3_w;      // X of the port edge (ly = 0)
function v2b(lx, ly) = [vim3_xr - ly, vim3_y0 + lx];
m2x_bottom_z = floor_z + m2x_support_h;                  // M2X PCB underside
vim3_bottom_z = m2x_bottom_z + m2x_pcb_t + m2x_vim_gap;
vim3_top_z = vim3_bottom_z + vim3_pcb_t;
stack_x0 = vim3_xr - vim3_w;

// HDMI J13 on the main board: footprint body x 70.19..85.19 (KiCad), mouth at y = 0
j13_centre_y = mb2body([77.69, 0])[1];
j13_z = mb_top_z + j13_centre_above_pcb;
// J2 (2x20 IDC): pin 1 at KiCad (13.64, 6.76), pin 39 at (61.91, 6.77)
j2_centre_y = mb2body([(13.64 + 61.91)/2, 0])[1];
vim3_y0 = j2_centre_y - (vim3_hdr_lx[0] + vim3_hdr_lx[1])/2 + vim3_ribbon_offset;
stack_y0 = vim3_y0 + m2x_front_lx;                      // M2X front edge
stack_y1 = stack_y0 + m2x_l;                              // M2X rear edge (M.2 sockets)
vim3_y1 = vim3_y0 + vim3_l;
vim3_hdmi_c = v2b(vim3_hdmi_lx, -vim3_port_overhang);    // [X, Y] of the socket face
vim3_hdmi_cz = vim3_top_z + vim3_hdmi_z;
// FPV head boxes [x0, x1, y0, y1, z0, z1]
vim3_head = [vim3_xr + 1.31 + fpv_seat_gap, vim3_xr + 1.31 + fpv_seat_gap + fpv_head_t,
             vim3_hdmi_c[1] - fpv_head_sq/2, vim3_hdmi_c[1] + fpv_head_sq/2,
             vim3_hdmi_cz - fpv_plug_to_bottom, vim3_hdmi_cz - fpv_plug_to_bottom + fpv_head_sq];
j13_head = [mb_x0 - fpv_seat_gap - fpv_head_t, mb_x0 - fpv_seat_gap,
            j13_centre_y - fpv_head_sq/2, j13_centre_y + fpv_head_sq/2,
            j13_z - fpv_plug_to_bottom, j13_z - fpv_plug_to_bottom + fpv_head_sq];

// Screen FPC J14 (KiCad 94.75..99.66 x 8.64..32.14)
j14_x_lo = mb2body([0, 8.64])[0];
j14_x_hi = mb2body([0, 32.14])[0];

// --- FIT CHECKS (printed in the console) ---
echo(str("Overall depth incl. bezel and back plate: ", bezel_depth + front_wall_thickness + enclosure_depth + back_plate_thickness, " mm"));
echo(str("VIM3 port edge X=", vim3_xr, ", VIM3 HDMI head back X=", vim3_head[1], ", main board edge X=", mb_x0,
         (vim3_head[1] <= mb_x0 - 0.3) ? "  OK" : "  CONFLICT: VIM3 HDMI head hits the main board edge"));
echo(str("VIM3 header edge X=", stack_x0, ", side ledge X=", -ledge_face_x));
echo(str("Stack Y ", stack_y0, "..", stack_y1, " (M2X overhang at the rear), back plate at, enclosure depth ", enclosure_depth));
echo(str("Header pin 1 Y=", v2b(vim3_hdr_lx[0], 0)[1], " / J2 pin 1 Y=", mb2body([13.64, 0])[1]));
echo(str("VIM3 HDMI centre Y=", vim3_hdmi_c[1], " z=", vim3_hdmi_cz, "; J13 centre Y=", j13_centre_y, " z=", j13_z));
echo(str("J13 head bottom z=", j13_head[4], ", VIM3 USB-A top z=", vim3_top_z + vim3_usba_h));
echo(str("Main board standoff ", mb_standoff_height, " mm (was 8)"));
echo(str("VIM3 top (with heatsink) z=", vim3_top_z + vim3_heatsink_height, ", lid underside z=", lid_z));
echo(str("Main board z ", mb_bottom_z, "..", mb_top_z, ", modules ", module_bottom_z, "..", module_top_z, ", USB-A centre z=", usb_a_z));
echo(str("Screen ribbon (J14) leaves the board at X ", j14_x_lo, "..", j14_x_hi));
for (m = mb_mounts)
    echo(str("Post ", m[7], ": KiCad (", m[0], ", ", m[1], ") -> assembly X=", mb2body([m[0], m[1]])[0],
             " Y=", mb2body([m[0], m[1]])[1] + front_wall_thickness, ", insert bore ", m[2], " x ", m[3], " deep, post OD ", m[5]));


// --- HELPER MODULES (unchanged from the prototype) ---

module pcb_standoff_custom(h, outer_d, inner_d) {
    difference() {
        cylinder(h=h, d=outer_d, $fn=30);
        translate([0,0,-1]) cylinder(h=h+2, d=inner_d, $fn=30);
    }
}

module standoff_post(height, outer_d=m2_standoff_outer_diam) {
    cylinder(h=height, d=outer_d, $fn=30);
}

module standoff_insert_cut(height, insert_depth=m2_insert_hole_depth, insert_d=m2_insert_hole_diameter, guide_d=m2_insert_guide_diameter) {
    translate([0, 0, height])
        rotate([180, 0, 0])
        heatset_insert_bore(depth=insert_depth, hole_d=insert_d, guide_d=guide_d);
}

module rounded_rect_2d(w, h, r) {
    safe_r = min(r, w/2, h/2);
    hull() {
        translate([(w/2) - safe_r, (h/2) - safe_r]) circle(r=safe_r, $fn=30);
        translate([-(w/2) + safe_r, (h/2) - safe_r]) circle(r=safe_r, $fn=30);
        translate([(w/2) - safe_r, -(h/2) + safe_r]) circle(r=safe_r, $fn=30);
        translate([-(w/2) + safe_r, -(h/2) + safe_r]) circle(r=safe_r, $fn=30);
    }
}

module rounded_rect_slice(w, h, r) {
    linear_extrude(height=0.1) rounded_rect_2d(w, h, r);
}

module rounded_plate(w, h, thk, r) {
    safe_r = min(r, w/2, h/2);
    hull() {
        translate([safe_r, safe_r, 0]) cylinder(h=thk, r=safe_r, $fn=30);
        translate([w - safe_r, safe_r, 0]) cylinder(h=thk, r=safe_r, $fn=30);
        translate([safe_r, h - safe_r, 0]) cylinder(h=thk, r=safe_r, $fn=30);
        translate([w - safe_r, h - safe_r, 0]) cylinder(h=thk, r=safe_r, $fn=30);
    }
}

module tray_rounded_rect(w, h, d, r) {
    translate([-w/2, -h/2, 0])
    hull() {
        translate([r, r, 0]) cylinder(h=d, r=r, $fn=40);
        translate([w-r, r, 0]) cylinder(h=d, r=r, $fn=40);
        translate([r, h-r, 0]) cylinder(h=d, r=r, $fn=40);
        translate([w-r, h-r, 0]) cylinder(h=d, r=r, $fn=40);
    }
}

module filleted_bottom_rect(w, h, d, r, f) {
    safe_f = max(0.01, min(f, r, d));
    translate([-w/2, -h/2, 0])
    hull() {
        translate([r, r, safe_f]) cylinder(h=d-safe_f, r=r, $fn=40);
        translate([w-r, r, safe_f]) cylinder(h=d-safe_f, r=r, $fn=40);
        translate([r, h-r, safe_f]) cylinder(h=d-safe_f, r=r, $fn=40);
        translate([w-r, h-r, safe_f]) cylinder(h=d-safe_f, r=r, $fn=40);
        for (a = [0 : 15 : 90]) {
            let(z = safe_f - safe_f * sin(a), xy_r = r - safe_f + safe_f * cos(a)) {
                translate([r, r, z]) cylinder(h=0.01, r=xy_r, $fn=20);
                translate([w-r, r, z]) cylinder(h=0.01, r=xy_r, $fn=20);
                translate([r, h-r, z]) cylinder(h=0.01, r=xy_r, $fn=20);
                translate([w-r, h-r, z]) cylinder(h=0.01, r=xy_r, $fn=20);
            }
        }
    }
}

module countersunk_hole(thk, thru_d, head_d, angle=90, from_top=false) {
    cs_depth_raw = (head_d - thru_d) / (2 * tan(angle/2));
    cs_depth = min(thk, cs_depth_raw);
    translate([0,0,-1]) cylinder(h=thk+2, d=thru_d, $fn=30);
    if (!from_top) {
        translate([0,0,-0.01]) cylinder(h=cs_depth+0.02, d1=head_d, d2=thru_d, $fn=40);
    } else {
        translate([0,0,thk - cs_depth + 0.01]) cylinder(h=cs_depth+0.02, d1=thru_d, d2=head_d, $fn=40);
    }
}

module heatset_insert_bore(depth=insert_hole_depth, hole_d=insert_hole_diameter, guide_d=insert_guide_diameter) {
    union() {
        translate([0, 0, -0.01])
            cylinder(h=depth + 0.01, d=hole_d, $fn=30);
        cylinder(h=0.6, d1=guide_d, d2=hole_d, $fn=30);
    }
}

module smooth_ribbon_slot_with_guide(w, thk, d) {
    r = thk / 2;
    translate([0, 0, -d/2])
    linear_extrude(d)
    hull() {
        translate([-w/2 + r, 0]) circle(r=r, $fn=30);
        translate([ w/2 - r, 0]) circle(r=r, $fn=30);
    }
    translate([0, 0, d/2 - r])
    hull() {
        translate([-w/2 + r, 0, 0]) cylinder(r1=r, r2=r*2, h=r+0.01, $fn=30);
        translate([ w/2 - r, 0, 0]) cylinder(r1=r, r2=r*2, h=r+0.01, $fn=30);
    }
    translate([0, 0, -d/2 - 0.01])
    hull() {
        translate([-w/2 + r, 0, 0]) cylinder(r1=r*2, r2=r, h=r+0.01, $fn=30);
        translate([ w/2 - r, 0, 0]) cylinder(r1=r*2, r2=r, h=r+0.01, $fn=30);
    }
}

// Side panel / back plate assembly screw positions along the depth
function side_screw_ys() = [20, enclosure_depth/2, enclosure_depth - 15];


// --- 1. SCREEN TRAY (Tape-In Style) + BUTTON BAR ---
// Tray frame: x to the right and y up as seen from the front, z = 0 at the back (base),
// z = outer_d at the front face. The bar hangs under the tray: y from tb_y0 to tb_y1.
tb_y1 = -outer_h/2;                    // tray bottom edge = bar top
tb_y0 = tb_y1 - bar_h;
cap_y = tb_y1 - bar_h/2;
bar_skin_back = outer_d - bar_skin;
cap_flange_back_z = bar_skin_back - cap_flange_t;
btn_pcb_front_z = cap_flange_back_z - (btn_total_h - btn_preload);
btn_pcb_back_z = btn_pcb_front_z - btn_pcb_t;
bar_cav_back_z = -tongue_t + bar_back_wall;
bh_y0 = tb_y0 + bar_wall - bh1750_sink + 0.1;           // module bottom edge
bh_y1 = bh_y0 + bh1750_board[1];                        // module top edge (into the tray rim)
bh_z1 = bar_skin_back - bh1750_front_gap;               // board front face
bh_z0 = bh_z1 - btn_pcb_t;
bh_chip = [bh1750_x + bh1750_chip_offset[0], (bh_y0 + bh_y1)/2 + bh1750_chip_offset[1]];

// tray outline: top corners rounded, bottom corners square (the bar continues below)
module tray_outline_2d() {
    hull() {
        for (sx = [-1, 1]) translate([sx * (outer_w/2 - outer_r), outer_h/2 - outer_r]) circle(r=outer_r, $fn=48);
        translate([-outer_w/2, -outer_h/2]) square([outer_w, 1]);
    }
}
// bar outline: top square, bottom corners rounded
module bar_outline_2d() {
    hull() {
        for (sx = [-1, 1]) translate([sx * (outer_w/2 - outer_r), tb_y0 + outer_r]) circle(r=outer_r, $fn=48);
        translate([-outer_w/2, tb_y1 - 1]) square([outer_w, 1]);
    }
}
module pill_2d(w, h) { hull() for (sx = [-1, 1]) translate([sx * (w - h)/2, 0]) circle(d=h, $fn=36); }

// Icons for the caps, about 7.5 x 4.6 mm, lines >= 0.8 mm for a 0.4 nozzle
module icon_2d(name) {
    module spk() polygon([[-3.9, -0.9], [-2.7, -0.9], [-1.0, -2.3], [-1.0, 2.3], [-2.7, 0.9], [-3.9, 0.9]]);
    module tri_l(x) translate([x, 0]) polygon([[1.4, 2.0], [1.4, -2.0], [-1.3, 0]]);
    module tri_r(x) translate([x, 0]) polygon([[-1.4, 2.0], [-1.4, -2.0], [1.3, 0]]);
    if (name == "voldown") { spk(); translate([0.6, -0.45]) square([3.2, 0.9]); }
    else if (name == "volup") { spk(); translate([0.6, -0.45]) square([3.2, 0.9]); translate([1.75, -1.6]) square([0.9, 3.2]); }
    else if (name == "mute") { spk(); translate([2.2, 0]) for (a = [45, -45]) rotate(a) square([3.6, 0.85], center=true); }
    else if (name == "prev") { translate([-3.4, -2]) square([0.9, 4]); tri_l(-1.1); tri_l(1.6); }
    else if (name == "next") { translate([2.5, -2]) square([0.9, 4]); tri_r(1.1); tri_r(-1.6); }
    else if (name == "play") { tri_r(-1.6); translate([0.6, -2]) square([0.9, 4]); translate([2.2, -2]) square([0.9, 4]); }
    else if (name == "power") {
        difference() { circle(r=2.3, $fn=40); circle(r=1.45, $fn=40); translate([-0.9, 0]) square([1.8, 3]); }
        translate([-0.42, -0.4]) square([0.84, 2.9]);
    }
    else if (name == "home") {
        house = [[-2.5, -2.2], [2.5, -2.2], [2.5, 0.5], [0, 2.5], [-2.5, 0.5]];
        difference() { offset(r=0.3, $fn=12) polygon(house); offset(delta=-0.55) polygon(house); }
        translate([-0.6, -2.2]) square([1.2, 1.9]);
    }
    else if (name == "mic") {
        translate([0, 0.9]) hull() { translate([0, 0.9]) circle(d=1.9, $fn=24); translate([0, -0.5]) circle(d=1.9, $fn=24); }
        difference() { translate([0, 0.2]) circle(r=2.1, $fn=40); translate([0, 0.2]) circle(r=1.3, $fn=40); translate([-3, 0.2]) square([6, 3]); }
        translate([-0.4, -2.3]) square([0.8, 0.8]);
        translate([-1.3, -2.4]) square([2.6, 0.75]);
    }
}

module screen_tray() {
    difference() {
        union() {
            hull() {
                translate([0, 0, tray_bottom_rounding]) linear_extrude(outer_d - tray_bottom_rounding) tray_outline_2d();
                linear_extrude(tray_bottom_rounding) offset(delta=-tray_bottom_rounding) tray_outline_2d();
            }
            // sun-visor pads on the back of both side ends
            if (!visor_flush) for (sx = [-1, 1]) translate([sx > 0 ? outer_w/2 - visor_pad[0] : -outer_w/2, visor_pad[1], visor_pad[3]])
                cube([visor_pad[0], visor_pad[2] - visor_pad[1], tray_bottom_rounding - visor_pad[3]]);
        }
        // sun-visor M3 inserts in the side faces
        vi = visor_flush ? visor_flush_insert : visor_insert;
        for (sx = [-1, 1]) for (vy = visor_hole_ys) translate([sx * outer_w/2, vy, visor_flush ? visor_flush_z : visor_hole_z]) rotate([0, sx * -90, 0])
            heatset_insert_bore(depth=vi[1], hole_d=vi[0], guide_d=vi[2]);
        // ---- screen pocket (as before; turned 180 deg if screen_features_rot180) ----
        translate([0, 0, outer_d - ledge_depth])
            tray_rounded_rect(inner_w, inner_h, ledge_depth + 1, screen_radius);
        translate([0, 0, tray_base_thickness])
            linear_extrude(outer_d)
            square([inner_w - (tape_ledge_width * 2) + lcd_wiggle_room,
                    inner_h - (tape_ledge_width * 2) + lcd_wiggle_room], center=true);
        for(tx=[-mount_spacing_w/2, mount_spacing_w/2]) {
            for(ty=[-mount_spacing_h/2, mount_spacing_h/2]) {
                translate([tx, ty, -1])
                    cylinder(d=insert_clearance_hole, h=tray_base_thickness + 2, $fn=20);
                translate([tx, ty, tray_base_thickness - insert_hole_depth])
                    cylinder(d=insert_hole_diameter, h=insert_hole_depth + 0.1, $fn=30);
                translate([tx, ty, tray_base_thickness - 0.5])
                    cylinder(d1=insert_hole_diameter, d2=insert_guide_diameter, h=0.51, $fn=30);
            }
        }
        rotate([0, 0, screen_features_rot180 ? 180 : 0]) {
            if (!ribbon_in_hatch) translate([tray_ribbon_slot_offset_x, -inner_h/2 + ribbon_slot_offset_y, tray_base_thickness/2])
                smooth_ribbon_slot_with_guide(ribbon_slot_width, ribbon_slot_thickness, tray_base_thickness);
            translate([touch_relief_offset_x, inner_h/2 - touch_relief_depth/2, tray_base_thickness])
                linear_extrude(outer_d)
                square([touch_relief_width, touch_relief_depth], center=true);
        }
        // ---- hatch over the board on the LCD back ----
        translate([hatch_open[0], hatch_open[2], -1]) cube([hatch_open[1] - hatch_open[0], hatch_open[3] - hatch_open[2], tray_base_thickness + 2]);
        translate([hatch_open[0] - hatch_rim, hatch_open[2] - hatch_rim, -1]) cube([hatch_open[1] - hatch_open[0] + 2 * hatch_rim, hatch_open[3] - hatch_open[2] + 2 * hatch_rim, hatch_t + 1]);
        for (h = hatch_screws) translate([h[0], h[1], -1]) cylinder(d=hatch_pilot, h=hatch_t + 1 + 2.3, $fn=16);
        // pry slot for a small screwdriver at the bottom edge of the hatch
        translate([(hatch_open[0] + hatch_open[1])/2 - 4, hatch_open[2] - hatch_rim - 1.5, -1]) cube([8, 2.5, hatch_t + 1 + 0.8]);
        // ---- M2 inserts in the back for the button bar tongue ----
        for (x = tongue_screw_xs)
            translate([x, tb_y1 + tongue_screw_y, 0]) mirror([0, 0, 1]) rotate([180, 0, 0])
                heatset_insert_bore(depth=m2_insert_hole_depth, hole_d=m2_insert_hole_diameter, guide_d=m2_insert_guide_diameter);
        // ---- top of the BH1750 module reaches into the tray rim ----
        translate([bh1750_x - bh1750_board[0]/2 - 0.3, tb_y1 - 1, bh_z0 - 0.3])
            cube([bh1750_board[0] + 0.6, bh_y1 + 0.2 - tb_y1 + 1, bar_skin_back - bh_z0 + 0.3]);
    }
}

module button_bar() {
    W = outer_w;
    difference() {
        union() {
            translate([0, 0, -tongue_t]) linear_extrude(outer_d + tongue_t) bar_outline_2d();
            // tongue behind the tray
            translate([-W/2 + 1, tb_y1 - 1, -tongue_t]) cube([W - 2, tongue_h + 1, tongue_t]);
        }
        // cavity, open at the top (closed by the tray bottom face)
        translate([-W/2 + bar_wall, tb_y0 + bar_wall, bar_cav_back_z])
            cube([W - 2 * bar_wall, bar_h - bar_wall + 1, bar_skin_back - bar_cav_back_z]);
        // perfboard strip grooves (bottom wall + both end walls); the strip drops in from the top
        translate([-W/2 + bar_wall - 0.8, tb_y0 + bar_wall - 0.8, btn_pcb_back_z - 0.15])
            cube([W - 2 * bar_wall + 1.6, bar_h + 2, btn_pcb_t + 0.3]);
        // cap holes
        for (x = btn_xs) translate([x, cap_y, bar_skin_back - 1]) linear_extrude(bar_skin + 2) pill_2d(cap_w + 2 * cap_clear, cap_h + 2 * cap_clear);
        // BH1750: module pocket (sinks into the bottom wall) + light window
        translate([bh1750_x - bh1750_board[0]/2 - 0.3, bh_y0 - 0.1, bh_z0 - 0.3])
            cube([bh1750_board[0] + 0.6, bar_h + 1, bar_skin_back - bh_z0 + 0.3]);
        translate([bh_chip[0], bh_chip[1], bar_skin_back - 0.01])
            cylinder(d1=bh1750_window_d, d2=bh1750_window_d + 1.4, h=bar_skin + 0.02, $fn=30);
        // tongue screws (M2, counterbored from the back)
        for (x = tongue_screw_xs) translate([x, tb_y1 + tongue_screw_y, -tongue_t - 1]) {
            cylinder(d=2.4, h=tongue_t + 2, $fn=20);
            cylinder(d=4.2, h=1 + 1.6, $fn=24);
        }
        // wire exit in the back wall
        translate([bar_wire_slot[0] - bar_wire_slot[1]/2, cap_y - bar_wire_slot[2]/2, -tongue_t - 1])
            cube([bar_wire_slot[1], bar_wire_slot[2], bar_back_wall + 2]);
    }
    // ribs behind the strip (stop it bowing when a button is pressed)
    for (x = bar_rib_xs)
        translate([x - 0.6, tb_y0 + bar_wall, bar_cav_back_z - 0.01])
            cube([1.2, bar_h - bar_wall - 1, btn_pcb_back_z - bar_cav_back_z - 0.1]);
}

// Screen hatch lid, in place (tray frame): flush in the rebate of the tray base
module ghost_panel() {   // Waveshare 70H, from the STEP files
    gz = outer_d - ledge_depth;
    color("#20304a") translate([-86.5, -51.5, gz]) cube([173, 103, 0.71]);
    color("#303030") translate([-80.2, -48.8 - 0.3, gz - panel_lcd_thickness]) cube([163.9, 97.6, panel_lcd_thickness]);
    color("Green") translate([-15.4, -11.96, gz - panel_lcd_thickness - 1.84]) cube([46.4, 51.56, 3.42]);
}
module tray_hatch() {
    c = hatch_clear;
    difference() {
        translate([hatch_open[0] - hatch_rim + c, hatch_open[2] - hatch_rim + c, 0])
            cube([hatch_open[1] - hatch_open[0] + 2 * hatch_rim - 2 * c, hatch_open[3] - hatch_open[2] + 2 * hatch_rim - 2 * c, hatch_t]);
        for (h = hatch_screws) translate([h[0], h[1], -1]) {
            cylinder(d=2.4, h=hatch_t + 2, $fn=20);
            cylinder(d1=4.4, d2=2.4, h=1 + 1.0, $fn=24);    // countersink from the back (flat-head M2)
        }
        // ribbon slot (same place as the old tray-base slot), edges chamfered 0.5 mm
        if (ribbon_in_hatch) {
            rc = ribbon_lid_c;
            r = ribbon_slot_thickness/2;
            translate([rc[0], rc[1], -1]) linear_extrude(hatch_t + 2) hull() for (sx = [-1, 1]) translate([sx * (ribbon_slot_width/2 - r), 0]) circle(r=r, $fn=30);
            for (z = [0, hatch_t]) translate([rc[0], rc[1], z]) hull() for (sx = [-1, 1]) translate([sx * (ribbon_slot_width/2 - r), 0, -0.5]) cylinder(r1=z == 0 ? r + 0.5 : r, r2=z == 0 ? r : r + 0.5, h=1.0, $fn=30);
        }
    }
}

// ---- Split button bar (bar_split): bar_front + PCB + bar_back ----
bar_pcb_c = [0, cap_y + 0.65];                 // KiCad board centre y 105.75 vs switch row 106.4
module bar_front() {
    W = outer_w;
    difference() {
        translate([0, 0, btn_pcb_back_z]) linear_extrude(outer_d - btn_pcb_back_z) bar_outline_2d();
        // switch space in front of the PCB, open at the top (closed by the tray bottom face)
        translate([-W/2 + bar_wall, tb_y0 + bar_wall, btn_pcb_front_z - 0.01])
            cube([W - 2 * bar_wall, bar_h - bar_wall + 1, bar_skin_back - btn_pcb_front_z + 0.01]);
        // PCB pocket (open at the top and the back)
        translate([-bar_pcb_size[0]/2 - bar_pcb_clear, bar_pcb_c[1] - bar_pcb_size[1]/2 - bar_pcb_clear, btn_pcb_back_z - 1])
            cube([bar_pcb_size[0] + 2 * bar_pcb_clear, bar_h, btn_pcb_front_z - btn_pcb_back_z + 1.01]);
        for (x = btn_xs) translate([x, cap_y, bar_skin_back - 1]) linear_extrude(bar_skin + 2) pill_2d(cap_w + 2 * cap_clear, cap_h + 2 * cap_clear);
        translate([bh1750_x - bh1750_board[0]/2 - 0.3, bh_y0 - 0.1, bh_z0 - 0.3])
            cube([bh1750_board[0] + 0.6, bar_h + 1, bar_skin_back - bh_z0 + 0.3]);
        translate([bh_chip[0], bh_chip[1], bar_skin_back - 0.01])
            cylinder(d1=bh1750_window_d, d2=bh1750_window_d + 1.4, h=bar_skin + 0.02, $fn=30);
        // room for the solder joints of the BH1750 header row; the wires go back past the switch board
        translate([bh1750_x - bh1750_board[0]/2 + 4.5, bh_y0 - 0.1, btn_pcb_back_z - 1]) cube([16.4, 4.6, bh_z0 - btn_pcb_back_z + 1.01]);
    }
    // BH1750: two locating pins through the upper 2.5 mm holes (fix with a dot of hot glue)
    for (hx = [2.54, 22.86]) translate([bh1750_x - bh1750_board[0]/2 + hx, bh_y0 + 15.24, 0]) {
        translate([0, 0, bh_z1]) cylinder(d=4.5, h=bar_skin_back - bh_z1 + 0.01, $fn=28);
        translate([0, 0, bh_z0 + 0.3]) cylinder(d=2.2, h=bh_z1 - bh_z0, $fn=20);
    }
    // screw bosses with M2 inserts (pressed in from the PCB side)
    for (b = bar_screws) translate([b[0], cap_y + b[1], btn_pcb_front_z]) difference() {
        cylinder(d=bar_boss_d, h=bar_skin_back - btn_pcb_front_z + 0.01, $fn=32);
        heatset_insert_bore(depth=m2_insert_hole_depth, hole_d=m2_insert_hole_diameter, guide_d=m2_insert_guide_diameter);
    }
}
module bar_back() {
    W = outer_w;
    top_wall = 1.0;
    difference() {
        union() {
            difference() {
                translate([0, 0, -tongue_t]) linear_extrude(btn_pcb_back_z + tongue_t) bar_outline_2d();
                // solder-side cavity behind the PCB
                translate([-W/2 + bar_wall, tb_y0 + bar_wall, bar_cav_back_z])
                    cube([W - 2 * bar_wall, bar_h - bar_wall - top_wall, btn_pcb_back_z - bar_cav_back_z + 1]);
            }
            translate([-W/2 + 1, tb_y1 - 1, -tongue_t]) cube([W - 2, tongue_h + 1, tongue_t]);
            // support pads behind every switch, between its two pins and clear of the diode pads
            for (x = btn_xs) translate([x - 0.6, cap_y - 1.8, bar_cav_back_z - 0.01]) cube([1.2, 4.2, btn_pcb_back_z - bar_cav_back_z + 0.01]);
            // standoffs around the screws (d 4.4: clear of the diode solder joints next to the end screws)
            for (b = bar_screws) translate([b[0], cap_y + b[1], bar_cav_back_z - 0.01]) cylinder(d=4.4, h=btn_pcb_back_z - bar_cav_back_z + 0.01, $fn=28);
        }
        for (b = bar_screws) translate([b[0], cap_y + b[1], -tongue_t - 1]) {
            cylinder(d=2.4, h=tongue_t + btn_pcb_back_z + 2, $fn=20);
            cylinder(d=4.2, h=1 + 1.6, $fn=24);
        }
        for (x = tongue_screw_xs) translate([x, tb_y1 + tongue_screw_y, -tongue_t - 1]) {
            cylinder(d=2.4, h=tongue_t + 2, $fn=20);
            cylinder(d=4.2, h=1 + 1.6, $fn=24);
        }
        translate([bar_wire_slot[0] - bar_wire_slot[1]/2, cap_y - bar_wire_slot[2]/2, -tongue_t - 1])
            cube([bar_wire_slot[1], bar_wire_slot[2], bar_back_wall + 2]);
    }
}
// Printed switch plate (Glenn, 2026-11-09): drop-in replacement for the button PCB, same outline
// and 1.6 mm thickness, so bar_front / bar_back are unchanged. The switch legs go through the
// plate and are wired point to point on the back (GND to one leg of every switch, J12 lines and
// BAT85 diodes to the other legs, see wiring/wiring.png). The back is recessed 0.8 mm between the
// pads round the switches and screws, giving 3.8 mm for wires and diodes.
sp_leg_pitch = 7.4;       // TC-0120 drawing: legs 6.8-8.0 apart (+-0.5)
sp_leg_slot = [1.8, 0.8]; // legs are 1.0 x 0.3 strips
sp_pad = [11.0, 7.0];
sp_recess = 0.8;
module switch_plate() {
    L = bar_pcb_size[0]; H = bar_pcb_size[1];
    y0 = bar_pcb_c[1] - H/2;
    difference() {
        translate([-L/2, y0, btn_pcb_back_z]) cube([L, H, btn_pcb_t]);
        difference() {
            translate([-L/2 + 1.2, y0 + 1.0, btn_pcb_back_z - 1]) cube([L - 2.4, H - 2.0, 1 + sp_recess]);
            for (x = btn_xs) translate([x - sp_pad[0]/2, cap_y - sp_pad[1]/2, btn_pcb_back_z - 2]) cube([sp_pad[0], sp_pad[1], 4]);
            for (b = bar_screws) translate([b[0], cap_y + b[1], btn_pcb_back_z - 2]) cylinder(d=6.0, h=4, $fn=28);
        }
        for (x = btn_xs) for (dx = [-1, 1]) translate([x + dx * sp_leg_pitch/2 - sp_leg_slot[0]/2, cap_y - sp_leg_slot[1]/2, btn_pcb_back_z - 1]) cube([sp_leg_slot[0], sp_leg_slot[1], btn_pcb_t + 2]);
        for (b = bar_screws) translate([b[0], cap_y + b[1], btn_pcb_back_z - 1]) cylinder(d=2.4, h=btn_pcb_t + 2, $fn=20);
        // wire notches at the top edge next to the bar_back wire slot
        for (x = [bar_wire_slot[0] - 3, bar_wire_slot[0] + 3]) translate([x - 1, y0 + H - 1.5, btn_pcb_back_z - 1]) cube([2, 2, btn_pcb_t + 2]);
    }
}
// ---- Copper-tape switch plate (Glenn 2026-11-10, method of PCB Forge / Hackaday 2026-02-19) ----
// Same outline/holes as switch_plate. Back face (solder side, toward bar_back) carries 1.0 mm channels
// 0.3 deep, each closed off by 0.6 mm ridges 0.4 high. Stick copper tape over the back, press it into the
// channels with tape_mold, sand the ridges flat: the copper left in the channels is the circuit.
// Plate frame: x as the bar, y relative to the switch row (cap_y).
tp_w = 1.0; tp_ridge = 0.6; tp_depth = 0.3; tp_ridge_h = 0.4; tp_tape = 0.05;   // Glenn's copper tape: 0.05 mm (2026-11-10)
tp_bus = [["GND", 1.6], ["U", 3.2], ["S", 4.8], ["D", -2.6], ["M", -4.2]];    // [net, lower edge y]
tp_bus_x = [-83.0, 83.0];
tp_upper_gap = [-27.0, -23.4];          // middle bar screw (-25.2, +3.4): upper buses bridged by wire jumpers
tp_lines = ["SD", "D", "M", "U", "S", "DM", "UD", "UM", "SU"];   // per btn_xs: J12 lines of each button
tp_gnd_left = [true, false, false, false, false, false, false, false, false];  // home turned: GND on its left leg
function tp_rects() = concat(
    // buses (upper ones split at the middle screw)
    [for (b = tp_bus) for (seg = (b[1] > 0 ? [[tp_bus_x[0], tp_upper_gap[0]], [tp_upper_gap[1], tp_bus_x[1]]] : [tp_bus_x]))
        [seg[0], seg[1], b[1], b[1] + tp_w]],
    // leg pads
    [for (x = btn_xs) for (dx = [-1, 1]) [x + dx * sp_leg_pitch/2 - 1.3, x + dx * sp_leg_pitch/2 + 1.3, -1.0, 1.0]],
    // GND stubs from the GND leg up to the GND bus
    [for (i = [0 : len(btn_xs) - 1]) let(gx = btn_xs[i] + (tp_gnd_left[i] ? -1 : 1) * sp_leg_pitch/2) [gx - 0.5, gx + 0.5, 0.9, 1.7]],
    // single-line button on the inner lower bus (vol-, D): direct stub down
    [for (i = [0 : len(btn_xs) - 1]) if (tp_lines[i] == "D") let(nx = btn_xs[i] - sp_leg_pitch/2) [nx - 0.5, nx + 0.5, -1.7, -0.9]],
    // both diodes on the same side (prev D+M, voice S+U): node pad 2.5 mm longer, away from the switch,
    // so the two diode leads land 2.5 mm apart
    [for (i = [0 : len(btn_xs) - 1]) if (tp_lines[i] == "DM" || tp_lines[i] == "SU") let(nx = btn_xs[i] - sp_leg_pitch/2) [nx - 1.3 - 2.5, nx, -1.0, 1.0]]);
module tp_channels_2d() for (r = tp_rects()) translate([r[0], r[2]]) square([r[1] - r[0], r[3] - r[2]]);
module tp_outline_2d() translate([-bar_pcb_size[0]/2, bar_pcb_c[1] - cap_y - bar_pcb_size[1]/2]) square(bar_pcb_size);
module tp_holes_2d() {
    for (x = btn_xs) for (dx = [-1, 1]) translate([x + dx * sp_leg_pitch/2, 0]) square(sp_leg_slot, center=true);
    for (b = bar_screws) translate([b[0], b[1]]) circle(d=2.4, $fn=20);
}
module tape_plate() {
    T = btn_pcb_t;
    translate([0, cap_y, btn_pcb_back_z]) difference() {
        union() {
            linear_extrude(T) tp_outline_2d();
            translate([0, 0, -tp_ridge_h]) linear_extrude(tp_ridge_h + 0.01) intersection() {
                difference() { offset(delta=tp_ridge) tp_channels_2d(); tp_channels_2d(); }
                tp_outline_2d();
            }
        }
        translate([0, 0, -tp_ridge_h - 1]) linear_extrude(tp_ridge_h + 1 + tp_depth) tp_channels_2d();
        translate([0, 0, -2]) linear_extrude(T + 4) tp_holes_2d();
        // copper keep-out ring is automatic: no channel within 0.6 of the screw holes (checked)
    }
}
// Press mold: lay it on the taped plate (back face), tongues push the tape into the channels.
// Aligned with M2 screws / 2.2 mm pins through the three bar-screw holes.
tm_t = 3.0;
module tape_mold() {
    tongue_h = tp_ridge_h + tp_depth - tp_tape;      // from the ridge tops down to the tape in the channel floor
    translate([0, cap_y, btn_pcb_back_z - tp_ridge_h]) mirror([0, 0, 1]) difference() {
        union() {
            translate([0, 0, 0]) linear_extrude(tm_t) offset(delta=1.0) tp_outline_2d();
            translate([0, 0, -tongue_h]) linear_extrude(tongue_h + 0.01) offset(delta=-(0.15 + tp_tape)) tp_channels_2d();
        }
        for (b = bar_screws) translate([b[0], b[1], -2]) cylinder(d=2.4, h=tm_t + 4, $fn=20);
        // relief over the leg slots so the tape is not punched before the legs go in
    }
}
module ghost_bar_pcb() {
    color("Green", 0.9) translate([-bar_pcb_size[0]/2, bar_pcb_c[1] - bar_pcb_size[1]/2, btn_pcb_back_z]) cube([bar_pcb_size[0], bar_pcb_size[1], btn_pcb_t]);
    for (x = btn_xs)
        color("Black") translate([x - btn_body[0]/2, cap_y - btn_body[1]/2, btn_pcb_front_z]) cube([btn_body[0], btn_body[1], btn_total_h - btn_preload - 0.3]);
    color("MediumBlue") translate([bh1750_x - bh1750_board[0]/2, bh_y0, bh_z0]) cube([bh1750_board[0], bh1750_board[1], btn_pcb_t]);
    ghost_bh_conn();
}
module ghost_bh_conn() for (c = [[0.4, 4.65], [20.75, 25.0]])
    color("White") translate([bh1750_x - bh1750_board[0]/2 + c[0], bh_y0 + 8.89 - 3.0, bh_z1]) cube([c[1] - c[0], 6.0, 2.95]);

// ---- Tray mount (use_tray_mount), tray frame: z = 0 tray back, z = -spacer_length bezel face ----
brk_z0 = -spacer_length;             // bracket back face (on the bezel)
brk_z1 = brk_z0 + brk_t;             // bracket front face
brk_thin_z1 = brk_z0 + 3.0;          // bracket front face in the lug channels
cleat_y1 = brk_y[1] - cleat_d;       // top of the bracket cleat at the bracket face
lock_z = (brk_thin_z1 + (-carrier_t)) / 2;
lock_flange = [brk_y[0], brk_y[0] + 4.0];
lock_lug_y = [lock_flange[1] + 0.5, lock_flange[1] + 0.5 + lock_lug[1]];
module brk_cleat_2d() polygon([[cleat_y1 - cleat_h, brk_z1 - 0.01], [cleat_y1, brk_z1 - 0.01],
                               [cleat_y1 + cleat_d, brk_z1 + cleat_d], [cleat_y1 + cleat_d - cleat_h, brk_z1 + cleat_d]]);
car_cleat_yt = cleat_y1 + cleat_d + cleat_gap + cleat_h;
module car_cleat_2d() polygon([[cleat_y1 + 0.3 + cleat_gap, brk_z1 + 0.3], [cleat_y1 + cleat_d + cleat_gap, brk_z1 + cleat_d],
                               [cleat_y1 + cleat_d + cleat_gap, -carrier_t + 0.01], [car_cleat_yt, -carrier_t + 0.01], [car_cleat_yt, brk_z1 + 0.3]]);
// 2D [y, z] profile extruded along x from x0 to x1
module x_extrude(x0, x1) translate([x0, 0, 0]) rotate([90, 0, 90]) linear_extrude(x1 - x0) children();

module tray_bracket() {
    difference() {
        union() {
            translate([-brk_w/2, brk_y[0], brk_z0]) cube([brk_w, brk_y[1] - brk_y[0], brk_t]);
            for (cx = cleat_xs) x_extrude(cx[0], cx[1]) brk_cleat_2d();
            // lock flange along the bottom edge
            translate([-brk_w/2, lock_flange[0], brk_z0]) cube([brk_w, lock_flange[1] - lock_flange[0], -carrier_t - 0.5 - brk_z0]);
            // joiner locating rails (fix the joiner board with double-sided tape)
            if (use_joiner) for (sx = [-1, 1]) translate([joiner_c[0] + sx * (joiner_size[0]/2 + 0.4 + 0.75) - 0.75, joiner_c[1] - joiner_size[1]/2, brk_z1 - 0.01])
                cube([1.5, joiner_size[1], joiner_rim + 0.01]);
        }
        // M3 inserts from the back face, on the 4 front-plate slots
        for (tx = [-mount_spacing_w/2, mount_spacing_w/2]) for (ty = [-mount_spacing_h/2, mount_spacing_h/2])
            translate([tx, ty, brk_z0]) heatset_insert_bore(depth=4.5);
        // channels for the carrier lugs (they rise ~5 mm when the tray is unhooked)
        for (lx = lock_xs) translate([lx - lock_lug[0]/2 - 1.0, lock_flange[1] - 0.01, brk_thin_z1])
            cube([lock_lug[0] + 2.0, lock_lug_y[1] + cleat_d + 1.5 - lock_flange[1], brk_t]);
        // extension FFC into the case (on the front-plate slot)
        translate([front_ribbon_slot_offset_x, slot_offset_z, brk_z0 - 1])
            linear_extrude(brk_t + 2) hull() for (sx = [-1, 1]) translate([sx * (ribbon_slot_width/2 + 1.5 - 2.5), 0]) circle(d=5, $fn=24);
        // lock screws (M3 x 10 from below, head under the flange)
        for (lx = lock_xs) translate([lx, lock_flange[0] - 1, lock_z]) rotate([-90, 0, 0]) cylinder(d=3.4, h=lock_flange[1] - lock_flange[0] + 2, $fn=20);
    }
}
module tray_carrier() {
    hw = carrier_w/2;
    difference() {
        union() {
            // top bar (window for the panel FPC), bottom bar, two vertical bars on the tray inserts
            difference() {
                intersection() {
                    translate([-hw, carrier_top_y0, -carrier_t]) cube([carrier_w, outer_h/2 - carrier_top_y0, carrier_t]);
                    translate([0, 0, -carrier_t - 1]) linear_extrude(carrier_t + 2) tray_outline_2d();
                }
                translate([carrier_gap_x[0], carrier_top_y0 - 1, -carrier_t - 1]) cube([carrier_gap_x[1] - carrier_gap_x[0], outer_h, carrier_t + 2]);
            }
            translate([-hw, carrier_bot_y[0], -carrier_t]) cube([carrier_w, carrier_bot_y[1] - carrier_bot_y[0], carrier_t]);
            for (sx = [-1, 1]) translate([sx * mount_spacing_w/2 - carrier_bar/2, carrier_bot_y[0], -carrier_t])
                cube([carrier_bar, carrier_top_y0 - carrier_bot_y[0] + 0.01, carrier_t]);
            // cleats
            for (cx = cleat_xs) x_extrude(cx[0], cx[1]) car_cleat_2d();
            // lock lugs
            for (lx = lock_xs) translate([lx - lock_lug[0]/2, lock_lug_y[0], brk_thin_z1 + 0.5]) cube([lock_lug[0], lock_lug[1], -carrier_t - brk_thin_z1 - 0.5 + 0.01]);
        }
        // 4 screws into the tray's M3 inserts (M3 x 6, pan head on the carrier back)
        for (tx = [-mount_spacing_w/2, mount_spacing_w/2]) for (ty = [-mount_spacing_h/2, mount_spacing_h/2])
            translate([tx, ty, -carrier_t - 1]) cylinder(d=insert_clearance_hole, h=carrier_t + 2, $fn=20);
        // lock inserts from below
        for (lx = lock_xs) translate([lx, lock_lug_y[0], lock_z]) rotate([-90, 0, 0])
            heatset_insert_bore(depth=lock_insert[1], hole_d=lock_insert[0], guide_d=lock_insert[2]);
    }
}
// full carrier plate (source for the modular tray_hook parts)
module tray_carrier_full() {
    difference() {
        union() {
            intersection() {
                translate([-carrier_w/2, brk_y[0], -carrier_t]) cube([carrier_w, outer_h/2 - brk_y[0], carrier_t]);
                translate([0, 0, -carrier_t - 1]) linear_extrude(carrier_t + 2) tray_outline_2d();
            }
            for (cx = cleat_xs) x_extrude(cx[0], cx[1]) car_cleat_2d();
            for (lx = lock_xs) translate([lx - lock_lug[0]/2, lock_lug_y[0], brk_thin_z1 + 0.5]) cube([lock_lug[0], lock_lug[1], -carrier_t - brk_thin_z1 - 0.5 + 0.01]);
        }
        for (tx = [-mount_spacing_w/2, mount_spacing_w/2]) for (ty = [-mount_spacing_h/2, mount_spacing_h/2])
            translate([tx, ty, -carrier_t - 1]) cylinder(d=insert_clearance_hole, h=carrier_t + 2, $fn=20);
        for (lx = lock_xs) translate([lx, lock_lug_y[0], lock_z]) rotate([-90, 0, 0])
            heatset_insert_bore(depth=lock_insert[1], hole_d=lock_insert[0], guide_d=lock_insert[2]);
    }
}
// ---- Modular hooks (hooks_modular) ----
// front_hook: one per slot column (x = sx * 50), identical parts. Two M3 inserts on the existing slots,
// 45 deg cleat on top, lock flange with one M3 hole at the bottom, channel for the tray_hook lug.
module front_hook(sx) {
    cx = sx * mount_spacing_w/2; hw = hook_w/2;
    intersection() {
        tray_bracket();
        translate([cx - hw, brk_y[0] - 1, brk_z0 - 1]) cube([hook_w, brk_y[1] - brk_y[0] + 2, 30]);
    }
}
// tray_hook: on the two tray inserts of one column; cleat and lock lug (identical left/right apart from mirroring).
module tray_hook(sx) {
    cx = sx * mount_spacing_w/2; hw = hook_w/2;
    intersection() {
        tray_carrier_full();
        translate([cx - hw, brk_y[0] - 1, -30]) cube([hook_w, outer_h/2 - brk_y[0] + 2, 31]);
    }
}
module front_hooks() for (sx = [-1, 1]) front_hook(sx);
module tray_hooks() for (sx = [-1, 1]) tray_hook(sx);

module ghost_joiner() {
    color("SeaGreen") translate([joiner_c[0] - joiner_size[0]/2, joiner_c[1] - joiner_size[1]/2, brk_z1]) cube([joiner_size[0], joiner_size[1], 1.6]);
    color("Black") for (dy = [-1, 1]) translate([joiner_c[0] - 13, joiner_c[1] + dy * 3.5 - 2, brk_z1 + 1.6]) cube([26, 4, 2.5]);
}

// One cap; z = 0 at the back of the flange (prints flange down, icon up)
// Glenn 2026-11-10: caps 1 % narrower (X only) (printed caps were tight in the bar) and a notch in the
// flange wherever an insert boss or a BH1750 pin boss of the bar comes close.
cap_scale = 0.99;
cap_notch_clear = 0.4;
// obstacles behind the skin, in the bar frame: [x, y, radius]
function cap_obstacles() = concat(
    [for (b = bar_screws) [b[0], cap_y + b[1], bar_boss_d/2]],
    [for (hx = [2.54, 22.86]) [bh1750_x - bh1750_board[0]/2 + hx, bh_y0 + 15.24, 4.5/2]]);
module button_cap(icon, bx=undef) {
    body_l = bar_skin + cap_protrude;
    difference() {
        scale([cap_scale, 1, 1]) union() {   // width only (Glenn: height was right)
            linear_extrude(cap_flange_t) hull() {
                pill_2d(cap_w, cap_h);
                square([cap_w - 1.2, cap_h + 2 * cap_flange], center=true);
            }
            translate([0, 0, cap_flange_t - 0.01]) hull() {
                linear_extrude(body_l - 0.4) pill_2d(cap_w, cap_h);
                linear_extrude(body_l) offset(delta=-0.4) pill_2d(cap_w, cap_h);
            }
            translate([0, 0, cap_flange_t + body_l - 0.02]) linear_extrude(cap_icon_h + 0.02) icon_2d(icon);
        }
        // notches in the flange next to the bosses (only the flange sits behind the skin)
        if (bx != undef) for (o = cap_obstacles())
            if (abs(o[0] - bx) < cap_w/2 + cap_flange + o[2] + 1 && abs(o[1] - cap_y) < cap_h/2 + cap_flange + o[2] + 1)
                translate([o[0] - bx, o[1] - cap_y, -1]) cylinder(r=o[2] + cap_notch_clear, h=1 + cap_flange_t + 1.0, $fn=32);   // flange + 1 mm of the body (stays inside the skin, room for the press travel)
    }
}
module button_caps_placed() {
    for (i = [0 : len(btn_xs) - 1]) translate([btn_xs[i], cap_y, cap_flange_back_z]) button_cap(btn_icons[i], btn_xs[i]);
}
module button_caps_print() {
    for (i = [0 : len(btn_xs) - 1]) translate([(i % 3) * 15, floor(i / 3) * 12, 0]) button_cap(btn_icons[i], btn_xs[i]);
}

// Ghost boards in the bar (assembly preview)
module ghost_tray_boards() {
    color("Tan", 0.9) translate([-outer_w/2 + bar_wall - 0.6, tb_y0 + bar_wall - 0.6, btn_pcb_back_z]) cube([outer_w - 2 * bar_wall + 1.2, bar_h - bar_wall + 0.5, btn_pcb_t]);
    for (x = btn_xs)
        color("Black") translate([x - btn_body[0]/2, cap_y - btn_body[1]/2, btn_pcb_front_z]) cube([btn_body[0], btn_body[1], btn_total_h - btn_preload - 0.3]);
    color("MediumBlue") translate([bh1750_x - bh1750_board[0]/2, bh_y0, bh_z0]) cube([bh1750_board[0], bh1750_board[1], btn_pcb_t]);
}

echo(str("Front: ", outer_w, " x ", outer_h + bar_h, " mm (tray ", outer_h, " + bar ", bar_h, "); caps ", cap_protrude,
         " mm proud; strip ", outer_w - 2 * bar_wall + 1.2, " x ", bar_h - bar_wall + 0.5, " mm, front at z=", btn_pcb_front_z));


// --- 2. DIN FRONT PLATE (unchanged apart from comments) ---
module din_front_plate() {
    union() {
        difference() {
            union() {
                translate([0, -bezel_depth, (chassis_h - bezel_height)/2])
                hull() {
                    translate([-(bezel_width/2) + bezel_corner_radius, 0, bezel_corner_radius])
                        rotate([-90,0,0]) cylinder(r=bezel_corner_radius, h=bezel_depth, $fn=40);
                    translate([(bezel_width/2) - bezel_corner_radius, 0, bezel_corner_radius])
                        rotate([-90,0,0]) cylinder(r=bezel_corner_radius, h=bezel_depth, $fn=40);
                    translate([-(bezel_width/2) + bezel_corner_radius, 0, bezel_height - bezel_corner_radius])
                        rotate([-90,0,0]) cylinder(r=bezel_corner_radius, h=bezel_depth, $fn=40);
                    translate([(bezel_width/2) - bezel_corner_radius, 0, bezel_height - bezel_corner_radius])
                        rotate([-90,0,0]) cylinder(r=bezel_corner_radius, h=bezel_depth, $fn=40);
                }
                translate([-(chassis_w/2), 0, 0])
                    cube([chassis_w, front_wall_thickness, chassis_h]);
            }

            slot_len = vertical_travel;
            for(tx = [-mount_spacing_w/2, mount_spacing_w/2]) {
                for(tz_center = [chassis_h/2 - mount_spacing_h/2, chassis_h/2 + mount_spacing_h/2]) {
                    translate([tx, -bezel_depth-1, tz_center])
                    rotate([-90,0,0])
                    hull() {
                        translate([0, slot_len/2, 0]) cylinder(h=bezel_depth + front_wall_thickness + 2, d=mount_screw_diam, $fn=20);
                        translate([0, -slot_len/2, 0]) cylinder(h=bezel_depth + front_wall_thickness + 2, d=mount_screw_diam, $fn=20);
                    }
                }
            }

            if (add_front_slot) {
                y_front_outer = -bezel_depth - 1;
                y_front_inner = -bezel_depth + slot_bevel_size;
                y_back_inner  = front_wall_thickness - slot_bevel_size;
                y_back_outer  = front_wall_thickness + 1;

                w_small = ribbon_slot_width;
                h_small = ribbon_slot_thickness + 1.0;
                r_small = 1.0;
                w_big = w_small + (slot_bevel_size*2);
                h_big = h_small + (slot_bevel_size*2);
                r_big = r_small + slot_bevel_size;

                translate([front_ribbon_slot_offset_x, 0, (chassis_h/2) + slot_offset_z]) {
                    hull() {
                        translate([0, y_front_outer, 0]) rotate([90,0,0]) rounded_rect_slice(w_big, h_big, r_big);
                        translate([0, y_front_inner, 0]) rotate([90,0,0]) rounded_rect_slice(w_small, h_small, r_small);
                    }
                    hull() {
                        translate([0, y_front_inner, 0]) rotate([90,0,0]) rounded_rect_slice(w_small, h_small, r_small);
                        translate([0, y_back_inner, 0])  rotate([90,0,0]) rounded_rect_slice(w_small, h_small, r_small);
                    }
                    hull() {
                        translate([0, y_back_inner, 0])  rotate([90,0,0]) rounded_rect_slice(w_small, h_small, r_small);
                        translate([0, y_back_outer, 0])  rotate([90,0,0]) rounded_rect_slice(w_big, h_big, r_big);
                    }
                }
            }

            // DIN Removal Key Slots, aligned with the clip pockets in the side panels
            if (add_key_slots) {
                key_x_inset = (key_slot_width/2) + 1.5;
                for(tx = [-(chassis_w/2) + key_x_inset, (chassis_w/2) - key_x_inset]) {
                    translate([tx - key_slot_width/2, -bezel_depth - 1, clip_height_z - key_slot_height/2])
                        cube([key_slot_width, bezel_depth + front_wall_thickness + 2, key_slot_height]);
                }
            }

            hole_inset_z = front_mount_inset_z;
            hole_inset_x = side_wall_thickness + (ledge_width/2);
            for(tx = [-(chassis_w/2) + hole_inset_x, (chassis_w/2) - hole_inset_x]) {
                for(tz = [hole_inset_z, chassis_h - hole_inset_z]) {
                    translate([tx, -bezel_depth-1, tz])
                        rotate([-90, 0, 0])
                        cylinder(h=bezel_depth + front_wall_thickness + 2, d=assem_screw_diam, $fn=20);
                    translate([tx, -bezel_depth-0.01, tz])
                        rotate([-90, 0, 0])
                        cylinder(h=assem_screw_head_height + 0.02, d=assem_screw_head_diam, $fn=30);
                }
            }

            // Extra screws into the top / bottom panel end bosses
            for (fbz = concat([for (b = front_top_bosses) [b[0], panel_boss_z(b, true)]],
                              [for (b = front_bottom_bosses) [b[0], panel_boss_z(b, false)]])) {
                translate([fbz[0], -bezel_depth-1, fbz[1]])
                    rotate([-90, 0, 0])
                    cylinder(h=bezel_depth + front_wall_thickness + 2, d=assem_screw_diam, $fn=20);
                translate([fbz[0], -bezel_depth-0.01, fbz[1]])
                    rotate([-90, 0, 0])
                    cylinder(h=assem_screw_head_height + 0.02, d=assem_screw_head_diam, $fn=30);
            }

            if (add_uart_pogo) {
                translate([pogo_offset_x, 0, (chassis_h/2) + pogo_offset_z]) {
                    translate([0, -bezel_depth - 1, 0])
                        rotate([-90,0,0])
                        hull() {
                            translate([-pogo_front_hole_w/2 + pogo_front_hole_h/2, 0, 0]) cylinder(d=pogo_front_hole_h, h=20, $fn=30);
                            translate([ pogo_front_hole_w/2 - pogo_front_hole_h/2, 0, 0]) cylinder(d=pogo_front_hole_h, h=20, $fn=30);
                        }
                    recess_y = -bezel_depth + pogo_face_thickness;
                    translate([0, recess_y, 0])
                        rotate([-90,0,0])
                        hull() {
                            translate([-pogo_recess_w/2 + pogo_recess_h/2, 0, 0]) cylinder(d=pogo_recess_h, h=20, $fn=30);
                            translate([ pogo_recess_w/2 - pogo_recess_h/2, 0, 0]) cylinder(d=pogo_recess_h, h=20, $fn=30);
                        }
                    translate([0, -bezel_depth + 0.7, pogo_front_hole_h/2 + 2.0])
                        rotate([90, 0, 0])
                        linear_extrude(0.8)
                        text("5V  TX  RX  GND", size=2.0, halign="center", valign="bottom");
                }
            }
        }

        if (add_uart_pogo) {
            translate([pogo_offset_x, 0, (chassis_h/2) + pogo_offset_z]) {
                recess_y = -bezel_depth + pogo_face_thickness;
                for(dx = [-pogo_peg_spacing/2, pogo_peg_spacing/2]) {
                    translate([dx, recess_y - 0.1, 0])
                        rotate([-90,0,0])
                        cylinder(d=pogo_peg_diam, h=pogo_peg_height + 0.1, $fn=20);
                }
            }
        }
    }
}


// --- 2b. MODULE SPACER SLEEVES (between main board and plug-in modules) ---
module module_spacer(id, od) {
    difference() {
        cylinder(d=od, h=module_stack_height, $fn=40);
        translate([0, 0, -1]) cylinder(d=id, h=module_stack_height + 2, $fn=24);
        // small chamfers so the ends sit flat on the boards
        for (z = [0, module_stack_height]) translate([0, 0, z]) cylinder(d1=id + 0.8, d2=id - 0.01, h=0.4, center=true, $fn=24);
    }
}
module module_spacers_print() {
    for (t = [0 : len(module_spacer_types) - 1]) for (i = [0 : module_spacer_types[t][3] - 1])
        translate([i * 8, t * 8, 0]) module_spacer(module_spacer_types[t][1], module_spacer_types[t][2]);
}

// --- 3. FLANGED STANDOFF (Washer included, unchanged) ---
module standoff_spacer() {
    washer_diam = 12;
    washer_thick = 2;
    difference() {
        union() {
            cylinder(h=spacer_length, d=8, $fn=20);
            cylinder(h=washer_thick, d=washer_diam, $fn=20);
        }
        translate([0,0,-1]) cylinder(h=spacer_length+2, d=mount_screw_diam + 0.2, $fn=20);
    }
}


// --- 4. BACKPLATE (IO PLATE) ---
// Local frame: X centred like the assembly, Y = 0 is the inner face (touching the side
// panels), Y = back_plate_thickness the outside face, Z = 0 at the bottom.
module back_plate() {

    module round_hole(x, z, d, flat=false) {
        translate([x, -1, z])
            rotate([-90, 0, 0])
            linear_extrude(back_plate_thickness + 2)
            difference() {
                circle(d=d, $fn=40);
                // SMA bulkhead anti-rotation flat (5.8 mm across flats on a 6.35 mm thread)
                if (flat) translate([-d, (5.8 + (d - 6.35)) / 2]) square([2*d, d]);
            }
    }

    // Engraved on the outside face, mirrored so it reads correctly from behind
    module io_label(x, z, label) {
        translate([x, back_plate_thickness + 0.01, z])
            rotate([90, 0, 0])
            mirror([1, 0, 0])
            linear_extrude(io_text_depth + 0.01)
            text(label, size=io_text_size, font="Liberation Sans:style=Bold", halign="center", valign="center");
    }

    usb_xs = [for (my = usb_a_centres_my) usb2body([0, my])[0]];
    pocket_x0 = min(usb_xs) - usb_hole_w/2 - usb_pocket_margin;
    pocket_x1 = max(usb_xs) + usb_hole_w/2 + usb_pocket_margin;
    pocket_h = usb_hole_h + 2 * usb_pocket_margin + 1;

    // Screen-ribbon wrap relief, behind J14
    j14_xc = (j14_x_lo + j14_x_hi)/2;

    difference() {
        union() {
            translate([-(chassis_w/2), 0, 0])
                cube([chassis_w, back_plate_thickness, chassis_h]);
            // tongue over the M2X rear edge (holds the VIM3 stack down at the back)
            translate([back_tongue_xs[0], -back_tongue_depth, m2x_bottom_z + m2x_pcb_t + ret_air])
                cube([back_tongue_xs[1] - back_tongue_xs[0], back_tongue_depth + 0.01, 2.0]);
        }

        // Side mounting holes (countersunk, as before)
        hole_inset_x = side_wall_thickness + (ledge_width/2);
        cs_depth = (assem_screw_head_diam - assem_screw_diam) / 2;
        for(tx = [-(chassis_w/2) + hole_inset_x, (chassis_w/2) - hole_inset_x]) {
            for(tz = [for (i = [0 : len(rear_mount_z) - 1]) if (!(tx > 0 && right_drop_low_rear && i == 0)) rear_mount_z[i]]) {
                translate([tx, -1, tz])
                    rotate([-90, 0, 0])
                    cylinder(h=back_plate_thickness + 2, d=assem_screw_diam, $fn=20);
                translate([tx, back_plate_thickness - cs_depth + 0.01, tz])
                    rotate([-90, 0, 0])
                    cylinder(h=cs_depth + 0.02, d1=assem_screw_diam, d2=assem_screw_head_diam, $fn=20);
            }
        }

        // Extra screws into the top / bottom panel end bosses (countersunk, outside)
        for (rbz = concat([for (b = rear_top_bosses) [b[0], panel_boss_z(b, true)]],
                          [for (b = rear_bottom_bosses) [b[0], panel_boss_z(b, false)]])) {
            translate([rbz[0], -1, rbz[1]])
                rotate([-90, 0, 0])
                cylinder(h=back_plate_thickness + 2, d=assem_screw_diam, $fn=20);
            translate([rbz[0], back_plate_thickness - (assem_screw_head_diam - assem_screw_diam)/2 + 0.01, rbz[1]])
                rotate([-90, 0, 0])
                cylinder(h=(assem_screw_head_diam - assem_screw_diam)/2 + 0.02, d1=assem_screw_diam, d2=assem_screw_head_diam, $fn=20);
        }

        // --- PANEL JACKS ---
        round_hole(gps_x, gps_zz, gps_hole_diam, gps_flat);
        io_label(gps_x, gps_zz - 8, "GPS");
        round_hole(mic_x, io_row_z, mic_hole_diam);
        io_label(mic_x, io_row_z - 8, "MIC");
        round_hole(rca_x, io_row_z, rca_hole_diam);
        io_label(rca_x, io_row_z - 9.5, "CAM");

        // --- USB-A (aligned to the USB module sockets) ---
        for (i = [0 : len(usb_xs) - 1]) {
            translate([usb_xs[i], -1, usb_a_z])
                rotate([-90, 0, 0])
                linear_extrude(back_plate_thickness + 2)
                rounded_rect_2d(usb_hole_w, usb_hole_h, usb_hole_r);
            io_label(usb_xs[i], usb_a_z + pocket_h/2 + 3, usb_a_labels[i]);
        }
        // Shared outside pocket: leaves only usb_pocket_web of plate at the sockets
        translate([pocket_x0, usb_pocket_web, usb_a_z - pocket_h/2])
            cube([pocket_x1 - pocket_x0, back_plate_thickness, pocket_h]);

        // --- CABLE SLIT (ISO pigtails), open to the top edge ---
        slit_bottom_z = chassis_h - wire_slit_h;
        translate([wire_slit_x - wire_slit_w/2, -1, slit_bottom_z])
            cube([wire_slit_w, back_plate_thickness + 2, wire_slit_h + 2]);
        translate([wire_slit_x, -1, slit_bottom_z])
            rotate([-90, 0, 0])
            cylinder(h=back_plate_thickness + 2, d=wire_slit_w, $fn=30);

        // --- INNER RELIEF for the screen ribbon wrapping round the board edge ---
        translate([j14_xc - ffc_relief_w/2, -0.01, floor_z])
            cube([ffc_relief_w, ffc_relief_depth + 0.01, ffc_relief_h]);
    }
}


// --- 5. SIDE PANELS ---
// Insert bosses (local side-panel frame: x 0 = outer face, inward +x)
module side_insert_bosses(is_right=false) {
    hole_x = side_total_thickness - (ledge_width/2);
    vhole_x = panel_screw_inset;
    h_v = side_insert_hole_depth + side_boss_extra;
    // vertical pad: round boss around the insert axis, hulled to the wall
    module vpad(ty, z0) {
        hull() {
            translate([0, ty - side_boss_d/2, z0]) cube([0.01, side_boss_d, h_v]);
            translate([vhole_x, ty, z0]) cylinder(d=side_boss_d, h=h_v, $fn=40);
        }
    }
    // horizontal pad along Y
    module hpad(y0, len, tz) {
        hull() {
            translate([0, y0, tz - side_boss_d/2]) cube([0.01, len, side_boss_d]);
            translate([hole_x, y0, tz]) rotate([-90, 0, 0]) cylinder(d=side_boss_d, h=len, $fn=40);
        }
    }
    for (ty = side_screw_ys()) {
        vpad(ty, lid_thickness);
        vpad(ty, chassis_h - lid_thickness - h_v);
    }
    for (tz = [front_mount_inset_z, chassis_h - front_mount_inset_z])
        hpad(0, front_boss_length, tz);
    for (i = [0 : len(rear_mount_z) - 1])
        if (!(is_right && right_drop_low_rear && i == 0))
            hpad(enclosure_depth - rear_boss_length, rear_boss_length, rear_mount_z[i]);
}

module side_panel_gen(is_right=false) {
    mirror_x = is_right ? 1 : 0;
    mirror([mirror_x, 0, 0]) {
        difference() {
            union() {
                // wall + ledge between the top and bottom panels (the panels cover them)
                translate([0, 0, lid_thickness])
                    cube([side_total_thickness, enclosure_depth, chassis_h - (lid_thickness * 2)]);
                side_insert_bosses(is_right);
            }
            // left side: lower insert pads are cut back where the M2X edge passes
            if (!is_right)
                translate([stack_x0 - 0.3 + chassis_w/2, vim3_y0 - 1, lid_thickness - 0.01])
                    cube([20, stack_y1 - vim3_y0 + 2, vim3_top_z + 0.5 - lid_thickness]);
            if (add_ventilation) {
                for (i = [45 : 10 : enclosure_depth - 15]) {
                    translate([-1, i, 12])
                        cube([side_total_thickness+2, 4, chassis_h - 24]);
                }
            }

            if (add_din_clip_pockets) {
                clip_pocket_depth = clip_thickness + clip_pocket_clearance;
                clip_pocket_w = clip_width + (clip_pocket_clearance * 2);
                translate([-1, 0, clip_height_z - clip_pocket_w/2])
                    cube([clip_pocket_depth + 1, clip_length, clip_pocket_w]);
            }

            hole_x = side_total_thickness - (ledge_width/2);
            hole_inset_z = front_mount_inset_z;

            for (ty = side_screw_ys()) {
                translate([panel_screw_inset, ty, lid_thickness])
                    heatset_insert_bore(depth=side_insert_hole_depth);
                translate([panel_screw_inset, ty, chassis_h - lid_thickness])
                    rotate([180, 0, 0])
                    heatset_insert_bore(depth=side_insert_hole_depth);
            }
            for(tz = [hole_inset_z, chassis_h - hole_inset_z])
                translate([hole_x, 0, tz])
                    rotate([-90, 0, 0])
                    heatset_insert_bore(depth=side_insert_hole_depth);
            for(i = [0 : len(rear_mount_z) - 1]) if (!(is_right && right_drop_low_rear && i == 0))
                translate([hole_x, enclosure_depth, rear_mount_z[i]])
                    rotate([90, 0, 0])
                    heatset_insert_bore(depth=side_insert_hole_depth);
        }
    }
}


// --- Shared top/bottom panel parts (panel local frame: X 0..inner_plate_w as before,
// the plate itself now extends (chassis_w - inner_plate_w)/2 further on each side) ---
panel_x0 = -(chassis_w - inner_plate_w) / 2;

module panel_plate() {
    translate([panel_x0, 0, 0]) cube([chassis_w, enclosure_depth, lid_thickness]);
}

// is_top: lips/bosses hang down from the top panel (built in the panel frame, z = 0 is the
// outer face for the bottom panel and the inner face for the top panel)
module panel_lips_and_bosses(is_top) {
    cx = inner_plate_w/2;
    zin = is_top ? 0 : lid_thickness;          // inner face
    dir = is_top ? -1 : 1;                     // towards the inside
    lip_x = chassis_w/2 - side_total_thickness;
    // locating lips along the long edges, interrupted at the side-panel insert bosses
    gaps = [for (ty = side_screw_ys()) [ty - side_boss_d/2 - 0.5, ty + side_boss_d/2 + 0.5]];
    starts = concat([0], [for (g = gaps) g[1]]);
    ends = concat([for (g = gaps) g[0]], [enclosure_depth]);
    for (sx = [-1, 1], k = [0 : len(starts) - 1])
        translate([cx + (sx > 0 ? lip_x - panel_lip_w : -lip_x), starts[k], is_top ? -panel_lip_h : zin])
            cube([panel_lip_w, ends[k] - starts[k], panel_lip_h]);
    // end bosses for the front / back plate screws
    fb = is_top ? front_top_bosses : front_bottom_bosses;
    rb = is_top ? rear_top_bosses : rear_bottom_bosses;
    for (b = fb) translate([cx + b[0] - panel_boss_w/2, 0, is_top ? -b[1] : zin]) cube([panel_boss_w, panel_boss_depth, b[1]]);
    for (b = rb) translate([cx + b[0] - panel_boss_w/2, enclosure_depth - panel_boss_depth, is_top ? -b[1] : zin]) cube([panel_boss_w, panel_boss_depth, b[1]]);
}

module panel_boss_bores(is_top) {
    cx = inner_plate_w/2;
    fb = is_top ? front_top_bosses : front_bottom_bosses;
    rb = is_top ? rear_top_bosses : rear_bottom_bosses;
    for (b = fb) translate([cx + b[0], 0, is_top ? -b[1]/2 : lid_thickness + b[1]/2]) rotate([-90, 0, 0]) heatset_insert_bore(depth=side_insert_hole_depth);
    for (b = rb) translate([cx + b[0], enclosure_depth, is_top ? -b[1]/2 : lid_thickness + b[1]/2]) rotate([90, 0, 0]) heatset_insert_bore(depth=side_insert_hole_depth);
}

module panel_side_screw_holes(from_top) {
    cx = inner_plate_w/2;
    for (sx = [-1, 1], ty = side_screw_ys())
        translate([cx + sx * (chassis_w/2 - panel_screw_inset), ty, 0])
            countersunk_hole(lid_thickness, assem_screw_diam, assem_screw_head_diam, 90, from_top=from_top);
}

// Assembly-Z of each panel boss insert axis (for the front / back plate holes)
function panel_boss_z(b, is_top) = is_top ? chassis_h - lid_thickness - b[1]/2 : lid_thickness + b[1]/2;


// --- 6. BOTTOM PANEL (carries the main board and the VIM3 stack) ---
// Local frame: X 0..inner_plate_w (body X + inner_plate_w/2), Y 0..enclosure_depth.
module bottom_panel() {
    cx = inner_plate_w/2;

    mb_posts = [for (h = mb_mounts) mb2body([h[0], h[1]])];

    difference() {
        union() {
            panel_plate();
            panel_lips_and_bosses(false);
            // Main board: one post per hole (M3, M2.5, M2), with a fillet ring at the foot
            for (i = [0 : len(mb_mounts) - 1]) {
                p = mb_posts[i];
                od = mb_mounts[i][5];
                translate([cx + p[0], p[1], lid_thickness]) {
                    standoff_post(mb_standoff_height, od);
                    cylinder(h=1.5, d1=od + 2, d2=od, $fn=30);
                }
            }
            // VIM3 / M2X: pocket with support ledges and retainer clips
            translate([cx, 0, 0]) vim3_pocket();
        }

        // Assembly screw holes into the side panels, and the front / back plate inserts
        panel_side_screw_holes(false);
        panel_boss_bores(false);

        // Heat-set insert bores
        for (i = [0 : len(mb_mounts) - 1]) {
            p = mb_posts[i];
            m = mb_mounts[i];
            translate([cx + p[0], p[1], lid_thickness]) {
                standoff_insert_cut(mb_standoff_height, m[3], m[2], m[4]);
                // screw relief below the insert
                translate([0, 0, mb_screw_relief_floor - lid_thickness])
                    cylinder(h=mb_standoff_height - m[3] + lid_thickness - mb_screw_relief_floor + 0.1, d=m[6], $fn=24);
            }
        }

        if (use_front_retainer) translate([cx, 0, 0]) ret_insert_cuts();

        // Vent slots under the VIM3 stack (air in at the bottom, out through the lid)
        if (add_lid_vents) {
            for (yy = [stack_y0 + 12 : lid_vent_pitch : stack_y1 - 12])
                translate([cx + stack_x0 + 8, yy, -1])
                    hull() {
                        cylinder(d=lid_vent_w, h=lid_thickness + 2, $fn=16);
                        translate([vim3_w - 16, 0, 0]) cylinder(d=lid_vent_w, h=lid_thickness + 2, $fn=16);
                    }
        }
    }
}



// --- VIM3 + New M2X pocket (body coordinates, z = 0 at the underside of the bottom panel) ---
// The M2X rests on two 1.2 mm ledges along its long edges (the SSD and M.2 sockets hang
// below it, so nothing under the middle). Low walls locate it; two snap clips hold the
// stack down: one over the M2X front edge (M.2 end), one over the VIM3 rear edge.
m2x_x0 = vim3_xr - 56.01;    // M2X edge at the header side
m2x_x1 = vim3_xr - 0.01;     // M2X edge at the port side
module vim3_pocket() {
    c = pocket_clear;
    ledge = 1.2;               // M2X edge strip free of the SSD / sockets (SSD starts 2 mm in)
    zt = m2x_bottom_z + m2x_pcb_t + 0.5;   // stays under the VIM3 HDMI socket (it reaches 1.75 below the VIM3 PCB)
    // support ledges under both long edges of the M2X
    // header-side ledge full length; port-side ledge with a gap where the RJ45 hangs
    // 3.7 mm below the VIM3 PCB through the M2X notch (VIM3 STEP: lx 47.1-64.5, 1.4 below the M2X)
    translate([m2x_x0 - c, stack_y0, floor_z - 0.01]) cube([ledge + c, m2x_l - 0.5, m2x_support_h + 0.01]);
    for (seg = [[0, rj45_gap[0]], [rj45_gap[1], m2x_l - 0.5 + m2x_front_lx]])
        translate([m2x_x1 - ledge, vim3_y0 + seg[0], floor_z - 0.01])
            cube([ledge + c, seg[1] - seg[0], m2x_support_h + 0.01]);
    // no port-side wall: RJ45 (1.7 out, 3.7 down), HDMI (0.65 out, 1.3 down) and the
    // USB-A shells (2.5 out, 0.95 down) hang over that edge (Glenn, 2026-11-06)
    // front wall: kept 1 mm under the USB-A shells, stops 18 mm short of the port edge
    translate([m2x_x0 + 6, vim3_y0 - c - pocket_wall, floor_z - 0.01]) cube([m2x_w - 6 - 18, pocket_wall, zt - 1.0 - floor_z]);
    // retainer posts (M3 inserts are cut in bottom_panel)
    if (use_front_retainer)
    for (p = ret_posts()) translate([p[0], p[1], floor_z - 0.01]) {
        cylinder(d=ret_post_d, h=p[2] - floor_z + 0.01, $fn=32);
        cylinder(d1=ret_post_d + 2, d2=ret_post_d, h=1.5, $fn=32);
    }
}
// [X, Y, top z] of the four retainer posts (body coordinates)
function ret_front_y() = vim3_y0 - pocket_clear - pocket_wall - ret_post_d/2 - 0.5;
function ret_posts() = [for (x = ret_front_xs) [x, ret_front_y(), vim3_top_z + ret_air]];
module ret_insert_cuts() for (p = ret_posts()) translate([p[0], p[1], p[2]])
    rotate([180, 0, 0]) heatset_insert_bore(depth=ret_insert[1], hole_d=ret_insert[0], guide_d=ret_insert[2]);
// one retainer strip, in place (body coordinates): flat bar on the two posts, reaching
// ret_overlap over the board edge; edge_y = board edge, dir = +1 if the board is at +Y
module retainer_strip(xs, post_y, top_z, edge_y, dir) {
    y0 = min(post_y - ret_post_d/2 - 0.5, edge_y + dir * ret_overlap);
    y1 = max(post_y + ret_post_d/2 + 0.5, edge_y + dir * ret_overlap);
    difference() {
        translate([xs[0] - ret_post_d/2 - 1, y0, top_z]) cube([xs[1] - xs[0] + ret_post_d + 2, y1 - y0, ret_t]);
        for (x = xs) translate([x, post_y, top_z - 1]) {
            cylinder(d=ret_screw_d, h=ret_t + 2, $fn=24);
            translate([0, 0, ret_t + 1 - 1.8]) cylinder(d=6.2, h=2, $fn=24);   // head recess
        }
    }
}
module retainers_placed() {
    retainer_strip(ret_front_xs, ret_front_y(), vim3_top_z + ret_air, vim3_y0, 1);
}
module retainers_print() {
    translate([80, -ret_front_y(), -(vim3_top_z + ret_air)])
        retainer_strip(ret_front_xs, ret_front_y(), vim3_top_z + ret_air, vim3_y0, 1);
}

// --- 7. TOP PANEL ---
module top_panel() {
    cx = inner_plate_w/2;
    difference() {
        union() {
            panel_plate();
            panel_lips_and_bosses(true);
            // stiffening ribs on the inside
            for (x = top_rib_xs)
                translate([cx + x - panel_rib_w/2, panel_boss_depth + 1, -panel_rib_h]) cube([panel_rib_w, enclosure_depth - 2 * panel_boss_depth - 2, panel_rib_h + 0.01]);
            for (y = [enclosure_depth/3, 2 * enclosure_depth/3])
                translate([cx + min(top_rib_xs), y - panel_rib_w/2, -panel_rib_h]) cube([max(top_rib_xs) - min(top_rib_xs), panel_rib_w, panel_rib_h + 0.01]);
        }
        panel_side_screw_holes(true);
        panel_boss_bores(true);
        // Vent slots over the VIM3 (heatsink)
        if (add_lid_vents) {
            for (yy = [stack_y0 + 8 : lid_vent_pitch : stack_y1 - 8])
                translate([cx + stack_x0 + 6, yy, -1])
                    hull() {
                        cylinder(d=lid_vent_w, h=lid_thickness + 2, $fn=16);
                        translate([vim3_w - 12, 0, 0]) cylinder(d=lid_vent_w, h=lid_thickness + 2, $fn=16);
                    }
        }
    }
}


// --- 8. GHOST MODELS (assembly preview only, not printed) ---
module ghost_boards() {
    // Main board
    color("ForestGreen", 0.85)
        translate([mb_x0, mb_y0, mb_bottom_z])
        linear_extrude(mb_thickness)
        translate([mb_size/2, mb_size/2]) rounded_rect_2d(mb_size, mb_size, mb_corner_r);

    // Main-board parts that matter for the case (KiCad courtyard boxes, rotated):
    // [bx0, bx1, by0, by1, height, colour]
    mb_parts = [
        [70.19, 85.19, 0.54, 12.00, 6.5, "Silver"],    // J13 HDMI (mouth at y = 0)
        [94.75, 99.66, 8.64, 32.14, 2.5, "Wheat"],     // J14 display FPC (ribbon leaves at x = 100)
        [8.04, 67.50, 0.55, 10.45, 9.0, "DimGray"],    // J2 2x20 IDC to VIM3
        [1.04, 9.45, 11.04, 17.79, 7.0, "White"],      // J18 VIM3 VIN
        [11.04, 17.95, 11.45, 16.95, 6.0, "White"],    // J5 power key
        [1.04, 18.20, 81.67, 91.45, 12.0, "Ivory"],    // J1 ISO A Micro-Fit
        [54.65, 64.42, 85.30, 99.45, 12.0, "Ivory"],   // J8 ISO C1 Micro-Fit
        [65.24, 78.14, 93.95, 99.45, 6.0, "White"],    // J12 buttons
        [78.84, 89.75, 93.95, 99.45, 6.0, "White"],    // J7 light sensor
        [18.84, 36.62, 81.25, 91.16, 13.0, "Yellow"]   // F4 fuse holder
    ];
    for (p = mb_parts) {
        a = mb2body([p[0], p[2]]);
        b = mb2body([p[1], p[3]]);
        color(p[5], 0.9)
            translate([min(a[0], b[0]), min(a[1], b[1]), mb_top_z])
            cube([abs(b[0] - a[0]), abs(b[1] - a[1]), p[4]]);
    }

    // Stacked modules: GNSS (x0-26.5, y19-50.5), audio (x27-63.5, y13-54), USB (x64-100, y32.5-87.5)
    mods = [[0, 26.5, 19, 50.5, "RoyalBlue"], [27, 63.5, 13, 54, "Purple"],
            [usbmod_origin[0], usbmod_origin[0] + usbmod_size[0], usbmod_origin[1], usbmod_origin[1] + usbmod_size[1], "Teal"]];
    for (m = mods) {
        a = mb2body([m[0], m[2]]);
        b = mb2body([m[1], m[3]]);
        color(m[4], 0.8)
            translate([min(a[0], b[0]), min(a[1], b[1]), module_bottom_z])
            cube([abs(b[0] - a[0]), abs(b[1] - a[1]), module_thickness]);
    }
    // USB-A shells, mouth at the module edge (KiCad x = 100)
    for (my = usb_a_centres_my) {
        c = usb2body([36.01, my]);
        color("LightSteelBlue")
            translate([c[0] - usb_a_shell_w/2, c[1] - 14.0, usb_a_z - usb_a_shell_h/2])
            cube([usb_a_shell_w, 14.0, usb_a_shell_h]);
    }

    // VIM3 + New M2X stack (real outlines; parts as boxes)
    color("SteelBlue", 0.8) translate([m2x_x0, stack_y0, m2x_bottom_z]) cube([m2x_w, m2x_l, m2x_pcb_t]);
    color("SteelBlue", 0.35) translate([m2x_x0 + 2.0, stack_y0 + 1.5, m2x_bottom_z - m2x_under]) cube([m2x_w - 4.0, m2x_l - 1.5, m2x_under]);   // SSD + M.2 sockets underneath
    color("Navy", 0.85) translate([stack_x0, vim3_y0, vim3_bottom_z]) cube([vim3_w, vim3_l, vim3_pcb_t]);
    color("Gray", 0.6) translate([stack_x0 + 14, vim3_y0 + 22, vim3_top_z]) cube([28, 34, vim3_heatsink_height]);
    for (u = vim3_usba_lx) color("LightSteelBlue")
        translate([vim3_xr - vim3_usba_depth + vim3_port_overhang, vim3_y0 + u[0], vim3_top_z]) cube([vim3_usba_depth, u[1] - u[0], vim3_usba_h]);
    color("Silver") translate([vim3_xr - 11.55, vim3_y0 + 47.07, vim3_top_z]) cube([13.22, 17.47, 6.74]);   // RJ45
    color("Silver") translate([vim3_xr - 7.8, vim3_y0 + 30.4, vim3_top_z - 1.75]) cube([9.11, 16.2, 7.9]);   // HDMI socket
    // 40-pin header + IDC socket on it, ribbon goes over the VIM3 to J2
    color("Black") translate([vim3_xr - vim3_hdr_ly - 3.0, v2b(vim3_hdr_lx[0], 0)[1] - 2.5, vim3_top_z]) cube([6.0, vim3_hdr_lx[1] - vim3_hdr_lx[0] + 5.0, 8.5 + 9.0]);
    if (use_front_retainer) color("Tan") retainers_placed();
    // FPV HDMI heads (plug + square PCB, ribbon up)
    color("Gold") translate([vim3_xr + 1.31 - fpv_plug_len + fpv_seat_gap, vim3_hdmi_c[1] - 7, vim3_hdmi_cz - 2.25]) cube([fpv_plug_len, 14, 4.5]);
    color("Gold") translate([mb_x0 - fpv_seat_gap, j13_centre_y - 7, j13_z - 2.25]) cube([fpv_plug_len, 14, 4.5]);
    for (h = [vim3_head, j13_head]) color("DarkSlateGray")
        translate([h[0], h[2], h[4]]) cube([h[1] - h[0], h[3] - h[2], h[5] - h[4]]);

    // Panel jacks behind the back plate (body length inside the case)
    y_in = enclosure_depth;
    for (j = [[gps_x, 8.0, 10.0, gps_zz], [mic_x, 8.0, 12.0, io_row_z], [rca_x, 12.0, 15.0, io_row_z]])
        color("Gold")
            translate([j[0], y_in - j[2], j[3]])
            rotate([-90, 0, 0]) cylinder(d=j[1], h=j[2], $fn=24);

    // printed 11 mm spacer sleeves between the main board and the modules (H5-H8)
    for (i = [4 : len(mb_mounts) - 1]) {
        p = mb2body([mb_mounts[i][0], mb_mounts[i][1]]);
        t = (i == 7) ? 1 : 0;
        color("Goldenrod")
            translate([p[0], p[1], mb_top_z]) module_spacer(module_spacer_types[t][1], module_spacer_types[t][2]);
    }
    // Board screws / standoff threads into the inserts
    for (m = mb_mounts) {
        p = mb2body([m[0], m[1]]);
        color("Silver") translate([p[0], p[1], mb_bottom_z - m[3] + 0.5]) cylinder(h=m[3] + mb_thickness, d=m[6] - 0.4, $fn=16);
    }

    // Screen extension ribbon: wraps from J14 round the board edge and runs under the
    // board in the post-free lane (between H7 and H5), then forward to the front slot.
    xr = (j14_x_lo + j14_x_hi)/2;
    zr = floor_z + 2;
    color("Orange", 0.8) {
        translate([xr - 10.5, mb_y0 + 97, mb_top_z + 1]) cube([21, 3 + mb_rear_gap + 0.5, 0.2]);
        translate([xr - 10.5, enclosure_depth - 0.5, zr]) cube([21, 0.2, mb_top_z + 1 - zr]);
        translate([xr - 10.5, ffc_turn_y - 10.5, zr]) cube([21, enclosure_depth - ffc_turn_y + 10.5, 0.2]);
        translate([xr - 10.5, ffc_turn_y - 10.5, zr]) cube([ffc_lane_x - xr + 21, 21, 0.2]);
        translate([ffc_lane_x - 10.5, ffc_front_y - 10.5, zr]) cube([21, ffc_turn_y - ffc_front_y + 10.5, 0.2]);
        translate([front_ribbon_slot_offset_x - 10.5, ffc_front_y - 10.5, zr]) cube([ffc_lane_x - front_ribbon_slot_offset_x + 21, 21, 0.2]);
        translate([front_ribbon_slot_offset_x - 10.5, 0, zr]) cube([21, ffc_front_y, 0.2]);
    }
}


// --- RENDER LOGIC ---

if (part_to_print == "assembly") {

        translate([0, -bezel_depth - spacer_length - explode_dist, chassis_h/2])
        rotate([90, 0, 0]) {
            color("DarkCyan") screen_tray();
            color("#20304a") translate([0, 0, outer_d - ledge_depth]) tray_rounded_rect(inner_w - 0.4, inner_h - 0.4, ledge_depth, screen_radius);   // screen glass (preview)
            if (bar_split) { color("DimGray") bar_front(); color("SlateGray") bar_back(); }
            else color("DimGray") button_bar();
            color("Gainsboro") button_caps_placed();
            if (show_boards) { if (bar_split) ghost_bar_pcb(); else ghost_tray_boards(); }
            if (use_tray_mount) {
                if (hooks_modular) color("Peru") tray_hooks(); else color("Peru") tray_carrier();
                color("Sienna") tray_hatch();
                if (hooks_modular) color("SaddleBrown") translate([0, 0, explode_dist]) front_hooks();
                else color("SaddleBrown") translate([0, 0, explode_dist]) tray_bracket();
                if (show_boards && use_joiner) translate([0, 0, explode_dist]) ghost_joiner();
            }
        }

    if (!use_tray_mount) color("White") {
        for(tx = [-mount_spacing_w/2, mount_spacing_w/2]) {
            for(tz = [chassis_h/2 - mount_spacing_h/2, chassis_h/2 + mount_spacing_h/2]) {
                translate([tx, -bezel_depth - spacer_length, tz])
                    rotate([-90,0,0])
                    standoff_spacer();
            }
        }
    }

    if (add_back_plate) {
        color("DarkSlateGray")
            translate([0, front_wall_thickness + enclosure_depth + explode_dist, 0])
            back_plate();
    }

    color("DarkGray") din_front_plate();

    color("LightGray", 0.5) translate([-(chassis_w/2), front_wall_thickness, 0]) side_panel_gen(false);
    color("LightGray", 0.5) translate([(chassis_w/2), front_wall_thickness, 0]) side_panel_gen(true);
    color("DarkSlateGray", 0.6) translate([-(inner_plate_w/2), front_wall_thickness, 0]) bottom_panel();
    if (show_lid)
        color("DarkSlateGray", 0.4) translate([-(inner_plate_w/2), front_wall_thickness, chassis_h - lid_thickness + explode_dist]) top_panel();

    if (show_boards)
        translate([0, front_wall_thickness, 0]) ghost_boards();

} else if (part_to_print == "vim3_retainers") {
    retainers_print();
} else if (part_to_print == "din_front_plate") {
    rotate([90,0,0]) din_front_plate();
} else if (part_to_print == "screen_tray") {
    screen_tray();
} else if (part_to_print == "button_bar") {
    translate([0, 0, tongue_t]) button_bar();     // back face down, front face up
} else if (part_to_print == "bar_front") {
    translate([0, 0, outer_d]) rotate([0, 180, 0]) bar_front();     // face down
} else if (part_to_print == "bar_back") {
    translate([0, 0, tongue_t]) bar_back();                         // back face down
} else if (part_to_print == "front_hook") {
    translate([mount_spacing_w/2, 0, -brk_z0]) front_hook(-1);      // print 2; back face down
} else if (part_to_print == "tray_hook_left") {
    translate([mount_spacing_w/2, 0, 0]) rotate([180, 0, 0]) tray_hook(-1);   // tray-side face down
} else if (part_to_print == "tray_hook_right") {
    translate([-mount_spacing_w/2, 0, 0]) rotate([180, 0, 0]) tray_hook(1);
} else if (part_to_print == "tray_hatch") {
    tray_hatch();
} else if (part_to_print == "tape_plate") {
    translate([0, 0, btn_pcb_back_z + btn_pcb_t]) rotate([180, 0, 0]) tape_plate();   // front face down, ridges up (rotate, NOT mirror: the 2026-11-10 export was mirrored)
} else if (part_to_print == "tape_mold") {
    translate([0, 0, -(btn_pcb_back_z - tp_ridge_h) + tm_t]) tape_mold();   // flat back down, tongues up
} else if (part_to_print == "switch_plate") {
    translate([0, 0, btn_pcb_back_z + btn_pcb_t]) rotate([180, 0, 0]) switch_plate();   // front face down
} else if (part_to_print == "tray_bracket") {
    translate([0, 0, -brk_z0]) tray_bracket();                      // back face down
} else if (part_to_print == "tray_carrier") {
    rotate([180, 0, 0]) tray_carrier();                             // tray-side face down
} else if (part_to_print == "button_caps") {
    button_caps_print();
} else if (part_to_print == "module_spacers") {
    module_spacers_print();
} else if (part_to_print == "standoff_spacer") {
    standoff_spacer();
} else if (part_to_print == "left_side") {
    rotate([0, -90, 0]) side_panel_gen(false);
} else if (part_to_print == "right_side") {
    rotate([0, 90, 0]) side_panel_gen(true);
} else if (part_to_print == "bottom") {
    bottom_panel();
} else if (part_to_print == "top") {
    translate([0, 0, lid_thickness]) rotate([180, 0, 0]) top_panel();   // outer face down, ribs up
} else if (part_to_print == "back_plate") {
    rotate([90,0,0]) back_plate();
}
