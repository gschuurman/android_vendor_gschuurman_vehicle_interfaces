set -e
cd /tmp/claude-0/-home-user/60f6a4d6-8ab7-59ef-94af-937b149e430f/scratchpad/bb4
python3 gen_pcb.py
python3 -c "
import pcbnew
b=pcbnew.LoadBoard('buttonbar_v4/buttonbar_v4.kicad_pcb'); pcbnew.ExportSpecctraDSN(b,'buttonbar_v4/buttonbar_v4.dsn')"
(cd fr && timeout 500 java -jar freerouting.jar -de /tmp/claude-0/-home-user/60f6a4d6-8ab7-59ef-94af-937b149e430f/scratchpad/bb4/buttonbar_v4/buttonbar_v4.dsn -do /tmp/claude-0/-home-user/60f6a4d6-8ab7-59ef-94af-937b149e430f/scratchpad/bb4/buttonbar_v4/buttonbar_v4.ses -mp 100 --gui.enabled=false > /tmp/claude-0/-home-user/60f6a4d6-8ab7-59ef-94af-937b149e430f/scratchpad/bb4/fr4.log 2>&1 || true)
python3 import_ses.py && python3 fixup.py 2>&1 | grep -v leak
python3 -c "
import pcbnew
b=pcbnew.LoadBoard('buttonbar_v4/buttonbar_v4.kicad_pcb')
pcbnew.WriteDRCReport(b,'buttonbar_v4/drc.rpt',pcbnew.EDA_UNITS_MILLIMETRES,True)"
grep -E 'Found' buttonbar_v4/drc.rpt; grep '^\[' buttonbar_v4/drc.rpt | sort | uniq -c
