"""Extract the approved character GIFs without altering their pixels or timing."""
import json
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1] / 'cerberus/assets/characters'
for name in ('ghost', 'cerberus', 'hades', 'charon'):
    root = ROOT / name
    image = Image.open(root / 'performance.gif')
    frames = []
    for index in range(image.n_frames):
        image.seek(index)
        filename = f'{index:02}.png'
        image.convert('RGBA').save(root / filename)
        frames.append(filename)
    manifest = {'format': 'cerberus-animation-pack', 'version': 2,
                'default': frames[0], 'states': {
                    'idle': {'gif': 'performance.gif', 'loop': True},
                    'play': {'gif': 'performance.gif', 'loop': False},
                    'guard': {'frames': [frames[0]], 'fps': 1, 'loop': True, 'anchored': True},
                    'sleep': {'frames': [frames[0]], 'fps': 1, 'loop': True, 'anchored': True}}}
    (root / 'animation-pack.json').write_text(json.dumps(manifest, indent=2)+'\n')
