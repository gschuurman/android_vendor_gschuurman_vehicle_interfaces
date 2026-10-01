#!/bin/bash
# simp.sh in out eps : simplify with clearance-revert loop
cd "$(dirname "$0")"; echo '[]' > skip_$2.json
KCWD=lay ../kc "python3 simplify.py $1.kicad_pcb $2.kicad_pcb $3" 2>&1 | grep chains; cp r9.kicad_pro $2.kicad_pro
for i in 1 2 3 4 5; do
  KCWD=lay ../kc "kicad-cli pcb drc --format json -o drc_$2.json $2.kicad_pcb" >/dev/null 2>&1
  n=$(python3 - $2 <<'PY'
import json,collections,sys
o=sys.argv[1]; m=json.load(open(o+'.kicad_pcb.map.json')); d=json.load(open('drc_'+o+'.json')); sk=set(json.load(open('skip_'+o+'.json')))
bad={it['uuid'] for v in d['violations'] if v['type'] in('clearance','shorting_items','hole_clearance','tracks_crossing') for it in v['items']}
nb=0
for c in m:
    if bad & set(c['new']): sk.add(c['first']); nb+=1
json.dump(sorted(sk),open('skip_'+o+'.json','w')); print(len(d['unconnected_items'])+nb)
PY
)
  echo "pass $i bad $n"; [ "$n" = 0 ] && break
  KCWD=lay ../kc "python3 simplify.py $1.kicad_pcb $2.kicad_pcb $3 skip_$2.json" 2>&1 | grep chains
done
