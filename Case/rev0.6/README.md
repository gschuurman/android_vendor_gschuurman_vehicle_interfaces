# 1 DIN case for peripheral board rev 0.6 + VIM3/M2X

`car_radio_rev06_case.scad` is a rework of the prototype case (`car_radio improved_0.2.scad`). It keeps the same parts and style: heat-set inserts, DIN clip pockets, removal-key slots, the front plate with the screen tray and flanged spacers, separate side, top and bottom panels, and a back plate. Pick a part with `part_to_print`. `show_boards` draws ghost boards, plugs and jacks in the assembly view, and `show_lid = false` lets you look inside. The OpenSCAD console prints the fit checks.

Rendered and exported with OpenSCAD 2021.01. Every part exports as a clean, simple (manifold) STL: see `stl/` for the files and `render/` for the pictures.

## Layout

- **Main board** (rev 0.6, 100 x 100 mm). The outline, the mounting holes and every connector position come from `PCB/rev0.6/main/carradio_peripheral_rev06.kicad_pcb`. The modules come from `rev0.6/usb` and `rev0.4/gnss|audio`. The board sits rear right on **eight 12.6 mm posts, one under every hole** (8 mm before the VIM3/M2X rework, see below), each with a heat-set insert (see the next section). It is **turned 90 degrees** so that its KiCad right edge (x = 100) faces the back plate:
  - The three USB-A sockets on the USB module face the rear: J17 RTL-SDR, then J19 and J20 for external devices. In assembly coordinates they sit at X = 23.1, 41.3 and 59.5 mm, with their centre about 27.8 mm above the case bottom.
  - The KiCad top edge, with J2 IDC, J13 HDMI, J18 VIN and J5 power key, faces the VIM3 on the left. The ISO and button connectors (J1, J8, J12, J7) are on the right-hand side. All of these are vertical apart from J13.
- **VIM3 + New M2X** sits front left in a pocket in the bottom panel, ports facing the main board, 40-pin header against the left side, held by a screwed retainer strip at the front and a tongue on the back plate at the rear. See "VIM3 / M2X mount" below.
- **HDMI bay**: J13 faces left, so the HDMI plug goes in from the left, behind the VIM3 stack. That is the reason the case is **134 mm deep inside, 146 mm overall** (the prototype was 110 / 118). That is still within a normal DIN cage, but check behind your dash.
- **Back plate**: SMA bulkhead (GPS, with an anti-rotation flat, right next to the SDR port at USB height), 3.5 mm panel jack (MIC, M6 thread), RCA (CAM), three USB-A openings, and one cable slit (8 x 16 mm, as on the prototype) for the ISO A + C1 pigtails. The pigtails carry the 12 V power, so they are the "power" opening. The slit is open to the top edge, so you can lay the loom in before fitting the lid. The USB openings have a shared outside pocket that leaves only 1 mm of plate, so plug overmolds can seat fully. The old audio-jack and SPDIF cutouts are gone. The labels are engraved and mirrored so they read correctly from behind.
- Vent slots in the lid and the bottom panel over and under the VIM3. There is now a third assembly screw per side, because the case is deeper. The release-key holes and the serial pogo plug are disabled (`add_key_slots`, `add_uart_pogo`).

## Main-board holes and module standoffs

I checked the holes against two independent sources: the KiCad footprints and the Gerber drill file (`fab/main/...-PTH.drl`). The two agree exactly. There are 8 mounting holes. The only other large hole is the 3.81 mm NPTH, which is the F4 fuse-holder peg, not a mounting hole. For each module, I matched its header pins to the main-board socket (all pins within 0.000 mm) and then mapped the module's own mounting hole across. All three land exactly on a main-board hole.

