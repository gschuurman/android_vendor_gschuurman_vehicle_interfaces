#!/bin/bash
# bridgeall.sh in out : run bridge.py once for each unconnected pair in a fresh DRC of `in` (no rip-up), then DRC `out`
export MSYS_NO_PATHCONV=1
PY="/c/Program Files/KiCad/10.0/bin/python.exe"; KCLI="/c/Program Files/KiCad/10.0/bin/kicad-cli.exe"
cp $1.kicad_pcb $2.kicad_pcb; cp base.kicad_pro $2.kicad_pro
"$KCLI" pcb drc --format json -o drc_$2_in.json $2.kicad_pcb >/dev/null 2>&1
"$PY" -c "
import json
for u in json.load(open('drc_$2_in.json'))['unconnected_items']:
    a, c = u['items'][0], u['items'][1]; net = a['description'].split('[')[1].split(']')[0]
    xs = (a['pos']['x'], c['pos']['x']); ys = (a['pos']['y'], c['pos']['y'])
    print(net, a['pos']['x'], a['pos']['y'], max(0, min(xs) - 5), max(0, min(ys) - 5), min(100, max(xs) + 5), min(100, max(ys) + 5))
" > pairs_$2.txt
while read net x y x0 y0 x1 y1; do
  echo "== $net"; CL=${CL:-0.15} HW=${HW:-0.1} "$PY" withlib.py bridge.py $2.kicad_pcb $2.kicad_pcb "$net" $x $y $x0 $y0 $x1 $y1 2>&1 | grep -E "path|no path|rror"
done < pairs_$2.txt
"$KCLI" pcb drc --format json -o drc_$2.json $2.kicad_pcb >/dev/null 2>&1
"$PY" -c "
import json,collections;d=json.load(open('drc_$2.json'));print('$2 unconnected',len(d['unconnected_items']),dict(collections.Counter(v['type'] for v in d['violations'])))"
