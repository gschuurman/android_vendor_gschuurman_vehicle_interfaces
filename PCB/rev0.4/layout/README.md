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
