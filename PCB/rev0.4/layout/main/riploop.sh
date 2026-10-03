#!/bin/bash
# riploop.sh start rounds : plain bridge pass, then a low-rip bridge pass, repeated; keeps the board with fewest unconnected as best.kicad_pcb
export MSYS_NO_PATHCONV=1; PY="/c/Program Files/KiCad/10.0/bin/python.exe"; KCLI="/c/Program Files/KiCad/10.0/bin/kicad-cli.exe"
cur=$1; best=999
for r in $(seq 1 $2); do
  CL=0.18 ./bridgeall.sh $cur rl$r > rl$r.log 2>&1; cur=rl$r; n=$(tail -1 rl$r.log | awk '{print $3}')
  echo "round $r plain -> $n"; if [ "$n" -lt "$best" ]; then best=$n; cp $cur.kicad_pcb best.kicad_pcb; fi; [ "$n" = 0 ] && break
  RIP=1 SOFT=${SOFT:-3000} CL=0.18 BIGONLY=1 ./bridgeall.sh $cur rr$r > rr$r.log 2>&1; cur=rr$r; n=$(tail -1 rr$r.log | awk '{print $3}')
  echo "round $r rip -> $n"; if [ "$n" -lt "$best" ]; then best=$n; cp $cur.kicad_pcb best.kicad_pcb; fi; [ "$n" = 0 ] && break
done
echo "best $best"
