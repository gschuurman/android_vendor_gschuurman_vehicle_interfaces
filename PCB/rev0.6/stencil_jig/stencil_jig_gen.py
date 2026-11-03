# Stencil jig v2 for main board rev 0.6: board and same-size frameless stencil drop into one pocket.
import trimesh, shapely.geometry as sg
OUT='/mnt/project-files/pcb/rev06_jig/'
PCB=100.0; CLR=0.15          # pocket = PCB + 2*CLR
PCB_T=1.60; STENCIL_T=0.12   # pocket depth = board + stencil - 0.03, so the stencil sits a hair proud
DEPTH=PCB_T+STENCIL_T-0.03
FLOOR=3.0; OUTER=140.0; RELIEF=1.2; NOTCH_W=16.0; NOTCH_L=10.0
def ext(poly,z0,h):
    m=trimesh.creation.extrude_polygon(poly,h); m.apply_translation([0,0,z0]); return m
P=PCB+2*CLR
outer=sg.box(-OUTER/2,-OUTER/2,OUTER/2,OUTER/2).buffer(-4).buffer(4,resolution=16)
base=ext(outer,0,FLOOR+DEPTH)
pocket=sg.box(-P/2,-P/2,P/2,P/2)
for sx in (-1,1):            # corner reliefs: square-cornered stencil also fits
    for sy in (-1,1):
        pocket=pocket.union(sg.Point(sx*(P/2-0.3),sy*(P/2-0.3)).buffer(RELIEF,resolution=16))
cuts=[ext(pocket,FLOOR,DEPTH+1)]
for sx in (-1,1):            # finger notches, 1 mm below the pocket floor
    x0,x1=(sx*(P/2-2),sx*(P/2+NOTCH_L))
    cuts.append(ext(sg.box(min(x0,x1),-NOTCH_W/2,max(x0,x1),NOTCH_W/2),FLOOR-1,DEPTH+2))
base=trimesh.boolean.difference([base]+cuts,engine='manifold')
base.export(OUT+'stencil_jig_rev06.stl')
print(base.is_watertight,base.bounds.round(2).tolist(),round(base.volume/1000,1),'cm3')
def h(x,y):
    loc,_,_=base.ray.intersects_location([[x,y,50]],[[0,0,-1]]); return round(max(loc[:,2]),2) if len(loc) else None
for p in [(0,0),(50,50),(50.1,0),(55,0),(0,55),(60,60)]: print(p,h(*p))
