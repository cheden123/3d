"""Run inside Autodesk Fusion: Utilities > Scripts and Add-Ins > Scripts.
Creates a NEW document; all sketches, section positions and diameters reference
user parameters. No external Python libraries or imported mesh geometry.
"""
import os
import sys
import json
import traceback
import importlib.util
import adsk.core
import adsk.fusion

HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location('paracord_model_spec', os.path.join(HERE,'model_spec.py'))
spec = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(spec)
SELECTION = None
config_path = os.path.join(HERE, 'selection.json')
if os.path.isfile(config_path):
    with open(config_path, encoding='utf-8') as f:
        config = json.load(f)
    SELECTION = config['shape']
    for name, value in config['values'].items():
        _, unit, comment = spec.PARAMETERS[name]
        spec.PARAMETERS[name] = (value, unit, comment)
P = adsk.core.Point3D.create
V = adsk.core.ValueInput.createByString

def coordinate_constraints(sketch, datum, point, x, y):
    """Positive distances from a fixed (-50,-50) mm datum allow signed coordinates
    to cross zero when the helix angle changes, without flipping dimension branches.
    The fixed datum is construction reference only, never part of a profile.
    """
    for expr, orientation in [
        (x,adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation),
        (y,adsk.fusion.DimensionOrientations.VerticalDimensionOrientation)]:
        dim=sketch.sketchDimensions.addDistanceDimension(datum,point,orientation,
                   P(point.geometry.x+0.15,point.geometry.y+0.15,0))
        dim.parameter.expression=f'50 mm + ({expr})'

def section(comp, data, plane_type, label):
    base=comp.xYConstructionPlane if plane_type=='XY' else comp.xZConstructionPlane
    pin=comp.constructionPlanes.createInput()
    if not pin.setByOffset(base,V(data['z'])):
        raise RuntimeError('Cannot define section plane: '+label)
    plane=comp.constructionPlanes.add(pin); plane.name=label+'_plane'
    sk=comp.sketches.add(plane); sk.name=label
    datum=sk.sketchPoints.add(P(-5,-5,0)); datum.isFixed=True
    if 'r' in data:
        x,y=data['x'],data['y']
        c=sk.sketchCurves.sketchCircles.addByCenterRadius(
            P(spec.evaluate(x)/10,spec.evaluate(y)/10,0),spec.evaluate(data['r'])/10)
        if abs(spec.evaluate(x))+abs(spec.evaluate(y))<1e-9:
            sk.geometricConstraints.addCoincident(c.centerSketchPoint,sk.originPoint)
        else:
            coordinate_constraints(sk,datum,c.centerSketchPoint,x,y)
        dim=sk.sketchDimensions.addDiameterDimension(c,P(spec.evaluate(data['r'])/10,0.15,0))
        dim.parameter.expression='2*('+data['r']+')'
    else:
        pts=data['points']; lines=[]
        for i,(x,y) in enumerate(pts):
            a=P(spec.evaluate(x)/10,spec.evaluate(y)/10,0)
            nx,ny=pts[(i+1)%len(pts)]
            b=P(spec.evaluate(nx)/10,spec.evaluate(ny)/10,0)
            if i==0:
                line=sk.sketchCurves.sketchLines.addByTwoPoints(a,b)
            else:
                end=lines[0].startSketchPoint if i==len(pts)-1 else b
                line=sk.sketchCurves.sketchLines.addByTwoPoints(lines[-1].endSketchPoint,end)
            lines.append(line)
        for line,(x,y) in zip(lines,pts):
            coordinate_constraints(sk,datum,line.startSketchPoint,x,y)
    if sk.profiles.count!=1:
        raise RuntimeError(f'{label}: expected one closed profile, got {sk.profiles.count}')
    plane.isLightBulbOn=False
    return sk

def add_feature(comp, feature):
    sketches=[section(comp,s,feature['plane'],f"{feature['name']}_{i:02d}")
              for i,s in enumerate(feature['sections'])]
    groups=[sketches] if not feature['ruled'] else [sketches[i:i+2] for i in range(len(sketches)-1)]
    ops=adsk.fusion.FeatureOperations
    for i,group in enumerate(groups):
        operation=ops.CutFeatureOperation if feature['operation']=='cut' else (
                  ops.NewBodyFeatureOperation if i==0 else ops.JoinFeatureOperation)
        inp=comp.features.loftFeatures.createInput(operation)
        inp.isSolid=True
        for sk in group:
            inp.loftSections.add(sk.profiles.item(0))
        if feature['operation']=='cut':
            inp.participantBodies=[comp.bRepBodies.item(0)]
        loft=comp.features.loftFeatures.add(inp)
        loft.name=feature['name']+(f'_{i+1}' if len(groups)>1 else '')
        if loft.healthState!=adsk.fusion.FeatureHealthStates.HealthyFeatureHealthState:
            raise RuntimeError(loft.name+': '+loft.errorOrWarningMessage)
    for sk in sketches:
        sk.isVisible=False

