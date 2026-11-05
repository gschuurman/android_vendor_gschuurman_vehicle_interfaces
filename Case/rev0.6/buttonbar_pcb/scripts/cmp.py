import re,pcbnew,sys
t=open('/tmp/x.net').read()
sch={}
for m in re.finditer(r'\(net \(code "?\d+"?\) \(name "([^"]+)"\)(.*?)\)\s*(?=\(net |\)\s*\)\s*$)',t,re.S):
    nodes=frozenset(re.findall(r'\(ref "([^"]+)"\) \(pin "([^"]+)"',m.group(2)))
    sch[m.group(1)]=nodes
b=pcbnew.LoadBoard('buttonbar/buttonbar.kicad_pcb')
pcb={}
for fp in b.GetFootprints():
    for p in fp.Pads():
        pcb.setdefault(p.GetNetname(),set()).add((fp.GetReference(),p.GetNumber()))
A=set(sch.values()); B=set(frozenset(v) for v in pcb.values())
print(len(A),len(B),"match" if A==B else "DIFF")
for x in A^B: print(sorted(x))
