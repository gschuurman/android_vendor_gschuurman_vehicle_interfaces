# Opening mainboard rev 0.3 in KiCad 10 on Windows

## 1. Footprints

Nothing to install. The three LCSC footprints (U12, F4, J14) are in `carradio.pretty` next to the schematic, and
the `fp-lib-table` in the same folder makes KiCad load them automatically.

## 2. Get the design files

Download the branch as a zip:
https://github.com/gschuurman/android_vendor_gschuurman_vehicle_interfaces/archive/refs/heads/claude/project-thread-78vfgl.zip

Unzip it and open the folder `PCB\rev0.3`. Or with git:

```powershell
git clone -b claude/project-thread-78vfgl https://github.com/gschuurman/android_vendor_gschuurman_vehicle_interfaces.git
```

## 3. Open in KiCad 10

1. Double-click `carradio_peripheral_rev03.kicad_pro`.
2. Open the schematic. KiCad 10 converts the file from the KiCad 7 format; say yes, then save.
3. **Don't** run "Update Symbols from Library". The symbols are built into the file on purpose.

## 4. Check, then start the board

1. **Inspect > Electrical Rules Checker > Run ERC.** Some "power pin not driven" warnings are expected on
   nets fed through a fuse or diode. Add a PWR_FLAG symbol on those nets. Anything else, send me the
   report.
2. **Tools > Update PCB from Schematic** (F8) pulls all parts into a new board.
3. Before routing, set up the board as 4 layers under **File > Board Setup > Physical Stackup**. The layout
   rules (HDMI and USB pairs, power stage, GPS) are in `../rev0.2/DESIGN_REVIEW_rev02.md`, section 6, and
   `DESIGN_rev03.md`.
