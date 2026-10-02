import re
TOK=re.compile(r'\s*(\(|\)|"(?:[^"\\]|\\.)*"|[^\s()"]+)')
class Sym(str): pass
def parse(s):
    pos=0; stack=[[]]
    for m in TOK.finditer(s):
        t=m.group(1)
        if t=='(': stack.append([])
        elif t==')':
            x=stack.pop(); stack[-1].append(x)
        elif t.startswith('"'): stack[-1].append(t[1:-1].replace('\\"','"').replace('\\\\','\\'))
        else: stack[-1].append(Sym(t))
    return stack[0]
def dump(x,ind=0):
    if isinstance(x,list):
        if not x: return '()'
        simple=all(not isinstance(e,list) for e in x)
        if simple: return '('+' '.join(dump(e) for e in x)+')'
        out='('+dump(x[0])
        for e in x[1:]:
            out+='\n'+'  '*(ind+1)+dump(e,ind+1)
        return out+')'
    if isinstance(x,Sym): return str(x)
    if isinstance(x,(int,float)): 
        return ('%.4f'%x).rstrip('0').rstrip('.') if isinstance(x,float) else str(x)
    return '"'+str(x).replace('\\','\\\\').replace('"','\\"')+'"'
_cache={}
def lib(name):
    if name not in _cache:
        _cache[name]=parse(open(f'/usr/share/kicad/symbols/{name}.kicad_sym').read())[0]
    return _cache[name]
def find_sym(libname,sym):
    for e in lib(libname):
        if isinstance(e,list) and e and e[0]=='symbol' and e[1]==sym: return e
    raise KeyError(sym)
def pins_of(symdef):
    res=[]
    def walk(x):
        for e in x:
            if isinstance(e,list) and e:
                if e[0]=='pin':
                    at=[q for q in e if isinstance(q,list) and q[0]=='at'][0]
                    nm=[q for q in e if isinstance(q,list) and q[0]=='name'][0][1]
                    nu=[q for q in e if isinstance(q,list) and q[0]=='number'][0][1]
                    res.append((nu,nm,float(at[1]),float(at[2]),float(at[3]) if len(at)>3 else 0.0,str(e[1])))
                elif e[0]=='symbol': walk(e)
    walk(symdef); return res
