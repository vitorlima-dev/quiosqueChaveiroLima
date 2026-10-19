import bpy, sys, math, json
from mathutils import Vector

argv = sys.argv[sys.argv.index('--') + 1:]
mode, cam_name, out, samples, res_x, res_y = argv[0], argv[1], argv[2], int(argv[3]), int(argv[4]), int(argv[5])
GLTF = '/tmp/claude-0/-home-user-quiosqueChaveiroLima/5384e258-31df-50b5-b5a6-66312b67d807/scratchpad/kiosk.gltf'
night = (mode == 'night')

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=GLTF)
sc = bpy.context.scene

# ---------- materiais ----------
def principled(m):
    if not m.use_nodes: return None
    for n in m.node_tree.nodes:
        if n.type == 'BSDF_PRINCIPLED': return n
    return None

report = []
for m in bpy.data.materials:
    p = principled(m)
    if p is None:
        em_node = next((n for n in m.node_tree.nodes if n.type == 'EMISSION'), None)
        has_tex = any(n.type == 'TEX_IMAGE' for n in m.node_tree.nodes)
        if em_node is not None:
            em_node.inputs['Strength'].default_value = (2.4 if has_tex else 9.0) if night else (1.0 if has_tex else 2.5)
        report.append((m.name, 'unlit ' + ('logo' if has_tex else 'halo')))
        continue
    alpha = p.inputs['Alpha'].default_value
    linked_alpha = p.inputs['Alpha'].is_linked
    em = p.inputs['Emission Color'].default_value
    em_lum = 0.2126 * em[0] + 0.7152 * em[1] + 0.0722 * em[2]
    base = p.inputs['Base Color'].default_value
    # vidro: opacidade baixa no modelo
    if not linked_alpha and alpha < 0.5:
        p.inputs['Alpha'].default_value = 1.0
        p.inputs['Transmission Weight'].default_value = 1.0
        p.inputs['Roughness'].default_value = 0.03
        p.inputs['IOR'].default_value = 1.45
        p.inputs['Base Color'].default_value = (0.9, 0.97, 1.0, 1)
        m.name = 'GLASS_' + m.name
        report.append((m.name, 'vidro'))
        continue
    # LED (emissivo claro, base escura)
    es = p.inputs['Emission Strength'].default_value
    if es > 0 and em_lum > 0.4 and not p.inputs['Emission Color'].is_linked:
        p.inputs['Emission Strength'].default_value = 12.0 if night else 5.0
        report.append((m.name, 'led %.2f' % em_lum))
    elif p.inputs['Emission Color'].is_linked:
        # letreiro iluminado: emissao por textura
        p.inputs['Emission Strength'].default_value = 1.6 if night else 0.0
        report.append((m.name, 'emissivo por textura'))
    # sem metal puro em superficies pintadas
    if p.inputs['Metallic'].default_value > 0.5 and base[0] < 0.2:
        p.inputs['Roughness'].default_value = max(p.inputs['Roughness'].default_value, 0.38)

# ---------- cor por vertice (chaves, carcacas, relogios) ----------
for ob in bpy.data.objects:
    if ob.type != 'MESH': continue
    me = ob.data
    ca = me.color_attributes
    if len(ca) == 0: continue
    for slot in ob.material_slots:
        m = slot.material
        if not m or not m.use_nodes: continue
        p = principled(m)
        if p is None or p.inputs['Base Color'].is_linked: continue
        nt = m.node_tree
        if any(n.type == 'VERTEX_COLOR' or n.type == 'ATTRIBUTE' for n in nt.nodes): continue
        vc = nt.nodes.new('ShaderNodeVertexColor'); vc.layer_name = ca[0].name
        mix = nt.nodes.new('ShaderNodeMix'); mix.data_type = 'RGBA'; mix.blend_type = 'MULTIPLY'
        mix.inputs['Factor'].default_value = 1.0
        mix.inputs['A'].default_value = p.inputs['Base Color'].default_value
        nt.links.new(vc.outputs['Color'], mix.inputs['B'])
        nt.links.new(mix.outputs['Result'], p.inputs['Base Color'])

