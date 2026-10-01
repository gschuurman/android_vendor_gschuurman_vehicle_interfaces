# Rev 0.3 layout scripts

These scripts made `carradio_peripheral_rev03.kicad_pcb`. They run in the `kicad/kicad:10.0` Docker image
(pcbnew Python) plus host Python with numpy, shapely, scipy and Pillow. They are kept as a record; for
small changes, edit the board in KiCad directly.

## Order used

1. `pipeline.sh base`: `build.py` (footprints, floorplan from `floorplan.py`), `hdmi.py` (HDMI routed and
   locked), `dumppads.py`, `powerpoly.py`, `viagrid.py`, `addpower.py` (locked F/B copper zones named
   `PWR <net>` for the TPS55288 stage plus stitching vias), `fanout.py` (GND vias), `prep_route.py`
   (net classes, rules, Specctra DSN with In1 set to `type power`).
2. Freerouting 2.1.0 on the DSN, then `post_route.py` (import SES, GND pours) and `evict.py` (removes
   autorouted tracks that cross the power zones; Freerouting ignores them).
3. `finish.sh`: `dumpstate.py` then `maze.py` and `maze2.py` (grid routers with rip-up and reroute,
   applied by `addtracks.py` / `apply2.py`). `loop.sh` repeats maze2 rounds.
4. Hand edits around U12 with `hand.py` and the files in `hand_ops/` (run in order 3 to 11, with maze2
   rounds between them). Notable changes:
   - U12 pins 2 to 6 fan out to two via columns (x 33.15 and 32.45) so VIN can reach the input FET.
   - R69 (ILIM set resistor) and TH1 (board thermistor) swapped places, so R69 sits right next to U12
     pin 17 and TH1 sits where R69 was.
   - VSYS_IN from D15/U15 joins the input caps through a 0.6 mm track on B.
5. `clean.py` (removes dangling stubs, keeping any whose removal would break a connection),
   `simplify.py` / `simp.sh` (straightens the grid router's stair-steps, reverting any that break
   clearance), `fin.py` (solid zone connection on U15 pad 9 and J7 pad 2), `tabs.py` (corner tabs and
   M3 holes), `trim.py` (shortens remaining dangling track ends).

`q.py`, `plotst.py`, `crop.sh` and `hd.sh` are inspection helpers.

## TPS55288 rework (after the TI layout review)

`rw.py` applies the review fixes to the routed board: new pad nets for the net ties (BB_ISP, BB_ISN,
BB_AGND), the control parts clustered at U12, hand-placed VCC/BOOT/sense/control copper (locked), an AGND
zone and new SW2/VOUT zone outlines. The nets it had to move out of the way were re-routed with `maze2.py`
(VMAX=3, then VMAX=6 for RPP_G), the `hand_ops/rw_*.txt` fixes, `clean.py`, `dang.py` (removes dead
branches DRC flags as dangling), `simplify.py` limited to the re-routed nets (`NETS=` env var) and
`fixz.py` (VOUT zone notch for the Kelvin taps, hidden net-tie fields).

