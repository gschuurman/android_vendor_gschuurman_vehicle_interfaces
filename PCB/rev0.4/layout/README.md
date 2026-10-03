# rev 0.4 layout scripts

Generated with KiCad 10 (`kicad/kicad:10.0` Docker image) pcbnew Python, Freerouting 2.1.0 and small grid routers.
They record how the boards were made; paths inside them point at the build sandbox (`/w/...`), so they need
editing before reuse.

- `schematic/gen4.py main|gnss|audio|usb` writes each board's schematic and BOM (needs the KiCad 7 symbol library).
- `gnss/gm.py` places the GNSS module and pre-routes its RF and supply copper; `swapj11.py` swapped the SMA for the U.FL.
- `usb/um6.py`, `audio/am4.py` place the modules.
- `main/run_n3x.sh` runs the main-board flow: `b5.py` (placement, module sockets from `modules.json`), `hd4.py` (HDMI),
  `fx1.py`/`fx2.py` (fixes), `add5v.py` (In2 +5V strip to J18), `fanmcu.py` (RP2350B escape vias), `fanout4.py` (GND vias),
  `prep4.py` (rules and DSN), then three Freerouting runs. `post_route4.py`, `evict4.py`, `clean.py` and `loop5.sh`
  (with `maze2b.py`) import and finish the result.

## Main board finish (rev 0.4, native KiCad 10 on Windows)

The routed main board was finished on a Windows PC with KiCad 10's bundled Python and kicad-cli, Freerouting 2.1.0 on
Java 21, and scipy/shapely installed with `pip install --target` (`withlib.py` puts them on the path; KiCad's Python
ignores PYTHONPATH). Run the scripts from Git Bash with `MSYS_NO_PATHCONV=1`, or net names like `/MCU_XOUT` are turned
into Windows paths.

1. `fixc3.py`: the VSYS_IN feed ran past its via into C3 pad 1 (BUCK_CB); cut back to via-to-pour.
2. `rmz.py ... all`, `prep4.py` (`KICAD_TEMPLATES` = the KiCad template folder), `Ω`→`R`, `stripgnd.py`; five parallel
   Freerouting jobs (55 min each). Some jobs hang at their timeout without writing a session; kill them.
3. `evalses.sh rN` imports a session (`post_route4.py`, `NETLIST`), evicts, cleans and runs DRC; the best was 39 unconnected.
4. `loop5w.sh` (maze2b, VMAX 3; `MAZE_T`/`MAZE_KILL` set its time budget) took it to 18. Higher VMAX diverges.
5. The RP2350B fan-out walls itself in: inner escape vias at 0.8 mm pitch leave 0.35 mm gaps, so the EP GND and every
   pin escaping inward are boxed in on In1/In2/B. `gndvia.py` gives open GND pads their own via, `dropavdd.py` removes
   the unused pin 61 inner via, and `deepen.py` moves every other inner via 0.8 mm further in (10 of 19 fit), opening
   1.15 mm gaps.
6. `bridge.py` is a single-connection grid router (own-net island to any other piece of the net, through vias, GND pours
   treated as refillable; `RIP=1` lets it rip unlocked tracks at cost `SOFT`, `BIGONLY=1`/`DSTLAYERS` aim GND at the
   planes). `bridgeall.sh` runs it for every unconnected pair and `riploop.sh` alternates plain and rip-up passes.
7. Final touches: `fixhole.py` (In1 ILLUM_LED vs the J1 peg hole, BATT_RAW stitching vias shifted 0.1 mm), `nudge.py`
   (one QSPI_SCLK via), `clean.py`, `solidgnd.py` (J23/J25 socket GND pins solid to the pours: starved thermals).

Result: DRC 0 unconnected, no errors (warnings only: silkscreen, and the unused fan-out stubs/vias).
Review items: USB_UP_DP runs 42 mm single-ended at 0.16 mm (not coupled to USB_UP_DM), +5V_AON has about 31 mm and
+3V3_MCU about 13 mm at 0.2 mm instead of the 0.3 mm Power width.
