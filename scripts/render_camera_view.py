"""Ray-trace the actual camera position through the finite top mirror.

The unknown cylindrical optics are represented by an ideal anisotropic camera,
not by invented refractive surfaces. Run with the local Blender executable.
"""
from pathlib import Path
import json
import math
import os
import bpy
from mathutils import Vector, Matrix

ROOT = Path(__file__).resolve().parents[1]
REFS = ROOT / 'references/ikea-billy-oxberg'
OUT = REFS / 'camera-render'
OUT.mkdir(exist_ok=True)
PARAMS = json.loads((REFS / 'camera-render-input.json').read_text())
P = PARAMS['base']
FLOOR = 1.062


def world(p):
    return Vector((p[0] / 1000, p[2] / 1000 - .120, FLOOR + p[1] / 1000))


def direction(p):
    return Vector((p[0], p[2], p[1]))


bpy.ops.wm.open_mainfile(filepath=str(ROOT / 'assets/ikea/billy-oxberg/billy-oxberg-80x30x202-white.blend'))
scene = bpy.context.scene
# Retain the intact original IKEA cabinet; remove its presentation setup only.
for obj in list(scene.objects):
    if not any(c.name.startswith('IKEA original reference') for c in obj.users_collection):
        bpy.data.objects.remove(obj, do_unlink=True)

