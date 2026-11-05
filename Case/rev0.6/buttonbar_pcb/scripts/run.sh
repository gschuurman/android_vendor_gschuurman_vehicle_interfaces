set -e
python3 gen_pcb.py
python3 -c "
import pcbnew
b=pcbnew.LoadBoard('buttonbar/buttonbar.kicad_pcb'); pcbnew.ExportSpecctraDSN(b,'buttonbar/buttonbar.dsn')"
(cd fr && timeout 600 java -jar freerouting.jar -de ../buttonbar/buttonbar.dsn -do ../buttonbar/buttonbar.ses -mp 100 --gui.enabled=false > fr.log 2>&1 || true)
python3 import_ses.py
python3 -c "
import pcbnew
b=pcbnew.LoadBoard('buttonbar/buttonbar.kicad_pcb')
pcbnew.WriteDRCReport(b,'buttonbar/drc.rpt',pcbnew.EDA_UNITS_MILLIMETRES,True)"
grep -E 'Found' buttonbar/drc.rpt; grep '^\[' buttonbar/drc.rpt | sort | uniq -c
