"""Regenerate catalogue thumbnails from the default printable geometry."""
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

import matplotlib
matplotlib.use('Agg')
from matplotlib import pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import numpy as np
from PIL import Image
import trimesh

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bead_studio.cad import Settings, build, export
from bead_studio.model_spec import PRESETS


def render_catalog(destination):
    destination.mkdir(parents=True, exist_ok=True)
    light = np.array([-.35, -.65, .73])
    light /= np.linalg.norm(light)
    copper = np.array([.77, .48, .29])
    with TemporaryDirectory() as tmp:
        stl = Path(tmp) / 'preview.stl'
        step = stl.with_suffix('.step')
        png = stl.with_suffix('.png')
        for key in PRESETS:
            settings = Settings.read({'shape': key})
            export(build(settings), stl, step)
            mesh = trimesh.load_mesh(stl)
            shade = .52 + .48 * np.clip(mesh.face_normals @ light, 0, 1)
            fig = plt.figure(figsize=(2, 2), dpi=150)
            ax = fig.add_axes([0, 0, 1, 1], projection='3d', proj_type='ortho')
            ax.add_collection3d(Poly3DCollection(
                mesh.triangles, facecolors=shade[:, None] * copper,
                edgecolors='none', antialiaseds=False))
            extent = max(settings.diameter, settings.height) / 2
            centre = settings.height / 2
            ax.set(xlim=(-extent, extent), ylim=(-extent, extent),
                   zlim=(centre-extent, centre+extent))
            ax.set_box_aspect((1, 1, 1), zoom=1.25)
            ax.view_init(elev=27, azim=-65)
            ax.set_axis_off()
            fig.savefig(png, transparent=True)
            plt.close(fig)
            with Image.open(png) as bitmap:
                cropped = bitmap.crop(bitmap.getbbox())
                cropped.thumbnail((88, 88), Image.Resampling.LANCZOS)
                frame = Image.new('RGBA', (96, 96))
                frame.paste(cropped, ((96-cropped.width)//2, (96-cropped.height)//2))
                frame.save(destination / f'{key}.webp', lossless=True)


if __name__ == '__main__':
    render_catalog(ROOT / 'web' / 'models')