for mat in bpy.data.materials:
    if not mat.use_nodes:
        continue
    n = next((n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if n is None:
        continue
    if 'Glass EKEBY' in mat.name:
        # The GLB's alpha shader is a web-display proxy. Use thin glass
        # transmission for path-traced illumination through the closed doors.
        tree = mat.node_tree
        tree.nodes.clear()
        glass = tree.nodes.new('ShaderNodeBsdfGlass')
        glass.inputs['Color'].default_value = (.97, .99, .98, 1)
        glass.inputs['Roughness'].default_value = .01
        glass.inputs['IOR'].default_value = 1.5
        out = tree.nodes.new('ShaderNodeOutputMaterial')
        tree.links.new(glass.outputs[0], out.inputs['Surface'])
    elif 'plastic transparency' in mat.name:
        n.inputs['Alpha'].default_value = 1
        n.inputs['Roughness'].default_value = .42

design = bpy.data.collections.new('Camera render additions — ideal optics')
scene.collection.children.link(design)


def move(obj):
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    design.objects.link(obj)
    return obj


def material(name, color, rough=.5, metallic=0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    shader = m.node_tree.nodes.get('Principled BSDF')
    shader.inputs['Base Color'].default_value = (*color, 1)
    shader.inputs['Roughness'].default_value = rough
    shader.inputs['Metallic'].default_value = metallic
    return m


def cube(name, size_mm, center, mat, bevel_mm=0):
    bpy.ops.mesh.primitive_cube_add(size=1, location=world(center))
    o = move(bpy.context.object)
    o.name = name
    o.dimensions = (size_mm[0] / 1000, size_mm[2] / 1000, size_mm[1] / 1000)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    o.data.materials.append(mat)
    if bevel_mm:
        b = o.modifiers.new('Small manufactured edge', 'BEVEL')
        b.width = bevel_mm / 1000
        b.segments = 2
        o.modifiers.new('Weighted corner normals', 'WEIGHTED_NORMAL')
    return o


def plane(name, vertices, mat):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], [(0, 1, 2, 3)])
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    design.objects.link(obj)
    obj.data.materials.append(mat)
    return obj


metal = material('Mounts — brushed aluminium', (.27, .30, .31), .32, .7)
black = material('Aperture and camera housing — matte black', (.008, .009, .011), .7)
mirror = material('M1 — ideal first surface aluminium', (.94, .94, .94), .001, 1)
pages = material('Book pages — warm paper', (.76, .735, .67), .86)
tree = pages.node_tree
noise = tree.nodes.new('ShaderNodeTexNoise')
noise.inputs['Scale'].default_value = 1600
noise.inputs['Detail'].default_value = 2
bump = tree.nodes.new('ShaderNodeBump')
bump.inputs['Strength'].default_value = .13
bump.inputs['Distance'].default_value = .00008
tree.links.new(noise.outputs['Fac'], bump.inputs['Height'])
tree.links.new(bump.outputs['Normal'], tree.nodes.get('Principled BSDF').inputs['Normal'])

# Mirror geometry uses the same centre, finite edges and tilt as the HTML model.
mc = world(PARAMS['mirror'])
tx = Vector((1, 0, 0))
ty = direction(PARAMS['tangent'])
normal = direction(PARAMS['normal'])
hw, hh = P['m1Length'] / 2000, P['m1Width'] / 2000
mirror_vertices = [mc + tx * sx * hw + ty * sy * hh for sx, sy in [(-1, -1), (1, -1), (1, 1), (-1, 1)]]
plane('M1 — reflective 580 × 52 mm face', mirror_vertices, mirror)
for sy in [-1, 1]:
    centre = mc + ty * (sy * (hh + .001))
    plane('M1 long edge — 1 mm rim', [centre - tx * (hw + .001) - ty * .0005,
          centre + tx * (hw + .001) - ty * .0005,
          centre + tx * (hw + .001) + ty * .0005,
          centre - tx * (hw + .001) + ty * .0005], black)
for sx in [-1, 1]:
    centre = mc + tx * (sx * (hw + .001))
    plane('M1 short edge — 1 mm rim', [centre - tx * .0005 - ty * (hh + .001),
          centre + tx * .0005 - ty * (hh + .001),
          centre + tx * .0005 + ty * (hh + .001),
          centre - tx * .0005 + ty * (hh + .001)], black)
    x = sx * (P['m1Length'] / 2 + 8)
    cube('M1 ceiling bracket', [18, 3, 34], [x, P['height'] - 2, P['mirrorZ']], metal, .3)
    cube('M1 bracket drop', [4, P['height'] - P['mirrorY'] - 3, 10],
         [x, (P['height'] + P['mirrorY'] - 3) / 2, P['mirrorZ']], metal, .3)

# Lens frames remain physical occluders. The clear openings contain no arbitrary
# glass: their unknown net power is represented by the ideal camera ray mapping.
cp = Vector(PARAMS['camera'])
f = Vector(PARAMS['forward'])
u = direction(PARAMS['up'])
fw = direction(PARAMS['forward'])
right = Vector((-1, 0, 0))
frame_basis = Matrix((right, u, -fw)).transposed()
for spec in PARAMS['cylinders']:
    lc = cp + f * spec['distance']
    center = world(lc)
    width, height = spec['clearWidth'] / 1000, spec['clearHeight'] / 1000
    for sign in [-1, 1]:
        for label, dims, off in [
            ('horizontal rim', (width + .006, .003, .005), u * sign * (height / 2 + .0015)),
            ('vertical rim', (.003, height, .005), right * sign * (width / 2 + .0015)),
        ]:
            bpy.ops.mesh.primitive_cube_add(size=1, location=center + off)
            obj = move(bpy.context.object)
            obj.name = spec['id'] + ' — ' + label
            obj.rotation_euler = frame_basis.to_euler()
            obj.dimensions = dims
            bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
            obj.data.materials.append(black)
        postx = sign * (spec['housingWidth'] / 2 + 2)
        top = lc[1] + spec['housingHeight'] / 2
        cube(spec['id'] + ' mounting post', [3, P['height'] - top, 5],
             [postx, (P['height'] + top) / 2, lc[2]], metal, .2)

font = bpy.data.fonts.load('/System/Library/Fonts/STHeiti Medium.ttc')
titles = ['书架设计', '光学入门', '空间与秩序', '建筑的细节', '阅读与生活', '图像的语言',
          '城市观察', '时间简史', '设计中的设计', '认识材料', '工程笔记', '视觉与感知',
          '数学之美', '看见世界', '科学的故事', '摄影与光线', '信息设计', '自然的形状',
          '机器视觉', '造物手记', '智能系统', '人间草木', '色彩研究', '图书管理',
          '纸上的风景', '计算之道', '未来的书房']
palette = [(.055, .12, .16), (.60, .18, .09), (.66, .59, .43), (.19, .25, .22),
           (.74, .72, .63), (.09, .21, .29), (.37, .10, .11), (.68, .43, .12),
           (.21, .23, .30), (.39, .46, .42), (.68, .66, .57), (.12, .23, .21)]
light_ink = material('Printed ink — warm white', (.84, .81, .71), .78)
dark_ink = material('Printed ink — charcoal', (.019, .023, .021), .78)


def print_text(name, body, position, size, ink, align='CENTER'):
    text = bpy.data.curves.new(name, type='FONT')
    text.body = body
    text.font = font
    text.size = size / 1000
    text.align_x = 'CENTER'
    text.align_y = align
    text.space_line = 1.18
    text.resolution_u = 4
    obj = bpy.data.objects.new(name, text)
    design.objects.link(obj)
    obj.location = world(position)
    obj.rotation_euler = (math.pi / 2, 0, 0)
    obj.data.materials.append(ink)
    return obj


for b in PARAMS['books']:
    i = b['id'] - 1
    x = (b['x0'] + b['x1']) / 2
    w = b['x1'] - b['x0'] - .7
    h = b['height']
    z = b['z']
    color = palette[i % len(palette)]
    cover = material(f'Book {i+1:02d} cloth cover', color, .73)
    # A spine shell, paper block and two thin covers give visible real shadows.
    cube(f'Book {i+1:02d} page block', [max(1, w-1.6), h-2, b['depth']-2.5],
         [x, h/2, z + b['depth']/2 + .4], pages, .2)
    cube(f'Book {i+1:02d} spine', [w, h, 1.8], [x, h/2, z+.9], cover, .65)
    for sign in [-1, 1]:
        cube(f'Book {i+1:02d} cover', [.65, h, b['depth']],
             [x + sign * (w/2-.325), h/2, z+b['depth']/2], cover, .22)
    ink = light_ink if sum(color) < 1.15 else dark_ink
    title_size = min(8.4, w*.40)
    print_text(f'Book {i+1:02d} vertical title', '\n'.join(titles[i]),
               [x, h*.61, z-.025], title_size, ink)
    print_text(f'Book {i+1:02d} index', f'{i+1:02d}', [x, h-17, z-.028], 5.0, ink)
    print_text(f'Book {i+1:02d} imprint', '示\n例\n书', [x, 30, z-.028], 3.4, ink)
    # Narrow printed rule above the imprint.
    cube(f'Book {i+1:02d} printed rule', [w*.48, .28, .015], [x, 49, z-.03], ink)


def aim(obj, point):
    obj.rotation_euler = (Vector(point) - obj.location).to_track_quat('-Z', 'Y').to_euler()


# External soft lighting is an explicit assumed room, not an installed shelf LED.
scene.world = bpy.data.worlds.new('Assumed bright indoor room')
scene.world.use_nodes = True
scene.world.node_tree.nodes['Background'].inputs['Color'].default_value = (.72, .78, .86, 1)
scene.world.node_tree.nodes['Background'].inputs['Strength'].default_value = .3
for name, loc, watts, size, tint in [
    ('Room window in front of cabinet', (-.65, -1.3, 2.05), 110, 1.15, (1, .94, .84)),
    ('Room fill on right', (.9, -.8, 1.30), 40, .85, (.86, .93, 1)),
]:
    bpy.ops.object.light_add(type='AREA', location=loc)
    light = move(bpy.context.object)
    light.name = name
    light.data.energy = watts
    light.data.shape = 'DISK'
    light.data.size = size
    light.data.color = tint
    aim(light, world((0, 150, 60)))

bpy.ops.object.camera_add(location=world(PARAMS['camera']))
camera = move(bpy.context.object)
camera.name = 'C — real position, ideal anisotropic entrance pupil'
aim(camera, world(PARAMS['aim']))
camera.data.type = 'PERSP'
camera.data.sensor_fit = 'HORIZONTAL'
camera.data.sensor_width = 36
camera.data.lens = 36 / (2 * math.tan(math.radians(P['hfov']/2)))
camera.data.clip_start = .0005
camera.data.clip_end = 20
camera.data.dof.use_dof = False
scene.camera = camera
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = int(os.environ.get('RENDER_SAMPLES', '64'))
scene.cycles.use_denoising = True
scene.cycles.max_bounces = 8
scene.cycles.transmission_bounces = 6
scene.cycles.glossy_bounces = 4
scene.cycles.transparent_max_bounces = 12
scene.render.resolution_x = int(os.environ.get('RENDER_WIDTH', '1920'))
scene.render.resolution_y = scene.render.resolution_x * 9 // 16
scene.render.resolution_percentage = 100
# Non-square pixel camera ray geometry implements only the ideal target mapping.
# Image files are displayed at their raster 16:9 dimensions, an ideal optical
# vertical magnification; this is not a solved two-cylinder-lens ray trace.
scene.render.pixel_aspect_x = PARAMS['fit']['anamorphicRatio']
scene.render.pixel_aspect_y = 1
bpy.context.view_layer.update()
from bpy_extras.object_utils import world_to_camera_view
projection_errors = []
for check in PARAMS['projectionChecks']:
    uv = world_to_camera_view(scene, camera, world(check['mirrorPoint']))
    error = max(abs(uv[i] - check['rawImageUV'][i]) for i in range(2))
    projection_errors.append(error)
    assert error < 1e-5, f'Camera ray projection disagrees with geometry: {uv}, {check}'
scene.render.image_settings.file_format = 'PNG'
scene.render.image_settings.color_mode = 'RGB'
scene.render.image_settings.color_depth = '8'
scene.render.film_transparent = False
scene.view_settings.view_transform = 'AgX'
scene.view_settings.look = 'AgX - Medium High Contrast'
scene.view_settings.exposure = 0
scene.render.filepath = str(OUT / 'camera-raw.png')
scene['optical_status'] = 'Finite M1 reflected rays; ideal anamorphic camera; no actual cylinder refraction, focus, MTF or OCR validation'
scene['lighting_status'] = 'Assumed external room lighting, through the intact glass doors'
scene['book_status'] = 'Synthetic sample books with printed sample titles; not user book data'
bpy.ops.wm.save_as_mainfile(filepath=str(OUT / 'camera-view.blend'))
bpy.ops.render.render(write_still=True)

# A single reflection reverses lateral orientation. Save a digital correction
# separately, with no perspective flattening, cropping or synthetic sharpening.
img = bpy.data.images.load(str(OUT / 'camera-raw.png'), check_existing=False)
img.filepath_raw = str(OUT / 'camera-raw.jpg')
img.file_format = 'JPEG'
img.save()
w, h = img.size
pixels = list(img.pixels[:])
flipped = [0.0] * len(pixels)
for y in range(h):
    for x in range(w):
        src, dst = (y*w+x)*4, (y*w+(w-1-x))*4
        flipped[dst:dst+4] = pixels[src:src+4]
img.pixels[:] = flipped
img.filepath_raw = str(OUT / 'camera-corrected.png')
img.file_format = 'PNG'
img.save()

report = {
    'renderer': 'Blender Cycles', 'samples': scene.cycles.samples,
    'resolution': [w, h], 'cameraLocalMm': PARAMS['camera'],
    'aimLocalMm': PARAMS['aim'], 'horizontalFovDeg': P['hfov'],
    'idealVerticalFovDeg': P['vfov'], 'idealAnamorphicRatio': PARAMS['fit']['anamorphicRatio'],
    'cameraProjectionMaxUVError': max(projection_errors),
    'mirrorCenterLocalMm': PARAMS['mirror'], 'mirrorSizeMm': [P['m1Length'], P['m1Width']],
    'cabinetGeometry': 'Intact official IKEA GLB from saved reference .blend; no cutaway',
    'books': '27 synthetic aligned books, 220–250 mm tall; custom printed sample titles',
    'raw': 'camera-raw.png', 'embeddedPreview': 'camera-raw.jpg',
    'digitalHorizontalFlip': 'camera-corrected.png',
    'notSimulated': ['real cylinder refraction and optical prescription', 'finite entrance pupil', 'focus, depth of field and aberrations', 'sensor noise and OCR'],
    'assumed': ['ideal anisotropic camera mapping', 'external indoor soft lighting', 'first-surface mirror material', 'thin glass door shader replacing GLB alpha preview'],
}
(OUT / 'render-settings.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
print('CAMERA_RENDER', json.dumps(report, ensure_ascii=False))
