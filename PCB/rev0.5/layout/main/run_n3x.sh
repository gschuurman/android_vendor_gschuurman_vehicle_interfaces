#!/bin/bash
# run_n.sh PREFIX : rev 0.4 three-module main board (b5.py), In1 routable, GND stripped from the DSN
cd "$(dirname "$0")"; P=$1
KCWD=lay ../kc "BOTTOM=0 python3 b5.py g1.kicad_pcb ${P}a.kicad_pcb 0.8 && python3 hd4.py ${P}a.kicad_pcb ${P}h.kicad_pcb && python3 fx1.py ${P}h.kicad_pcb ${P}g.kicad_pcb && python3 fx2.py ${P}g.kicad_pcb ${P}i.kicad_pcb && python3 add5v.py ${P}i.kicad_pcb ${P}m.kicad_pcb && python3 fanmcu.py ${P}m.kicad_pcb ALL ${P}k.kicad_pcb && python3 fanout4.py ${P}k.kicad_pcb ${P}f.kicad_pcb && python3 rmz.py ${P}f.kicad_pcb ${P}j.kicad_pcb all && python3 prep4.py ${P}j.kicad_pcb ${P}1" 2>&1 | grep -E "unplaced|failed|dsn|Error|moved|strip|rror"
sed -i "s/Ω/R/g" ${P}1.dsn; python3 stripgnd.py ${P}1.dsn
[ "$NOFR" = 1 ] && exit 0
for v in 1 2 3; do cp ${P}1.dsn ${P}r$v.dsn; rm -f ${P}r$v.ses
timeout 4000 java -Xmx4g -Djava.awt.headless=true -jar ../tools/freerouting.jar -de ${P}r$v.dsn -do ${P}r$v.ses --gui.enabled=false --router.max_passes=400 --router.optimizer.max_passes=0 --router.fanout.enabled=false --router.job_timeout=00:55:00 > fr_${P}r$v.log 2>&1 &
done; wait
for v in 1 2 3; do ls -la ${P}r$v.ses; grep -o "pass #[0-9]* .*(\([0-9]* unrouted\)" fr_${P}r$v.log | sed 's/on board.*score of//' | tail -1; done
