# rev 0.5 layout scripts

`main/` holds the rev 0.4 scripts (see `../../rev0.4/layout/README.md` for the original flow and the Windows notes)
plus the rev 0.5 steps. Run them with KiCad 10's Python from a work folder; after every script that saves a board under
a new name, copy the real `.kicad_pro` next to it (pcbnew writes a default project file otherwise, and DRC then uses
default rules).

Rev 0.5 main board, starting from the routed rev 0.4 board:

1. `dropexp.py in out netlist`: removes the GPIO11/12/13/29/34 expansion copper, gives the freed pads the schematic's
   `unconnected-(...)` net names and puts LUX_SDA/SCL on J21 pins 2/3.
2. `movebuck.py`: places the TPS560430 support parts at U1 per the datasheet layout section and rips the touched nets.
3. `pairroute.py` (USB_UP pair): `SWAPSTART=/USB_UP_DM PRE=19.995,8.4 POST="56.8,21.27;56.4,21.27"` with start
   19.995 9.6 and end 56.8 19.2. A centreline router plus offset; W/G set the trace width and gap.
4. `bridgeall.sh` with `ONLY=` for the buck nets (0.5 mm SW/VIN, 0.3 mm CB/FB) and +5V_AON (0.5 mm), `gndvia.py`,
   then `riploop.sh` for everything the moves displaced.
5. `pairkeep.py`: In1 keep-out under the pair; `bridge.py` respects rule areas. `riploop.sh` again.
6. `nudge.py`, `solidgnd.py`, `clean.py`, `widen.py ... /+5V_AON 0.5 0.3`, DRC. `pairqa.py` reports pair lengths, In1
   crossings and +5V_AON widths.

Removed pcbnew items must stay referenced in Python until the script ends (`gone.append(t)`); KiCad 10's bindings
break once a removed track is garbage-collected.

The schematic was not regenerated: KiCad 10's symbol library renamed some KiCad 7 symbols `gen5.py` uses (for
example `Q_PMOS_GDS`). The rev 0.5 schematic is the rev 0.4 file with those labels edited (five no-connects at U20,
three at J10/J21, J21 pins 2/3 relabelled LUX_SDA/SCL); `gen5.py` records the same pin map for a future run with the
KiCad 7 library.
