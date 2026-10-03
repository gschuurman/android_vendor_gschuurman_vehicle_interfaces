import re
def load(path):
    s = open(path).read()
    nets = {}; pads = {}
    for blk in re.split(r'\n\t\t\(net\n', s.split('(nets', 1)[1])[1:]:
        nm = re.search(r'\(name "([^"]+)"\)', blk).group(1)
        for r, p in re.findall(r'\(ref "([^"]+)"\)\s*\(pin "([^"]+)"\)', blk):
            nets.setdefault(nm, []).append((r, p)); pads.setdefault(r, {})[p] = nm
    return nets, pads
def comps(path):
    s = open(path).read().split('(nets', 1)[0]
    out = {}
    for blk in re.split(r'\(comp\s', s)[1:]:
        r = re.search(r'\(ref "([^"]+)"\)', blk).group(1)
        fp = re.search(r'\(footprint "([^"]+)"\)', blk)
        out[r] = dict(fp=fp.group(1) if fp else '', val=re.search(r'\(value "([^"]*)"\)', blk).group(1),
                      uuid=[t for t in re.findall(r'\(tstamps "([^"]+)"\)', blk) if t != '/'][0])
    return out
