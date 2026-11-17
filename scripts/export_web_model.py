"""Export a browser-ready GLB with embedded PNG textures and uncompressed geometry."""
from pathlib import Path
import bpy

root = Path(__file__).resolve().parents[1]
folder = root / 'assets/ikea/billy-oxberg'
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(folder / 'billy-oxberg-80x30x202-white-original.glb'))
for image in bpy.data.images:
    image.file_format = 'PNG'
bpy.ops.export_scene.gltf(
    filepath=str(folder / 'billy-oxberg-80x30x202-white-web.glb'),
    export_format='GLB',
    export_image_format='AUTO',
    export_draco_mesh_compression_enable=False,
    export_cameras=False,
    export_lights=False,
)
