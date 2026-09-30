# Opening mainboard rev 0.3 in KiCad 10 on Windows

## 1. Install Python

This is a one-time step, and only needed for the footprint tool.

1. Download the Windows installer from https://www.python.org/downloads/windows/, or in PowerShell run
   `winget install Python.Python.3.12`.
2. In the installer, tick **"Add python.exe to PATH"** before clicking Install.
3. Open a new PowerShell window and check it works: `py --version`

## 2. Install easyeda2kicad

In PowerShell:

```powershell
py -m pip install easyeda2kicad
```

## 3. Download the three missing footprints

The TPS55288 converter (U12), the fuse holder (F4) and the screen connector (J14) don't have footprints
in KiCad's library. This pulls the exact LCSC footprints and 3D models:

```powershell
mkdir "$HOME\Documents\KiCad\lcsc"
py -m easyeda2kicad --footprint --3d --lcsc_id C2864583 C206907 C2856837 --output "$HOME\Documents\KiCad\lcsc\lcsc"
```

That creates `Documents\KiCad\lcsc\lcsc.pretty` (the footprints) and `lcsc.3dshapes` (the 3D models).

## 4. Get the design files

Download the branch as a zip:
https://github.com/gschuurman/android_vendor_gschuurman_vehicle_interfaces/archive/refs/heads/claude/project-thread-78vfgl.zip

Unzip it and open the folder `PCB\rev0.3`. Or with git:

```powershell
git clone -b claude/project-thread-78vfgl https://github.com/gschuurman/android_vendor_gschuurman_vehicle_interfaces.git
```

## 5. Open in KiCad 10

1. Double-click `carradio_peripheral_rev03.kicad_pro`.
2. Open the schematic. KiCad 10 converts the file from the KiCad 7 format; say yes, then save.
3. **Don't** run "Update Symbols from Library". The symbols are built into the file on purpose.

## 6. Add the footprint library

1. Go to **Preferences > Manage Footprint Libraries > Global Libraries** and click the folder icon.
2. Pick `Documents\KiCad\lcsc\lcsc.pretty` and give it the nickname `lcsc`. Click OK.

## 7. Assign the three footprints

In the schematic, open each part (double-click it) and set **Footprint** to the new part from the `lcsc`
library. Use the footprint browser button next to the field, open the `lcsc` library, and pick the
footprint whose name matches the part:

| Part | LCSC | Part name to look for |
|---|---|---|
| U12 | C2864583 | TPS55288RPMR |
| F4 | C206907 | 01530008Z (Littelfuse) |
| J14 | C2856837 | FPC-05FB-40PH20 |

J14 already has a Hirose FH12 footprint. Replace it, because the XUNPU part's pads may differ.

## 8. Check, then start the board

1. **Inspect > Electrical Rules Checker > Run ERC.** Some "power pin not driven" warnings are expected on
   nets fed through a fuse or diode. Add a PWR_FLAG symbol on those nets. Anything else, send me the
   report.
2. **Tools > Update PCB from Schematic** (F8) pulls all parts into a new board.
3. Before routing, set up the board as 4 layers under **File > Board Setup > Physical Stackup**. The layout
   rules (HDMI and USB pairs, power stage, GPS) are in `../rev0.2/DESIGN_REVIEW_rev02.md`, section 6, and
   `DESIGN_rev03.md`.
