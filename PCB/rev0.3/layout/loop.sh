#!/bin/bash
# loop.sh start rounds VMAX : repeated dump -> maze2 -> apply -> DRC; boards named start_1, start_2 ...
cd "$(dirname "$0")"; cur=$1
for r in $(seq 1 $2); do
  nx=${1}_$r
  KCWD=lay ../kc "python3 dumpstate.py $cur.kicad_pcb drc_$cur.json st_$cur.json" 2>&1 | grep items
  NARROW=/VSYS_IN,/+5V_SYS STEP=1 VMAX=$3 timeout 1800 python3 maze2.py st_$cur.json m2_$cur.json > m2_$cur.log 2>&1
  tail -1 m2_$cur.log
  KCWD=lay ../kc "python3 apply2.py $cur.kicad_pcb m2_$cur.json $nx.kicad_pcb" 2>&1 | tail -1
  cp r9.kicad_pro $nx.kicad_pro
  KCWD=lay ../kc "kicad-cli pcb drc --format json -o drc_$nx.json $nx.kicad_pcb" >/dev/null 2>&1
  n=$(python3 -c "import json;print(len(json.load(open('drc_$nx.json'))['unconnected_items']))"); echo "round $r -> $nx unconnected $n"
  cur=$nx; [ "$n" = 0 ] && break
done
