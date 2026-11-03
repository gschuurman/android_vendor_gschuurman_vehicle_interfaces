#!/bin/bash
# full placement + pre-route pipeline -> lay/<base>.dsn
set -e
S=/tmp/claude-0/-home-claude/017ccac5-61ec-5bfe-a4f7-4d925f47fef5/scratchpad; cd $S
base=${1:-r6}
KCWD=lay ./kc 'python3 build.py' 2>&1 | grep -E "unplaced|saved"
KCWD=lay ./kc 'python3 hdmi.py board_placed.kicad_pcb board_hdmi.kicad_pcb' 2>&1 | grep TMDS
KCWD=lay ./kc 'python3 dumppads.py board_hdmi.kicad_pcb pads.json' 2>&1 | grep pads
cd lay; python3 powerpoly.py pads.json ppoly.json | grep -v "^   dropped" ; python3 viagrid.py pads.json ppoly.json pvias.json; cd ..
KCWD=lay ./kc 'python3 addpower.py board_hdmi.kicad_pcb board_pwr.kicad_pcb' 2>&1 | grep zones
KCWD=lay ./kc 'python3 fanout.py board_pwr.kicad_pcb board_fan.kicad_pcb' 2>&1 | grep -v Warn | tail -3
KCWD=lay ./kc "python3 prep_route.py board_fan.kicad_pcb $base" 2>&1 | grep dsn
python3 -c "import sys;p='lay/$base.dsn';s=open(p).read();s=s.replace('(layer In1.Cu\n      (type signal)','(layer In1.Cu\n      (type power)');open(p,'w').write(s)"
grep -c "(plane" lay/$base.dsn