# ---------- chao ----------
bpy.ops.mesh.primitive_plane_add(size=800, location=(0, 0, -0.002))
ground = bpy.context.object; ground.name = 'ground'
gm = bpy.data.materials.new('Calcada'); gm.use_nodes = True
nt = gm.node_tree; pb = nt.nodes['Principled BSDF']
brick = nt.nodes.new('ShaderNodeTexBrick'); brick.inputs['Scale'].default_value = 1.5
brick.offset = 0.0; brick.inputs['Mortar Size'].default_value = 0.02; brick.inputs['Brick Width'].default_value = 1.0; brick.inputs['Row Height'].default_value = 1.0
brick.inputs['Color1'].default_value = (0.36, 0.34, 0.31, 1); brick.inputs['Color2'].default_value = (0.29, 0.275, 0.255, 1); brick.inputs['Mortar'].default_value = (0.2, 0.2, 0.2, 1)
noise = nt.nodes.new('ShaderNodeTexNoise'); noise.inputs['Scale'].default_value = 8; noise.inputs['Detail'].default_value = 6
mixc = nt.nodes.new('ShaderNodeMix'); mixc.data_type = 'RGBA'; mixc.blend_type = 'MULTIPLY'; mixc.inputs['Factor'].default_value = 0.35
nt.links.new(brick.outputs['Color'], mixc.inputs['A']); nt.links.new(noise.outputs['Color'], mixc.inputs['B'])
nt.links.new(mixc.outputs['Result'], pb.inputs['Base Color']); pb.inputs['Roughness'].default_value = 0.55
tc = nt.nodes.new('ShaderNodeTexCoord'); mp = nt.nodes.new('ShaderNodeMapping'); mp.inputs['Scale'].default_value = (1, 1, 1)
nt.links.new(tc.outputs['Object'], mp.inputs['Vector']); nt.links.new(mp.outputs['Vector'], brick.inputs['Vector']); nt.links.new(mp.outputs['Vector'], noise.inputs['Vector'])
bump = nt.nodes.new('ShaderNodeBump'); bump.inputs['Strength'].default_value = 0.3
nt.links.new(brick.outputs['Fac'], bump.inputs['Height']); nt.links.new(bump.outputs['Normal'], pb.inputs['Normal'])
ground.data.materials.append(gm)

# ---------- ceu ----------
w = bpy.data.worlds.new('W'); sc.world = w; w.use_nodes = True
wn = w.node_tree.nodes; wl = w.node_tree.links
for n in list(wn): wn.remove(n)
sky = wn.new('ShaderNodeTexSky'); sky.sky_type = 'MULTIPLE_SCATTERING'
sky.sun_elevation = math.radians(-2.5 if night else 38); sky.sun_rotation = math.radians(210); sky.altitude = 5; sky.air_density = 1.0
sky.sun_size = math.radians(0.6); sky.sun_intensity = 1.0; sky.sun_disc = False
bg = wn.new('ShaderNodeBackground'); bg.inputs['Strength'].default_value = 0.5 if night else 0.32
outn = wn.new('ShaderNodeOutputWorld')
wl.new(sky.outputs['Color'], bg.inputs['Color']); wl.new(bg.outputs['Background'], outn.inputs['Surface'])

if night:
    # luz de poste distante, quente, e preenchimento azul suave
    bpy.ops.object.light_add(type='AREA', location=(6.5, -7.5, 5.0)); l = bpy.context.object
    l.data.energy = 420; l.data.size = 2.5; l.data.color = (1.0, 0.78, 0.5)
    l.rotation_euler = (math.radians(65), 0, math.radians(40))
    bpy.ops.object.light_add(type='AREA', location=(-7, -3, 4)); l2 = bpy.context.object
    l2.data.energy = 250; l2.data.size = 4; l2.data.color = (0.55, 0.7, 1.0)
    l2.rotation_euler = (math.radians(70), 0, math.radians(-60))
