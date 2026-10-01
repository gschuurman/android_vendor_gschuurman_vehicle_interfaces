#!/bin/bash
# finish.sh in_base out_base : maze (hard) -> apply -> maze2 (rip-up) -> apply -> DRC
S=/tmp/claude-0/-home-claude/017ccac5-61ec-5bfe-a4f7-4d925f47fef5/scratchpad; cd $S
i=$1; o=$2
cp lay/r9.kicad_pro lay/$i.kicad_pro 2>/dev/null
KCWD=lay ./kc "kicad-cli pcb drc --format json -o drc_$i.json $i.kicad_pcb" | grep unconn
KCWD=lay ./kc "python3 dumpstate.py $i.kicad_pcb drc_$i.json st_$i.json" 2>&1 | grep items
(cd lay; python3 maze.py st_$i.json mz_$i.json > mz_$i.log 2>&1; grep "^routed" mz_$i.log)
KCWD=lay ./kc "python3 addtracks.py $i.kicad_pcb mz_$i.json ${o}a.kicad_pcb" 2>&1 | grep added
cp lay/r9.kicad_pro lay/${o}a.kicad_pro
KCWD=lay ./kc "kicad-cli pcb drc --format json -o drc_${o}a.json ${o}a.kicad_pcb" | grep unconn
KCWD=lay ./kc "python3 dumpstate.py ${o}a.kicad_pcb drc_${o}a.json st_${o}a.json" 2>&1 | grep items
(cd lay; python3 maze2.py st_${o}a.json m2_$o.json > m2_$o.log 2>&1; tail -1 m2_$o.log | cut -c1-600)
KCWD=lay ./kc "python3 apply2.py ${o}a.kicad_pcb m2_$o.json $o.kicad_pcb" 2>&1 | grep removed
cp lay/r9.kicad_pro lay/$o.kicad_pro
KCWD=lay ./kc "kicad-cli pcb drc --format json -o drc_$o.json $o.kicad_pcb" | grep unconn
python3 -c "
import json,collections;d=json.load(open('lay/drc_$o.json'))
print(collections.Counter((v['type']) for v in d['violations'] if v['severity']=='error'))"
