#!/bin/bash
# evalses.sh r : import r.ses into base, evict, clean, rmshort, DRC -> p_r.kicad_pcb ; prints unconnected / copper errors
PY="/c/Program Files/KiCad/10.0/bin/python.exe"; KCLI="/c/Program Files/KiCad/10.0/bin/kicad-cli.exe"; r=$1
export NETLIST=${NETLIST:-../../main/carradio_peripheral_rev04.net}
"$PY" post_route4.py ${BASE:-base}.kicad_pcb $r.ses q1_$r.kicad_pcb 2>&1 | grep -E "ses import|saved"
"$PY" evict4.py q1_$r.kicad_pcb q2_$r.kicad_pcb | tail -1
"$PY" clean.py q2_$r.kicad_pcb q3_$r.kicad_pcb | tail -1
cp base.kicad_pro q3_$r.kicad_pro; "$KCLI" pcb drc --format json -o drc_q3_$r.json q3_$r.kicad_pcb >/dev/null 2>&1
"$PY" rmshort.py q3_$r.kicad_pcb drc_q3_$r.json p_$r.kicad_pcb
cp base.kicad_pro p_$r.kicad_pro; "$KCLI" pcb drc --format json -o drc_p_$r.json p_$r.kicad_pcb >/dev/null 2>&1
"$PY" -c "
import json,collections;d=json.load(open('drc_p_$r.json'));c=collections.Counter(v['type'] for v in d['violations'])
print('$r unconnected',len(d['unconnected_items']),dict(c))"
