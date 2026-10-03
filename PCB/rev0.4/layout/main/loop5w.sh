#!/bin/bash
# loop5w.sh start rounds VMAX : loop5.sh for a native KiCad 10 install (Windows Git Bash) instead of the Docker image.
# Run in the work folder holding the boards and these scripts. PY is KiCad's bundled Python, KCLI its kicad-cli;
# maze2b.py runs through withlib.py, which puts PYLIB (scipy, shapely: pip install --target) on sys.path.
PY=${PY:-"/c/Program Files/KiCad/10.0/bin/python.exe"}; KCLI=${KCLI:-"/c/Program Files/KiCad/10.0/bin/kicad-cli.exe"}
PRO=${PRO:-base.kicad_pro}; cur=$1
for r in $(seq 1 $2); do
  nx=${1}_$r
  "$PY" dumpstate.py $cur.kicad_pcb drc_$cur.json st_$cur.json 2>&1 | grep items
  LAYERS=F,In1,In2,B NARROW=/VSYS_IN,/+5V_SYS STEP=1 VMAX=$3 MAZE_T=${MAZE_T:-3000} timeout ${MAZE_KILL:-5400} "$PY" withlib.py maze2b.py st_$cur.json m2_$cur.json > m2_$cur.log 2>&1
  tail -1 m2_$cur.log
  "$PY" apply2.py $cur.kicad_pcb m2_$cur.json $nx.kicad_pcb 2>&1 | tail -1
  cp $PRO $nx.kicad_pro
  "$KCLI" pcb drc --format json -o drc_$nx.json $nx.kicad_pcb >/dev/null 2>&1
  n=$("$PY" -c "import json;print(len(json.load(open('drc_$nx.json'))['unconnected_items']))"); echo "round $r -> $nx unconnected $n"
  cur=$nx; [ "$n" = 0 ] && break
done
