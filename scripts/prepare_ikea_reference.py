"""Import IKEA's original GLB, save a Blender reference, and render a preview.

Run: /Applications/Blender.app/Contents/MacOS/Blender -b -P scripts/prepare_ikea_reference.py
Geometry and dimensions are preserved. The scene uses meters, Z up, front -Y.
"""
from pathlib import Path
import json
import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'assets/ikea/billy-oxberg'
REFS = ROOT / 'references/ikea-billy-oxberg'
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.unit_settings.system = 'METRIC'
scene.unit_settings.length_unit = 'MILLIMETERS'
scene.unit_settings.scale_length = 1.0

reference = bpy.data.collections.new('IKEA original reference — 69017828')
scene.collection.children.link(reference)
bpy.ops.import_scene.gltf(filepath=str(ASSETS / 'billy-oxberg-80x30x202-white-original.glb'))
meshes = [obj for obj in scene.objects if obj.type == 'MESH']
for obj in meshes:
    for collection in list(obj.users_collection):
        collection.objects.unlink(obj)
    reference.objects.link(obj)
    obj['source_product'] = 'IKEA 690.178.28'
    obj['source_url'] = 'https://web-api.ikea.com/fi/en/rotera/static/models/69017828-mini.glb'
    obj['geometry_preserved'] = True

all_points = [obj.matrix_world @ Vector(c) for obj in meshes for c in obj.bound_box]
lo = [min(p[i] for p in all_points) for i in range(3)]
hi = [max(p[i] for p in all_points) for i in range(3)]
report = {
    'source_product': '69017828',
    'nominal_dimensions_mm': {'width': 800, 'depth': 300, 'height': 2020},
    'blender_axes': {'width': 'X', 'depth': 'Y', 'height': 'Z', 'front': '-Y'},
    'world_bounds_m': {'min': lo, 'max': hi},
    'mesh_bounds_mm': {axis: (hi[i] - lo[i]) * 1000 for i, axis in enumerate(['width', 'depth', 'height'])},
    'mesh_objects': len(meshes),
    'triangles': sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in meshes),
    'note': 'Website visualization mesh; nominal dimensions are the design reference. China SKU and hole positions require separate verification.'
}
(REFS / 'model-inspection.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
scene['nominal_width_mm'] = 800
scene['nominal_depth_mm'] = 300
scene['nominal_height_mm'] = 2020
scene['source_note'] = report['note']
scene.collection.children.link(bpy.data.collections.new('Design additions'))

presentation = bpy.data.collections.new('Preview camera and lighting')
scene.collection.children.link(presentation)
def move_to_preview(obj):
    for collection in list(obj.users_collection):
        collection.objects.unlink(obj)
    presentation.objects.link(obj)

def aim(obj, target):
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat('-Z', 'Y').to_euler()

bpy.ops.object.camera_add(location=(3.1, -5.5, 2.9))
camera = bpy.context.object
camera.name = 'Reference preview camera'
aim(camera, (0, 0, 1.02))
camera.data.type = 'ORTHO'
camera.data.ortho_scale = 2.64
scene.camera = camera
move_to_preview(camera)
for name, location, energy, size in [
    ('Key softbox', (2, -4, 5), 450, 4),
    ('Fill softbox', (-3, -2, 2.5), 230, 3),
    ('Top softbox', (1, 2, 4.5), 330, 3),
]:
    bpy.ops.object.light_add(type='AREA', location=location)
    light = bpy.context.object
    light.name = name
    light.data.energy = energy
    light.data.shape = 'DISK'
    light.data.size = size
    aim(light, (0, 0, 1))
    move_to_preview(light)

bpy.ops.mesh.primitive_plane_add(size=200, location=(0, 0, -0.002))
floor = bpy.context.object
floor.name = 'Preview floor'
floor_mat = bpy.data.materials.new('Preview floor material')
floor_mat.use_nodes = True
floor_mat.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value = (0.64, 0.67, 0.68, 1)
floor_mat.node_tree.nodes.get('Principled BSDF').inputs['Roughness'].default_value = 0.85
floor.data.materials.append(floor_mat)
move_to_preview(floor)

scene.world = bpy.data.worlds.new('Reference studio')
scene.world.use_nodes = True
scene.world.node_tree.nodes['Background'].inputs['Color'].default_value = (0.8, 0.85, 0.9, 1)
scene.world.node_tree.nodes['Background'].inputs['Strength'].default_value = 0.45
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = 32
scene.cycles.use_denoising = True
scene.render.resolution_x = 900
scene.render.resolution_y = 1000
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
scene.render.filepath = str(REFS / 'model-preview.png')
scene.view_settings.view_transform = 'AgX'
bpy.ops.object.select_all(action='DESELECT')
for area in bpy.context.screen.areas:
    if area.type == 'VIEW_3D':
        area.spaces.active.region_3d.view_rotation = camera.rotation_euler.to_quaternion()
        area.spaces.active.region_3d.view_location = Vector((0, 0, 1.02))
        area.spaces.active.region_3d.view_distance = 3
        area.spaces.active.region_3d.view_perspective = 'ORTHO'
bpy.ops.file.pack_all()
bpy.ops.wm.save_as_mainfile(filepath=str(ASSETS / 'billy-oxberg-80x30x202-white.blend'))
print('MODEL_INSPECTION', json.dumps(report))
bpy.ops.render.render(write_still=True)
