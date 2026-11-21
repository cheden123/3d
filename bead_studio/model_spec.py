"""Shared, millimetre-based geometry specification for Fusion and OpenCascade.
No CAD dependencies. Expressions are authored here, never accepted from users.
"""
import math
from collections import namedtuple

Preset = namedtuple('Preset', 'slug name description group diameter height')
PRESETS = {
    'A': Preset('Smooth_barrel', 'Гладкая бочка', 'Плавные линии', 'basic', 14, 16),
    'B': Preset('Tactical_fluted', 'Тактическая', '10 канавок', 'textured', 14, 16),
    'C': Preset('Hexagonal', 'Шестигранная', '6 граней', 'basic', 14, 16),
    'D': Preset('Helical_grooves', 'Спиральная', '3 винтовые канавки', 'textured', 14, 16),
    'E': Preset('Faceted', 'Гранёная', '12 граней', 'basic', 14, 16),
    'F': Preset('Runic', 'Руническая', 'Углублённый знак', 'textured', 14, 18),
    'G': Preset('Segmented', 'Сегментированная', '4 кольца', 'textured', 14, 16),
    'H': Preset('Conical', 'Коническая', 'Сужение к торцу', 'basic', 14, 16),
    'I': Preset('Spool', 'Шпулька', 'Широкие края', 'shaped', 16, 16),
    'J': Preset('Olive', 'Олива', 'Вытянутый овал', 'shaped', 14, 20),
    'K': Preset('Disc', 'Диск', 'Низкая и широкая', 'shaped', 18, 12),
    'L': Preset('Bicone', 'Биконус', 'Два встречных конуса', 'shaped', 16, 18),
    'M': Preset('Octagonal', 'Восьмигранная', '8 плоских сторон', 'basic', 15, 16),
    'N': Preset('Square', 'Квадратная', '4 грани со скосами', 'basic', 16, 16),
    'O': Preset('Double_barrel', 'Двойная бочка', 'Два плавных выступа', 'shaped', 15, 20),
    'P': Preset('Crown', 'Корона', 'Зубчатый верх', 'textured', 16, 16),
    'Q': Preset('Star', 'Звезда', '6 лучей вдоль корпуса', 'textured', 16, 16),
    'R': Preset('Wave', 'Волна', 'Плавные кольцевые волны', 'textured', 15, 19),
    'S': Preset('Crystal', 'Кристалл', '5 граней и острый пояс', 'shaped', 16, 18),
    'T': Preset('Steps', 'Ступени', '3 яруса с переходами', 'shaped', 16, 16),
}

# Each section uses a height fraction and a radius fraction. Crown sections
# have a third fraction for the radial valleys between the teeth.
ROUND_PROFILES = {
    'I': (True, [(0,.94),(.035,1),(.10,1),(.29,.76),(.71,.76),(.90,1),(.965,1),(1,.94)]),
    'J': (False, [(0,.72),(.12,.86),(.30,.97),(.50,1),(.70,.97),(.88,.86),(1,.72)]),
    'K': (True, [(0,.83),(.16,.95),(.30,1),(.70,1),(.84,.95),(1,.83)]),
    'L': (True, [(0,.73),(.47,1),(.53,1),(1,.73)]),
    'O': (False, [(0,.84),(.10,.93),(.25,1),(.37,.92),(.50,.80),(.63,.92),(.75,1),(.90,.93),(1,.84)]),
    'R': (False, [(0,.89),(.09,.97),(.17,1),(.27,.94),(.34,.86),(.44,.95),(.50,1),
                  (.56,.95),(.66,.86),(.73,.94),(.83,1),(.91,.97),(1,.89)]),
    'T': (True, [(0,.94),(.035,1),(.33,1),(.41,.90),(.59,.90),(.67,.80),(.96,.80),(1,.76)]),
}
REGULAR_PROFILES = {
    'M': (8, [(0,.94),(.045,1),(.955,1),(1,.94)]),
    'S': (5, [(0,.86),(.38,.92),(.65,1),(1,.86)]),
}
TOOTHED_PROFILES = {
    'P': (8, [(0,.91,.88),(.06,.97,.94),(.64,.97,.94),(.78,1,.88),(1,.98,.77)]),
    'Q': (6, [(0,.94,.68),(.06,1,.68),(.94,1,.68),(1,.94,.68)]),
}

