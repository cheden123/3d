"""Package the tested Windows folder and preserve dependency license texts."""
from pathlib import Path
import importlib.metadata as metadata
import hashlib,json,shutil,sys,zipfile,urllib.request

root=Path(__file__).resolve().parents[1]
folder=root/'dist/BeadStudio'
assert (folder/'BeadStudio.exe').exists(),'Build BeadStudio.spec first'
licenses=folder/'LICENSES';licenses.mkdir(exist_ok=True)
for name in ['cadquery-ocp','cadquery-ocp-proxy','vtk','pyinstaller','altgraph','pefile','pywin32-ctypes']:
    dist=metadata.distribution(name)
    for f in dist.files or []:
        if '.dist-info/' in str(f) and any(x in str(f).lower() for x in ['license','copying','copyright','notice']):
            target=licenses/name/str(f).split('.dist-info/',1)[1]
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(dist.locate_file(f),target)
python_license=Path(sys.base_prefix)/'LICENSE.txt'
if python_license.exists():shutil.copyfile(python_license,licenses/'PYTHON-LICENSE.txt')
# Explicit LGPL and exception texts complement wheel metadata.
for filename in ['LICENSE_LGPL_21.txt','OCCT_LGPL_EXCEPTION.txt']:
    url='https://raw.githubusercontent.com/Open-Cascade-SAS/OCCT/V7_9_3/'+filename
    with urllib.request.urlopen(url,timeout=30) as response:
        (licenses/filename).write_bytes(response.read())
(licenses/'SOURCES.txt').write_text(
    'OpenCascade 7.9.3 source: https://github.com/Open-Cascade-SAS/OCCT/tree/V7_9_3\n'
    'OCP wrapper source: https://github.com/CadQuery/OCP\n'
    'VTK 9.6 source: https://gitlab.kitware.com/vtk/vtk/-/tree/v9.6.0\n'
    'Python: https://www.python.org/downloads/source/\n'
    'The OCP runtime uses separate replaceable shared libraries under _internal.\n',encoding='utf-8')
shutil.copyfile(root/'README.md',folder/'README_RU.md')
shutil.copyfile(root/'LICENSE',folder/'LICENSE.txt')
archive=root/'dist/BeadStudio-Windows-x64.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=7) as z:
    for p in sorted(folder.rglob('*')):
        if p.is_file():z.write(p,'BeadStudio/'+p.relative_to(folder).as_posix())
with zipfile.ZipFile(archive) as z:assert z.testzip() is None
sha=hashlib.sha256(archive.read_bytes()).hexdigest()
archive.with_suffix('.zip.sha256').write_text(f'{sha}  {archive.name}\n',encoding='ascii')
print(json.dumps({'zip':str(archive),'bytes':archive.stat().st_size,'sha256':sha},indent=2))