else:
    bpy.ops.object.light_add(type='SUN'); s = bpy.context.object
    s.data.energy = 7.0; s.data.color = (1.0, 0.93, 0.82); s.data.angle = math.radians(1.2)
    s.rotation_euler = (math.radians(52), 0, math.radians(30 + 180 + 0))
    s.rotation_euler = (math.radians(52), math.radians(0), math.radians(-52))


# ---------- luzes artificiais do quiosque (so a noite): sanca quente, perfis de vitrine, halo do logo ----------
def area(loc3, size, energy, color, rot_deg=(0, 0, 0), shape='RECTANGLE', size_y=None):
    bpy.ops.object.light_add(type='AREA', location=to_b(*loc3)); o = bpy.context.object
    o.data.shape = shape; o.data.size = size
    if size_y is not None: o.data.size_y = size_y
    o.data.energy = energy; o.data.color = color
    o.rotation_euler = tuple(math.radians(a) for a in rot_deg)
    return o

def to_b(x, y, z): return Vector((x, -z, y))

if night:
    warm = (1.0, 0.72, 0.42); cool = (1.0, 0.92, 0.82)
    area((0, 2.12, 1.05), 3.8, 200, warm, size_y=0.25)                       # sanca da frente
    area((-1.9, 2.12, 0.0), 0.25, 150, warm, size_y=2.1)                     # sanca lateral (lado da vitrine em L, espelhado)
    area((1.9, 2.12, 0.0), 0.25, 150, warm, size_y=2.1)                      # sanca lateral do relojoeiro
    area((0, 1.04, 0.95), 3.8, 55, cool, size_y=0.12)                       # perfil LED da vitrine, fileira da frente
    area((0, 1.04, 0.70), 3.8, 55, cool, size_y=0.12)
    area((-1.80, 1.04, -0.3), 0.12, 40, cool, size_y=1.5)                    # perfil LED lateral
    area((0, 1.85, -1.04), 0.9, 90, (1.0, 1.0, 1.0), rot_deg=(-90, 0, 0))    # halo do logo lavando a parede
    area((0, 2.1, -0.2), 3.5, 60, warm, size_y=1.2)                          # preenchimento quente suave no corredor

# ---------- cameras ----------
CAMS = {
    'tres_quartos': ((-4.6, 1.55, 5.6), (-0.1, 1.15, 0.2), 32),
    'frente':       ((-0.4, 1.45, 6.4), (0.0, 1.2, 0.3), 38),
    'painel':       ((0.8, 1.55, 2.6), (0.1, 1.45, -1.1), 30),
    'lateral':      ((-5.2, 1.5, 0.9), (-1.9, 1.05, -0.3), 36),
}
pos, tgt, fl = CAMS[cam_name]
bpy.ops.object.camera_add(location=to_b(*pos)); cam = bpy.context.object
d = to_b(*tgt) - cam.location
cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
cam.data.lens = fl; cam.data.sensor_width = 36
cam.data.dof.use_dof = True; cam.data.dof.focus_distance = d.length; cam.data.dof.aperture_fstop = 9.0
sc.camera = cam

# ---------- render ----------
sc.render.engine = 'CYCLES'
cy = sc.cycles
cy.device = 'CPU'; cy.samples = samples; cy.use_denoising = True
try: cy.denoiser = 'OPENIMAGEDENOISE'
except Exception: pass
cy.max_bounces = 10; cy.glossy_bounces = 6; cy.transmission_bounces = 8; cy.transparent_max_bounces = 10
cy.caustics_reflective = False; cy.caustics_refractive = False
cy.sample_clamp_indirect = 8
sc.render.resolution_x = res_x; sc.render.resolution_y = res_y; sc.render.resolution_percentage = 100
sc.render.image_settings.file_format = 'PNG'
sc.view_settings.view_transform = 'AgX'; sc.view_settings.look = 'AgX - Medium High Contrast' if False else 'None'
sc.view_settings.exposure = 0.0 if night else -1.0
sc.render.filepath = out
print('MATERIAIS', json.dumps(report))
bpy.ops.render.render(write_still=True)
print('RENDER OK', out)
