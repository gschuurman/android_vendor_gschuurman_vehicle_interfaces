#!/bin/bash
# hd.sh in ops out : apply hand ops, DRC, summarize
cd "$(dirname "$0")"
KCWD=lay ../kc "python3 hand.py $1.kicad_pcb $2 $3.kicad_pcb" 2>&1 | grep -E "NOT FOUND|ok|Error" 
cp r9.kicad_pro $3.kicad_pro
KCWD=lay ../kc "kicad-cli pcb drc --format json -o drc_$3.json $3.kicad_pcb" >/dev/null 2>&1
python3 - drc_$3.json <<'PY'
import json,collections,sys
d=json.load(open(sys.argv[1]))
print(len(d['unconnected_items']),collections.Counter(v['type'] for v in d['violations']))
for v in d['violations']:
    if v['type'] not in('starved_thermal','silk_overlap','silk_over_copper','silk_edge_clearance','text_height','text_thickness'): print(v['type'],v['description'][:60],[i['description'][:50]+' @%.2f,%.2f'%(i['pos']['x'],i['pos']['y']) for i in v['items']])
for u in d['unconnected_items']: print('U',[i['description'][:45]+' @%.2f,%.2f'%(i['pos']['x'],i['pos']['y']) for i in u['items']])
PY
