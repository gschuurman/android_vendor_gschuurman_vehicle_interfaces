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
2. The board already exists: open `carradio_peripheral_rev03.kicad_pcb`. It is 4 layers (JLC04161H-7628),
   109 x 92 mm plus four 8 x 9 mm corner tabs with plated M3 holes (125 x 92 mm overall), fully routed:
   DRC shows 0 unconnected items and no copper errors, only silkscreen warnings. Net classes and rules
   (0.45/0.2 mm signal vias, 0.6/0.3 mm on VSYS_IN and +5V_SYS) are in the project file. The footprints for U12, F4 and J14 come from the
   project library `carradio.pretty`, so easyeda2kicad is no longer needed.
3. Only use **Tools > Update PCB from Schematic** (F8) on this board after a schematic change; never into
   a new empty board, or the placement is lost.
4. The TPS55288 area was reworked against TI's layout guide (see `TPS55288_LAYOUT_REVIEW.md`).
   NT1-NT3 are net ties (copper only, not in the BOM): Kelvin sense taps at R74 and the single
   AGND-to-GND joint at C53. Before ordering: check J14 pin 1 in the 3D viewer and tidy the
   silkscreen (reference text overlaps pads in places, worst around U12's control parts). Press B to refill zones before running DRC. How the routing was made is in
   `layout/README.md`.
