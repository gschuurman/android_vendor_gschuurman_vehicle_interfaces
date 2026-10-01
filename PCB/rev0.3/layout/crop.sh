#!/bin/bash
# crop.sh board layers x0 y0 x1 y1 out.png [width]
KCWD=lay ../kc "kicad-cli pcb export svg --mode-single --exclude-drawing-sheet --layers $2 -o /w/lay/crop.svg $1 >/dev/null 2>&1"
python3 - "$3" "$4" "$5" "$6" "$7" "${8:-1600}" <<'PY'
import re,sys,cairosvg
x0,y0,x1,y1=map(float,sys.argv[1:5]); out=sys.argv[5]; w=int(sys.argv[6])
s=open('crop.svg').read()
s=re.sub(r'viewBox="[^"]+"',f'viewBox="{x0} {y0} {x1-x0} {y1-y0}"',s,1)
s=re.sub(r'width="[^"]+"',f'width="{x1-x0}mm"',s,1); s=re.sub(r'height="[^"]+"',f'height="{y1-y0}mm"',s,1)
cairosvg.svg2png(bytestring=s.encode(),write_to=out,output_width=w,background_color='white')
PY