| Hole | KiCad (x, y) | Drill | Used by | Post in the case (assembly X, Y) | Insert bore | Hardware |
|---|---|---|---|---|---|---|
| H1 | 4.5, 4.5 | 3.2 | main board | -14.5, 42.5 | 4.2 x 6 | M3 x 8 screw |
| H2 | 95.5, 4.5 | 3.2 | main board | -14.5, 133.5 | 4.2 x 6 | M3 x 8 screw |
| H3 | 4.5, 95.5 | 3.2 | main board | 76.5, 42.5 | 4.2 x 6 | M3 x 8 screw |
| H4 | 95.5, 95.5 | 3.2 | main board | 76.5, 133.5 | 4.2 x 6 | M3 x 8 screw |
| H5 | 67.8, 83.7 | 2.7 | USB module (its H1 at 3.8, 51.2) | 64.7, 105.8 | 3.6 x 5 | M2.5 x 11 M-F standoff + M2.5 screw |
| H6 | 31.0, 16.5 | 2.7 | audio module rev 0.4/0.7 (its hole at 37.5, 4.0, turned 270 deg) | -2.5, 69.0 | 3.6 x 5 | M2.5 x 11 M-F standoff + M2.5 screw |
| H7 | 3.2, 34.3 | 2.7 | GNSS module (its hole at 3.2, 15.3) | 15.3, 41.2 | 3.6 x 5 | M2.5 x 11 M-F standoff + M2.5 screw |
| H8 | 69.6, 18.5 | 2.2 | future K-line module on J10 | -0.5, 107.6 | 3.2 x 4 | M2 x 11 M-F standoff + M2 screw |

- The M3 pattern is 91.0 x 91.0 mm. I measured it again from the exported `bottom.stl` and got the same 91.0 x 91.0, with every post at the position in the table.
- 11 mm = 8.5 mm socket + 2.5 mm header body, so a module sits flat on its standoff. The standoff's male thread passes through the 1.6 mm main board into the insert. Use a male thread of at least 4 mm (M2.5) or 3 mm (M2).
- You melt each insert in from the top of its post before the board goes in. A screw-clearance bore continues below every insert, so long screws don't bottom out. It stops 0.6 mm above the underside of the panel, so nothing shows from below.
- No bottom-side pad comes within the post footprints. The nearest one is 6.2 mm from a hole centre (J21 pin 10 at H5), and the largest post radius is 4 mm. The posts sit on the holes' own plated rings.
- Insert sizes are parameters in `mb_mounts` (bore, depth, lead-in, post OD, screw clearance). M3 and M2 are the same as your prototype. **M2.5 (3.6 mm bore) is new, so check it against your inserts.**
- The posts don't cover the stacked capture board (rev 0.7). It screws to the USB module, not to the main board.

## Side-panel inserts

The side wall plus ledge is only 7 mm thick. A 4.2 mm M3 insert bore centred in it broke through the ledge face, so it had almost no material to grip. Every side-panel insert now sits in its own **boss**: a 9 mm round pad around the insert axis, blended into the wall, reaching 2.5 mm past the ledge face. That leaves at least 2.1 mm of wall inside and 2.9 mm to the outer face.

- Six vertical bosses per side (top and bottom, at Y 20, 67 and 119) for the lid and bottom-panel screws.
- Two front bosses per side, 11 mm long, for the front plate. These four screws carry the front plate with the display.
- Two rear bosses per side, 9 mm long, for the back plate.
- **Changed:** the lower rear insert moved from z 12 to z 20 (`rear_mount_z`), because at z 12 its boss would hit the corner of the main board. The back-plate holes moved with it. The front holes stay at z 12 / 37.5.
- **Changed (2026-11-05):** the VIM3 sits 0.8 mm from the left ledge (`vim3_side_clear`); the left side's lower insert pads are notched where the M2X edge passes, and the right side has no lower rear insert (`right_drop_low_rear`).
- Checked in OpenSCAD: the side panels have 0 mm³ of overlap with the boards, plugs, jacks, bottom panel, back plate and front plate.
- Sizes are parameters: `side_boss_d`, `side_boss_extra`, `front_boss_length`, `rear_boss_length`. The bore is unchanged (4.2 mm, 6.2 deep).

## Things to know before printing

