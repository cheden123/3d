from dataclasses import asdict
import io, json, zipfile
import pytest
import trimesh
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
from OCP.STEPControl import STEPControl_Reader
from OCP.IFSelect import IFSelect_RetDone
from bead_studio.cad import Settings,UserError,build,metrics,export,solid_count
from bead_studio.server import fusion_archive

@pytest.mark.parametrize('shape',list('ABCDEFGH'))
@pytest.mark.parametrize('changed',[False,True])
def test_real_geometry_and_exports(shape,changed,tmp_path):
    s=Settings.read({'shape':shape,**({'diameter':15,'height':19,'bore':6.4,'twist':230,'depth':1.1} if changed else {})})
    body=build(s);info=metrics(body)
    assert info['solids']==1 and abs(info['dimensions'][2]-s.height)<.001
    assert info['volume']>0
    bore=BRepPrimAPI_MakeCylinder(s.bore/2-.005,s.height).Shape()
    inside=BRepAlgoAPI_Common(body,bore).Shape()
    props=GProp_GProps();BRepGProp.VolumeProperties_s(inside,props)
    assert abs(props.Mass())<1e-6
    stl=tmp_path/'part.stl';step=tmp_path/'part.step'
    export(body,stl,step)
    mesh=trimesh.load_mesh(stl)
    assert mesh.is_volume and mesh.is_watertight and mesh.is_winding_consistent
    assert len(mesh.split())==1 and mesh.euler_number==0
    assert abs(mesh.volume-info['volume'])/info['volume']<.003
    reader=STEPControl_Reader();assert reader.ReadFile(str(step))==IFSelect_RetDone
    reader.TransferRoots();loaded=reader.OneShape()
    assert solid_count(loaded)==1
    assert abs(metrics(loaded)['volume']-info['volume'])<.01

@pytest.mark.parametrize('bad',[{'shape':'Z'},{'height':float('nan')},{'bore':True},{'twist':float('inf')},
                                {'unknown':5},{'diameter':1},{'shape':[]},{'diameter':12,'bore':10}])
def test_bad_settings(bad):
    with pytest.raises(UserError):Settings.read(bad)

def test_fusion_project_contains_selected_dimensions():
    s=Settings.read({'shape':'F','height':20,'bore':6.4})
    with zipfile.ZipFile(io.BytesIO(fusion_archive(s))) as z:
        config=json.loads(z.read('Paracord550/selection.json'))
        assert config['shape']=='F' and config['values']['F_height']==20
        assert config['values']['bore']==6.4
        compile(z.read('Paracord550/Paracord550.py'),'fusion.py','exec')
        assert 'def models()' in z.read('Paracord550/model_spec.py').decode()