def run(context):
    app=adsk.core.Application.get(); ui=app.userInterface
    out=os.path.join(HERE,'fusion_exports'); os.makedirs(out,exist_ok=True)
    report={'status':'started','components':[], 'exports':[]}
    try:
        doc=app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
        design=adsk.fusion.Design.cast(app.activeProduct)
        design.designType=adsk.fusion.DesignTypes.ParametricDesignType
        design.unitsManager.distanceDisplayUnits=adsk.fusion.DistanceUnits.MillimeterDistanceUnits
        root=design.rootComponent; root.name='Paracord 550 - A to H'
        for name,(value,unit,comment) in spec.PARAMETERS.items():
            design.userParameters.add(name,V(f'{value} {unit}'),unit,comment)
        chosen = [m for m in spec.models() if SELECTION is None or m['key'] == SELECTION]
        for index,model in enumerate(chosen):
            app.log('Building '+model['name'])
            occ=root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
            comp=occ.component; comp.name=model['name']
            start=design.timeline.count
            for feature in model['features']:
                add_feature(comp,feature)
                adsk.doEvents()
            if comp.bRepBodies.count!=1 or not comp.bRepBodies.item(0).isSolid:
                raise RuntimeError(model['name']+': expected one solid body')
            body=comp.bRepBodies.item(0); body.name=model['name']
            report['components'].append({'name':comp.name,'solid':True,'volume_mm3':body.volume*1000})
            group=design.timeline.timelineGroups.add(start,design.timeline.count-1)
            group.name=comp.name
            em=design.exportManager
            # Exports occur before the display-only assembly placement.
            for kind in ['step','stl']:
                path=os.path.join(out,comp.name+'.'+kind)
                try:
                    if kind=='step':
                        options=em.createSTEPExportOptions(path,comp)
                    else:
                        options=em.createSTLExportOptions(body,path)
                        options.unitType=adsk.fusion.DistanceUnits.MillimeterDistanceUnits
                        options.sendToPrintUtility=False
                        options.meshRefinement=adsk.fusion.MeshRefinementSettings.MeshRefinementHigh
                        options.isBinaryFormat=True
                    if not em.execute(options):
                        raise RuntimeError('Export returned false')
                    report['exports'].append({'file':path,'ok':True})
                except Exception:
                    report['exports'].append({'file':path,'ok':False,'error':traceback.format_exc()})
            transform=adsk.core.Matrix3D.create()
            transform.translation=adsk.core.Vector3D.create((index%4)*2.4,(index//4)*2.8,0)
            occ.transform2=transform
        if not design.computeAll():
            raise RuntimeError('Fusion computeAll returned false')
        for i in range(design.timeline.count):
            entity=design.timeline.item(i).entity
            if hasattr(entity,'healthState') and entity.healthState!=adsk.fusion.FeatureHealthStates.HealthyFeatureHealthState:
                raise RuntimeError(entity.name+': '+entity.errorOrWarningMessage)
        archive=os.path.join(out,'Paracord550_parametric.f3d')
        try:
            if not design.exportManager.execute(design.exportManager.createFusionArchiveExportOptions(archive)):
                raise RuntimeError('F3D export returned false')
            report['exports'].append({'file':archive,'ok':True})
        except Exception:
            report['exports'].append({'file':archive,'ok':False,'error':traceback.format_exc()})
        report['status']='geometry_complete'
        app.activeViewport.fit()
        failures=[x for x in report['exports'] if not x['ok']]
        ui.messageBox(f'Created {len(chosen)} parametric component(s).\nModify > Change Parameters.\nExports: '+out+
                      (f'\n{len(failures)} export(s) failed: see fusion_report.json.' if failures else ''))
    except Exception:
        report['status']='failed'; report['error']=traceback.format_exc()
        ui.messageBox('Build stopped. The partial new document is retained.\n'+report['error'])
    finally:
        with open(os.path.join(out,'fusion_report.json'),'w',encoding='utf-8') as f:
            json.dump(report,f,ensure_ascii=False,indent=2)

def stop(context):
    pass
