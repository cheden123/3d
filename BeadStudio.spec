# Windows portable build; recursively include only DLLs needed by the OCP binary.
from pathlib import Path
import importlib.util
import pefile

root=Path(SPECPATH)
ocp=Path(importlib.util.find_spec('OCP').origin).parent
site=ocp.parent
search=[site/'cadquery_ocp.libs',site/'vtk.libs']
lookup={p.name.lower():p for folder in search if folder.exists() for p in folder.glob('*.dll')}
queue=list(ocp.glob('*.pyd')); seen=set(); binaries=[]
while queue:
    file=queue.pop()
    if file in seen:continue
    seen.add(file)
    pe=pefile.PE(str(file),fast_load=True)
    pe.parse_data_directories(directories=[1,13])
    imports=list(getattr(pe,'DIRECTORY_ENTRY_IMPORT',[]))+list(getattr(pe,'DIRECTORY_ENTRY_DELAY_IMPORT',[]))
    for entry in imports:
        dll=lookup.get(entry.dll.decode().lower())
        if dll and dll not in seen:queue.append(dll)
    pe.close()
    if file.suffix.lower()=='.dll':binaries.append((str(file),file.parent.name))

datas=[('web','web'),('fusion_template','fusion_template'),
       ('bead_studio/model_spec.py','bead_studio'),('tools/NOTICE-vtk.txt','vtk.libs')]
a=Analysis(['launch.py'],pathex=[str(root)],binaries=binaries,datas=datas,
           hiddenimports=['OCP.OCP'],excludes=['cadquery','vtkmodules','numpy','scipy','casadi','pytest','trimesh'])
pyz=PYZ(a.pure)
exe=EXE(pyz,a.scripts,[],exclude_binaries=True,name='BeadStudio',console=False,
        icon='assets/bead.ico',upx=False)
coll=COLLECT(exe,a.binaries,a.datas,strip=False,upx=False,name='BeadStudio')
