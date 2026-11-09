"""Exact OpenCascade solids, not decorative browser meshes."""
import math
from dataclasses import dataclass, asdict
from pathlib import Path
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeWire, BRepBuilderAPI_MakePolygon
from OCP.BRepOffsetAPI import BRepOffsetAPI_ThruSections
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepGProp import BRepGProp
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.Bnd import Bnd_Box
from OCP.GProp import GProp_GProps
from OCP.gp import gp_Pnt, gp_Dir, gp_Ax2, gp_Circ
from OCP.TopAbs import TopAbs_SOLID
from OCP.TopExp import TopExp_Explorer
from OCP.StlAPI import StlAPI_Writer
from OCP.STEPControl import STEPControl_Writer, STEPControl_AsIs
from OCP.IFSelect import IFSelect_RetDone
from . import model_spec as spec

NAMES = {'A':'Гладкая бочка','B':'Тактическая','C':'Шестигранная',
         'D':'Спиральная','E':'Гранёная','F':'Руническая','G':'Сегментированная','H':'Коническая'}

class UserError(ValueError):
    pass

@dataclass(frozen=True)
class Settings:
    shape: str = 'A'
    diameter: float = 14
    height: float = 16
    bore: float = 6
    depth: float = .9
    twist: float = 180
    engraving: float = .65

    @classmethod
    def read(cls, data):
        if not isinstance(data,dict) or set(data)-set(cls.__dataclass_fields__):
            raise UserError('Неверный файл проекта или неизвестные настройки.')
        values=asdict(cls())
        values.update(data)
        if not isinstance(values['shape'],str) or values['shape'] not in NAMES:
            raise UserError('Выберите одну из восьми форм.')
        ranges={'diameter':(12,20),'height':(12,24),'bore':(4,10),'depth':(.5,1.3),
                'twist':(90,270),'engraving':(.3,1)}
        for key,(lo,hi) in ranges.items():
            v=values[key]
            if isinstance(v,bool) or not isinstance(v,(float,int)) or not math.isfinite(v) or not lo<=v<=hi:
                label={'diameter':'ширина','height':'высота','bore':'отверстие','depth':'глубина канавок',
                       'twist':'закручивание','engraving':'глубина орнамента'}[key]
                raise UserError(f'Настройка «{label}» должна быть числом от {lo} до {hi}.')
            values[key]=float(v)
        obj=cls(**values)
        if obj.minimum_wall<1.2-1e-6:
            raise UserError('Стенка получается тоньше 1,2 мм. Увеличьте ширину бусины или уменьшите отверстие.')
        return obj

    @property
    def minimum_wall(self):
        r=self.diameter/2; inner=self.bore/2
        limits={'A':.84*r-inner-.5,
                'B':min(r-.85-inner-.5,r-.5-inner-.5),
                'C':math.cos(math.pi/6)*(r-.6)-inner-.5,
                'D':min(r-self.depth-inner,r-.5-self.depth-inner-.5),
                'E':.78*r*math.cos(math.pi/12)-inner-.5,
                'F':min(math.cos(math.pi/6)*r-self.engraving-inner,
                        math.cos(math.pi/6)*(r-.6)-inner-.5),
                'G':min(.85*r-inner,.88*r-inner-.5),
                'H':.8*r-.5-inner-.5}
        return limits[self.shape]

    def parameters(self):
        return {f'{self.shape}_diameter':self.diameter,f'{self.shape}_height':self.height,
                'bore':self.bore,'D_depth':self.depth,'D_twist':self.twist,'F_engrave':self.engraving}

def _wire(section, plane, values):
    ev=lambda x:spec.evaluate(x,values)
    z=ev(section['z'])
    def point(x,y):
        return gp_Pnt(x,y,z) if plane=='XY' else gp_Pnt(x,-z,y)
    if 'r' in section:
        axis=gp_Ax2(point(ev(section['x']),ev(section['y'])),gp_Dir(0,0,1) if plane=='XY' else gp_Dir(0,-1,0))
        edge=BRepBuilderAPI_MakeEdge(gp_Circ(axis,ev(section['r']))).Edge()
        return BRepBuilderAPI_MakeWire(edge).Wire()
    poly=BRepBuilderAPI_MakePolygon()
    for x,y in section['points']:
        poly.Add(point(ev(x),ev(y)))
    poly.Close()
    return poly.Wire()

def solid_count(shape):
    exp=TopExp_Explorer(shape,TopAbs_SOLID); count=0
    while exp.More():
        count+=1; exp.Next()
    return count

def build(settings):
    model=next(x for x in spec.models() if x['key']==settings.shape)
    body=None
    for feature in model['features']:
        loft=BRepOffsetAPI_ThruSections(True,feature['ruled'],1e-7)
        for section in feature['sections']:
            loft.AddWire(_wire(section,feature['plane'],settings.parameters()))
        loft.Build()
        if not loft.IsDone():
            raise UserError('Не удалось построить эту форму. Попробуйте немного изменить размеры.')
        tool=loft.Shape()
        if body is None:
            body=tool
        else:
            cut=BRepAlgoAPI_Cut(body,tool)
            cut.Build()
            if not cut.IsDone():
                raise UserError('Не удалось вырезать канавки. Попробуйте изменить их глубину.')
            body=cut.Shape()
        if not BRepCheck_Analyzer(body).IsValid() or solid_count(body)!=1:
            raise UserError('Сочетание размеров не даёт цельную бусину. Измените размеры.')
    return body

def metrics(body):
    box=Bnd_Box(); BRepBndLib.AddOptimal_s(body,box,False,False)
    a,b,c,d,e,f=box.Get()
    props=GProp_GProps(); BRepGProp.VolumeProperties_s(body,props,1e-7)
    return {'dimensions':[round(d-a,3),round(e-b,3),round(f-c,3)],
            'volume':round(props.Mass(),3),'solids':solid_count(body)}

def export(body, stl_path, step_path):
    mesh=BRepMesh_IncrementalMesh(body,.008,False,.07,False)
    mesh.Perform()
    if not mesh.IsDone():
        raise UserError('Не удалось подготовить поверхность для печати.')
    stl=StlAPI_Writer(); stl.ASCIIMode=False
    if not stl.Write(body,str(stl_path)):
        raise RuntimeError('STL write failed')
    writer=STEPControl_Writer()
    if writer.Transfer(body,STEPControl_AsIs)!=IFSelect_RetDone or writer.Write(str(step_path))!=IFSelect_RetDone:
        raise RuntimeError('STEP write failed')
