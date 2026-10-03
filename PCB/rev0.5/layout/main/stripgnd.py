"""stripgnd.py file.dsn : drop the GND net from the DSN network and class lists (GND joins through fan-out vias and pours)."""
import re, sys
s = open(sys.argv[1]).read()
i = s.index('\n    (net GND\n'); j = s.index('\n    )', i + 5) + 6
s = s[:i] + s[j:]
s = re.sub(r'(\(class [^\n]*?) GND(?=[ \n)])', r'\1', s)
s = re.sub(r"\n(\s+)GND ", r"\n\1", s); s = re.sub(r"\n\s+GND\n", "\n", s)
open(sys.argv[1], 'w').write(s); print('GND stripped', s.count('(net GND'))
