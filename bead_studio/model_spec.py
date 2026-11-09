"""Shared, millimetre-based geometry specification for Fusion and OpenCascade.
No CAD dependencies. Expressions are authored here, never accepted from users.
"""
import math

PARAMETERS = {
    'bore': (6.0, 'mm', 'Through bore; nominal diameter'),
    'lead': (0.5, 'mm', '45 degree lead-in at both bore entrances'),
    'B_flute_radius': (0.85, 'mm', 'Radius of the ten axial flute cutters'),
    'D_depth': (0.9, 'mm', 'Radial depth of three helical grooves'),
    'D_twist': (180, 'deg', 'Total rotation of helical grooves'),
    'F_engrave': (0.65, 'mm', 'Depth of geometric rune engraving'),
}
for key, diameter, height in [('A',14,16),('B',14,16),('C',14,16),
                               ('D',14,16),('E',14,16),('F',14,18),
                               ('G',14,16),('H',14,16)]:
    PARAMETERS[key+'_diameter'] = (diameter, 'mm', 'Maximum diameter / polygon circumdiameter')
    PARAMETERS[key+'_height'] = (height, 'mm', 'Axial length')

def evaluate(expression, values=None):
    env = {k:math.radians(v[0]) if v[1]=='deg' else v[0] for k,v in PARAMETERS.items()}
    if values:
        env.update({k:math.radians(v) if PARAMETERS[k][1]=='deg' else v for k,v in values.items()})
    env.update(sin=math.sin, cos=math.cos, pi=math.pi)
    return float(eval(str(expression).replace(' deg','*pi/180').replace(' mm',''),
                      {'__builtins__': {}}, env))

def circle(z, r, x='0 mm', y='0 mm'):
    return dict(z=z, r=r, x=x, y=y)

def polygon(z, points):
    return dict(z=z, points=points)

def regular(z, r, n, phase=0):
    return polygon(z, [(f'({r}) * cos({phase+i*360/n:g} deg)',
                         f'({r}) * sin({phase+i*360/n:g} deg)') for i in range(n)])

def loft(name, sections, operation='new', ruled=True, plane='XY'):
    return dict(name=name, sections=sections, operation=operation, ruled=ruled, plane=plane)

def models():
    result=[]
    names=['Smooth_barrel','Tactical_fluted','Hexagonal','Helical_grooves',
           'Faceted','Runic','Segmented','Conical']
    for key,name in zip('ABCDEFGH', names):
        d=key+'_diameter'; h=key+'_height'; r=f'{d}/2'
        if key=='A':
            outer=loft('Barrel', [circle(f'{h}*{z}',f'{r}*{f}') for z,f in
                      [(0,.84),(.15,.94),(.5,1),(.85,.94),(1,.84)]], ruled=False)
        elif key in 'CF':
            outer=loft('Hexagonal_shell', [regular(z,rr,6) for z,rr in
                [('0 mm',f'{r}-0.6 mm'),('0.6 mm',r),(f'{h}-0.6 mm',r),(h,f'{r}-0.6 mm')]])
        elif key=='E':
            outer=loft('Twelve_facets', [regular(f'{h}*{z}',f'({r})*{f}',12,15)
                          for z,f in [(0,.78),(.25,1),(.75,1),(1,.78)]])
        elif key=='G':
            zr=[(0,.88),(.04,1)]
            for c in [.25,.5,.75]:
                zr.extend([(c-.06,1),(c-.02,.85),(c+.02,.85),(c+.06,1)])
            zr.extend([(.96,1),(1,.88)])
            outer=loft('Four_segments', [circle(f'{h}*{z}',f'({r})*{f}') for z,f in zr])
        elif key=='H':
            outer=loft('Cone', [circle(z,rr) for z,rr in
                      [('0 mm',f'{r}-0.5 mm'),('0.5 mm',r),
                       (f'{h}-0.5 mm',f'{r}*0.80'),(h,f'{r}*0.80-0.5 mm')]])
        else:
            outer=loft('Chamfered_shell', [circle(z,rr) for z,rr in
                      [('0 mm',f'{r}-0.5 mm'),('0.5 mm',r),
                       (f'{h}-0.5 mm',r),(h,f'{r}-0.5 mm')]])
        features=[outer]
        if key=='B':
            for i in range(10):
                a=i*36+9
                x=f'({r})*cos({a} deg)'; y=f'({r})*sin({a} deg)'
                features.append(loft(f'Axial_flute_{i+1}',
                    [circle(z,'B_flute_radius',x,y) for z in ['0 mm',h]],'cut'))
        if key=='D':
            for j in range(3):
                sections=[]
                for i in range(13):
                    a=f'({j*120+7} deg + D_twist*{i}/12)'
                    points=[(f'({rr})*cos({aa})', f'({rr})*sin({aa})') for rr,aa in
                            [(f'{r}-D_depth',a),(f'{r}+1.5 mm',f'{a}+10 deg'),
                             (f'{r}+1.5 mm',f'{a}-10 deg')]]
                    sections.append(polygon(f'{h}*{i}/12',points))
                features.append(loft(f'Helix_{j+1}',sections,'cut',False))
        if key=='F':
            # Three rectangular strokes, cut separately so overlapping arms are robust.
            strokes=[ [(-.22,.24),(-.10,.24),(-.10,.76),(-.22,.76)],
                      [(-.14,.66),(.20,.53),(.23,.60),(-.11,.73)],
                      [(-.14,.47),(.20,.34),(.23,.41),(-.11,.54)] ]
            # XZ plane has normal -Y. Positive offset puts engraving on the -Y flat.
            for i,pts in enumerate(strokes):
                p=[(f'{d}*{x}',f'{h}*{z}') for x,z in pts]
                sections=[polygon(f'{d}/2*cos(30 deg)+0.05 mm',p),
                          polygon(f'{d}/2*cos(30 deg)-F_engrave',p)]
                features.append(loft(f'Rune_stroke_{i+1}',sections,'cut',True,'XZ'))
        features.append(loft('Through_bore_and_lead_ins',[
            circle('0 mm','bore/2+lead'),circle('lead','bore/2'),
            circle(f'{h}-lead','bore/2'),circle(h,'bore/2+lead')],'cut'))
        result.append(dict(key=key, name=key+'_'+name, features=features))
    return result