1. **Screen ribbon (conflict).** With the USB ports at the rear, J14 (the display FPC) also faces the rear, and its ribbon leaves the board edge towards the back plate. The panel's own FPC cannot reach it. You need a 40-pin 0.5 mm FFC extension of about 160 mm plus an FPC joiner board near the front. The ribbon wraps round the board edge at J14 and runs forward **under** the main board (that is why the posts are 8 mm). The back plate has a 2 mm relief on the inside behind J14 for the wrap. Now that every hole has a post, H6 and H8 sit right behind J14, so the ribbon can't run straight forward. It needs a 45 degree fold just behind H8 into the post-free lane at X 20-42 (between H7 and H5), then a fold in front of the board over to the front slot (X = -12). The orange ghost in the assembly shows this route, set by `ffc_lane_x`, `ffc_turn_y` and `ffc_front_y`. Because of the wrap, check whether you need a same-side or an opposite-side contact FFC. Moving the USB-A ports to the other edge in the next revision removes all of this.
2. **The RTL-SDR dongle plugs in from outside** the back plate, because J17 is one of the rear sockets. The dongle sticks out the back, which is also where the FM/DAB antenna connects. If there is not enough room behind the cage, use a short USB extension.
3. **HDMI cable.** FPV ribbon with 90 degree "A2" heads (ribbon up). See "VIM3 / M2X mount" below.
4. **VIM3 / M2X numbers** now come from the Khadas DXF/STEP files and Glenn's measurements; see "VIM3 / M2X mount" below.
5. **USB-A height**: `usb_a_center_above_module = 2.6` assumes the Molex 67643 shell sits flat on the module. Check it on your stacked board. The openings are 15 x 8 mm, so they allow about +/-1 mm.
6. **Jack holes**: SMA 6.6 mm, mic 6.2 mm (PJ-392), RCA 10 mm (as on the prototype). The plate is 3 mm thick.

## OpenSCAD in the cloud environment

Cloud sessions start from a fresh container, so a manual install is lost when the session ends. To have OpenSCAD in every new session of this project, add this to the cloud environment's **Setup script** (Project settings, Cloud environment, gear icon):

```
apt-get update && apt-get install -y --no-install-recommends openscad xvfb xauth
```

xvfb is needed for PNG renders (`xvfb-run -a openscad -o view.png ...`). STL export works without it:

```
openscad -o bottom.stl -D 'part_to_print="bottom"' car_radio_rev06_case.scad
```

## Screen tray and button bar (v2, 2026-11-04)

Replaces the 18 mm task bar and the screen-off tab, which were too big.

- **Front is 179.5 x 122.5 mm**: the screen tray is 109.5 mm and the button bar 13 mm. The previous version was 140.5 mm tall. There is no button on the top edge.
- **Screen tray (`screen_tray`)** is one piece. The screen is taped in as before, with the pocket 1.5 mm larger and turned 180 deg. The bottom corners are square so the bar continues the outline. Four M2 inserts in the back of the base take the bar.
- **Button bar (`button_bar`)** is the only separate front part. It has a tongue that lies behind the tray and is screwed on from the back with 4x M2x6 into the tray inserts. No screws show at the front. Print it with its back face down; the front skin is then the top surface, which you can iron.
- **9 buttons in one line** (left = driver side): home | vol-, mute, vol+ | screen off (middle) | previous, play/pause, next | voice.
- **Caps (`button_caps`, 9 per plate)** are loose 10 x 6 mm pills with a flange above and below that keeps them in the skin. They stand **1.5 mm proud** of the bar and the screen glass. The icons are **raised 0.6 mm**: paint over them with a roller or a flat brush so only the tops take the paint. Print them flange down, icon up, at a fine layer height (0.12 mm).
- **Switch strip**: perfboard, 176.7 x 11.5 mm, with the 9 Kiwi KW-1556 / Adafruit 1489 switches. The cap pitch is on the 2.54 mm grid: 12.7 mm within a group, 33.02 mm from the screen-off button to each group, and 78.74 mm from the centre to home/voice. The strip drops in from the top of the bar into grooves in the end and bottom walls. The tray holds it once the bar is screwed on, and three ribs behind it stop it bending. Wires leave through a slot in the back wall.
- **Switch height is still an assumption** (5.0 mm from board to plunger, `btn_total_h`). The cap flange should just touch the plunger (`btn_preload` 0.1 mm). Measure one switch before printing the bar.
- **BH1750** (GY-302 module) sits between screen off and previous, behind a 3 mm window. Its header edge points down and it sinks 1.2 mm into the bottom wall. The top 2 mm reach into a pocket in the tray rim. Fix it with a dot of hot glue. If the chip is not centred on your module, set `bh1750_chip_offset`.
- **All 9 buttons go to J12** through diode coding (see the wiring section below).

Wiring (rev 0.6 main board): **only J12**, with diode coding. Diagram: `wiring/wiring.png`.