PARAMETERS = {
    'bore': (6.0, 'mm', 'Through bore; nominal diameter'),
    'lead': (0.5, 'mm', '45 degree lead-in at both bore entrances'),
    'B_flute_radius': (0.85, 'mm', 'Radius of the ten axial flute cutters'),
    'D_depth': (0.9, 'mm', 'Radial depth of three helical grooves'),
    'D_twist': (180, 'deg', 'Total rotation of helical grooves'),
    'F_engrave': (0.65, 'mm', 'Depth of geometric rune engraving'),
}
for key, preset in PRESETS.items():
    PARAMETERS[key+'_diameter'] = (preset.diameter, 'mm', 'Maximum diameter / polygon circumdiameter')
    PARAMETERS[key+'_height'] = (preset.height, 'mm', 'Axial length')

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

def new_outer(key, height, radius):
    name = PRESETS[key].slug
    if key in ROUND_PROFILES:
        ruled, sections = ROUND_PROFILES[key]
        return loft(name, [circle(f'{height}*{z}', f'{radius}*{r}') for z, r in sections], ruled=ruled)
    if key in REGULAR_PROFILES:
        sides, sections = REGULAR_PROFILES[key]
        return loft(name, [regular(f'{height}*{z}', f'{radius}*{r}', sides) for z, r in sections])
    if key == 'N':
        # A chamfered square with alternating short corner cuts and long sides.
        corners = [(.55,.835),(-.55,.835),(-.835,.55),(-.835,-.55),
                   (-.55,-.835),(.55,-.835),(.835,-.55),(.835,.55)]
        return loft(name, [polygon(f'{height}*{z}', [(f'{radius}*{scale*x:.9g}', f'{radius}*{scale*y:.9g}')
                     for x,y in corners]) for z,scale in [(0,.94),(.045,1),(.955,1),(1,.94)]])
    teeth, sections = TOOTHED_PROFILES[key]
    profiles = []
    for z, tip, valley in sections:
        points = []
        for index in range(teeth*2):
            angle = index*180/teeth
            scale = valley if index%2 else tip
            points.append((f'{radius}*{scale}*cos({angle:g} deg)', f'{radius}*{scale}*sin({angle:g} deg)'))
        profiles.append(polygon(f'{height}*{z}', points))
    return loft(name, profiles)

def new_minimum_radius_fraction(key):
    """Lower bounds for the distance from the bore axis to the outside wall."""
    if key in ROUND_PROFILES:
        ruled, sections = ROUND_PROFILES[key]
        # Allow for the smooth transition between sampled radii.
        return min(radius for _, radius in sections) - (0 if ruled else .03)
    if key in REGULAR_PROFILES:
        sides, sections = REGULAR_PROFILES[key]
        return min(radius for _, radius in sections)*math.cos(math.pi/sides)
    if key == 'N':
        return .94*.835
    teeth, sections = TOOTHED_PROFILES[key]
    # The closest point on each edge is no less than the smaller radius
    # projected onto the bisector of its two neighbouring vertices.
    return min(min(tip,valley) for _,tip,valley in sections)*math.cos(math.pi/(2*teeth))

def models():
    result=[]
    for key,preset in PRESETS.items():
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
        elif key in 'BD':
            outer=loft('Chamfered_shell', [circle(z,rr) for z,rr in
                      [('0 mm',f'{r}-0.5 mm'),('0.5 mm',r),
                       (f'{h}-0.5 mm',r),(h,f'{r}-0.5 mm')]])
        else:
            outer=new_outer(key,h,r)
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
        result.append(dict(key=key, name=key+'_'+preset.slug, features=features))
    return result