J12 has 4 inputs (each 1k series, 10k pull-up, 100 nF on the board) plus GND. Four buttons pull one line to GND directly. The other five pull two lines to GND at the same time, each line through its own Schottky diode (BAT85 or BAT43, cathode towards the switch). Don't use 1N4148s: with the 1k + 10k on the board a silicon diode leaves the line at ~0.8 V, right at the RP2350's maximum low level. A Schottky gives ~0.5 V.

| Button (# from the left) | Lines low | J12 pins |
|---|---|---|
| #5 Screen off | S | 1 (GPIO18) |
| #4 Volume up | U | 2 (GPIO17) |
| #2 Volume down | D | 3 (GPIO22) |
| #3 Mute | M | 4 (GPIO16) |
| #7 Play/pause | U + D | 2 + 3 |
| #6 Previous | D + M | 3 + 4 |
| #8 Next | U + M | 2 + 4 |
| #1 Home | S + D | 1 + 3 |
| #9 Voice | S + U | 1 + 2 |
| (spare) | S + M | 1 + 4 |
| GND | | 5 |
| BH1750 | J7: 1 3V3, 2 GND, 3 SCL, 4 SDA (I2C cannot go through J12) | |

Mount the 10 diodes flat on the back of the strip. Firmware: after any edge, wait ~30 ms (debounce) and decode the pattern of the 4 lines. The current firmware treats the four lines as separate buttons, so it needs this change. J21 and J10 stay free.

## Top / bottom panels and front / back screws (2026-11-04)

- The panels now run the **full width** and sit on top of the side walls. The side-panel screws moved from 1.8 mm to **4.5 mm from the edge**, so the countersunk heads no longer break out of the panel edge.
- A **locating lip** (1.5 x 2.5 mm) runs along both long edges, against the ledge face. It holds the side panels in line.
- **Ribs** (2 x 3 mm grid) stiffen the top panel. The top panel prints outer face down (`part_to_print="top"` turns it).
- **Extra screws** go into the front and back plates: M3 inserts in bosses on the panel ends (horizontal, melted in from the end face). Front: top at X -25 / 70, bottom at X 36 / 65 (behind the screen, clear of its mounting slots). Back: top at X -30 / 50, bottom at X 55 (X -60 / -30 dropped on 2026-11-05: the M2X runs up to the back plate there). That adds 4 screws in front and 5 at the back, all countersunk or counterbored like the existing ones.
- Checked in OpenSCAD: every pair of case parts overlaps by 0 mm³ (only touching faces), and nothing overlaps the boards, plugs or jacks.

## Screen fit check against Waveshare 70H-1024600 (2026-11-04)

Source: the spec table on https://www.waveshare.com/wiki/70H-1024600. The drawing images and CAD zip could not be downloaded from this environment, so only the table values are used.

| Waveshare spec | Value | In the tray | Margin |
|---|---|---|---|
| Touch screen (cover glass) | 173 x 103 mm | glass seat 175.5 x 105.5 mm, 1.5 mm deep | 1.25 mm per side |
| Display module (LCD body) | 164 x 97 mm | opening behind the seat 170.5 x 100.5 mm | 3.25 mm (sides), 1.75 mm (top/bottom) |
| Total thickness, touch version | 4.2 mm | 1.5 mm glass seat + 4.5 mm down to the tray base (`screen_depth` 6.0, was 8.0) | LCD back rests on 1 mm double-sided foam tape on the base (`screen_back_pad`) |
| Cover glass (4.2 - 3.5) | about 0.7 mm | in a 1.5 mm seat | glass face about 0.3-0.6 mm below the rim with tape: edges protected |
| Interface | 40-pin 0.5 mm FPC (~21 mm wide) | ribbon slot 25 x 3 mm (top) | ~2 mm per side |

- The BH1750 pocket and the bar inserts stay within the 4.5 mm solid rim / the base under the panel; no interference with the LCD body.
- The caps stand about 2 mm in front of the glass face.
- The prototype's 8 mm depth left the LCD hanging behind the glass, so the screen flexed (Glenn). `screen_depth` is now computed from the seat, the 3.5 mm LCD and a 1 mm foam pad (6.0 mm), and the tray and button bar are 2 mm thinner. Put the foam on the LCD back away from the FPC path (top) and the touch relief (bottom). If your foam is thicker or thinner, change `screen_back_pad`.
- Not checked (no data): touch controller / FPC parts on the back of the panel. Measure the thickest point on the back of your panel; it must fit in the 1 mm foam gap, or cut the foam around it.

## Module spacer sleeves (2026-11-04)

Part `module_spacers`: printed 11 mm sleeves that sit between the main board and the plug-in modules on H5-H7 (M2.5: ID 2.9, OD 5.0, 4 printed incl. one spare) and H8 (M2: ID 2.4, OD 4.5, 2 printed). One screw goes through the module, the sleeve and the main board into the insert in the bottom post: M2.5 x 18 (x20 also fits) and M2 x 18. 11 mm matches the stack height of the header sockets (8.5 mm socket + 2.5 mm pin header body); if your stack measures differently, change `module_stack_height`. Print them upright with 3+ perimeters. In the assembly view they replace the brass standoffs; checked against all case parts (0 mm3 overlap).

## Button bar PCB (KiCad)

KiCad project in `buttonbar_pcb/` (schematic, 2-layer PCB, Gerbers, README). 176.7 x 11.5 mm, 9 switches,
10 BAT85, 5 wires to J12. The bar's support rib moved to x -24 and the wire slot widened to x -17..-5 so they clear J1.

## VIM3 / M2X mount (rework 2026-11-05)

The first version guessed the VIM3 and M2X sizes; the M2X did not fit, the J2 ribbon did not line up and the HDMI plug did not fit. Everything below now comes from the Khadas VIM3 V11 DXF and STEP, the New M2X STEP, and Glenn's measurements.

- **Boards**: VIM3 82 x 56.64 x 1.2 mm, holes (2.5, 53.51), (16.5, 8.01), (65.5, 8.01), (79.5, 53.51). New M2X 93.55 x 56 x 0.8 mm, under the VIM3, sockets and SSD facing down (3.7 mm under it). The VIM3 sits directly on the M2X bosses (1.5 mm, no spacers). The M2X sticks out 12 mm past the VIM3 at its M.2 end, towards the back plate (0.7 mm left).
- **Orientation**: VIM3 ports face the main board (+X), the 40-pin header is against the left side. Header pin 1 lines up with J2 pin 1 (Y 46.6), so the IDC ribbon runs straight.
- **Pocket** in the bottom panel: two 1.2 mm edge ledges carry the M2X 4.5 mm above the floor (`m2x_support_h`, 0.8 mm under the SSD). A low wall on the port side and at the front locates the stack; the walls stop 0.5 mm above the M2X so they clear the VIM3 HDMI socket.
- **Retainer, no snap clips**: one printed strip (`vim3_retainers`) over the VIM3 front edge, 0.3 mm above the board, screwed down with 2x M3 x 8 into heat-set inserts in two posts of the bottom panel. At the rear a tongue on the back plate lies 0.3 mm over the M2X edge. The board is held with play, not clamped.
- **HDMI**: FPV ribbon with 90 degree "A2" heads, ribbon up. Head PCB 20 x 20 mm, plug 8 mm in front of it, plug centre 1 mm above the head's bottom edge (Glenn). The VIM3 head sits in the gap in front of the main board edge (head back at X -19.5, main board at -19). The J13 head sits over the VIM3's rear USB-A port.
- **Main-board height** is computed (`mb_standoff_height`) so the J13 head clears that USB-A port: posts 12.6 mm, main board 15.6-17.2 mm, modules 28.2-29.8 mm, USB-A centre 32.4 mm. J13: top 6 mm above the PCB (Glenn), centre ~3.05; the model uses 3.2 plus 1.0 mm margin, so the real clearance is ~0.85 mm.
- **Checked in OpenSCAD**: no overlap between case parts, boards, plugs and the FPV heads; no warnings.

### What to reprint after 2026-11-04

| Part | Action |
|---|---|
| bottom | reprint (`stl/bottom.stl`) |
| back_plate | reprint (`stl/back_plate.stl`) |
| vim3_retainers | new print, needs 2 M3 inserts |
| left_side | keep the printed one; file the two low insert pads back 1.5 mm where the M2X edge passes |
| right_side | keep the printed one; saw off the lower rear insert pad |
| top, din_front_plate, screen_tray, button_bar | keep as printed |

`stl/reference_only/` holds the side and top panels as the current model exports them, for reference only; the printed ones with the changes above are equivalent.
