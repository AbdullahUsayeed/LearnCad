# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileNotice: Part of the LearnCad addon.
"""Blender studio render used by LearnCad.

Run headless:

    blender --background --factory-startup --python learncad_render.py -- \
        model.stl output.png CYCLES 1200 800 64 aluminum
"""

from __future__ import annotations

import math
import sys

import bpy
from mathutils import Vector


def _args() -> list[str]:
    if "--" in sys.argv:
        return sys.argv[sys.argv.index("--") + 1 :]
    return []


def _clear() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for datablocks in (bpy.data.meshes, bpy.data.materials, bpy.data.lights, bpy.data.cameras):
        for block in list(datablocks):
            if block.users == 0:
                datablocks.remove(block)


def _import_model(path: str):
    try:
        bpy.ops.wm.stl_import(filepath=path)
    except Exception:
        bpy.ops.import_mesh.stl(filepath=path)
    meshes = [obj for obj in bpy.context.selected_objects if obj.type == "MESH"]
    if not meshes:
        meshes = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    if not meshes:
        raise RuntimeError("Blender could not find a mesh in the exported model.")
    if len(meshes) > 1:
        bpy.ops.object.select_all(action="DESELECT")
        for obj in meshes:
            obj.select_set(True)
        bpy.context.view_layer.objects.active = meshes[0]
        bpy.ops.object.join()
        meshes = [bpy.context.view_layer.objects.active]
    obj = meshes[0]
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    try:
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    except Exception:
        pass
    # Blender lights behave predictably when the model is roughly meter-scale.
    minimum, maximum, size = _bounds(obj)
    if size > 0.001:
        factor = 2.0 / size
        obj.scale = (factor, factor, factor)
        try:
            bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        except Exception:
            pass
    return obj


def _bounds(obj) -> tuple[Vector, Vector, float]:
    points = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    minimum = Vector((min(p.x for p in points), min(p.y for p in points), min(p.z for p in points)))
    maximum = Vector((max(p.x for p in points), max(p.y for p in points), max(p.z for p in points)))
    size = max(maximum.x - minimum.x, maximum.y - minimum.y, maximum.z - minimum.z, 1.0)
    return minimum, maximum, size


def _set(bsdf, names, value) -> bool:
    for name in names:
        if name in bsdf.inputs:
            try:
                bsdf.inputs[name].default_value = value
                return True
            except Exception:
                pass
    return False


def _new_material(name: str):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    return mat, mat.node_tree.nodes.get("Principled BSDF"), mat.node_tree.nodes


def _noise_surface(nodes, links, bsdf, scale, detail, roughness_low, roughness_high, bump_strength, stretch=(1.0, 1.0, 1.0)):
    tex = nodes.new("ShaderNodeTexCoord")
    mapping = nodes.new("ShaderNodeMapping")
    mapping.inputs["Scale"].default_value = stretch
    noise = nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = scale
    noise.inputs["Detail"].default_value = detail
    noise.inputs["Roughness"].default_value = 0.55
    ramp = nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.30
    ramp.color_ramp.elements[0].color = (roughness_low, roughness_low, roughness_low, 1.0)
    ramp.color_ramp.elements[1].position = 0.75
    ramp.color_ramp.elements[1].color = (roughness_high, roughness_high, roughness_high, 1.0)
    bump = nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = bump_strength
    bump.inputs["Distance"].default_value = 0.002

    links.new(tex.outputs["Object"], mapping.inputs["Vector"])
    links.new(mapping.outputs["Vector"], noise.inputs["Vector"])
    links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
    links.new(noise.outputs["Fac"], bump.inputs["Height"])
    if "Roughness" in bsdf.inputs:
        links.new(ramp.outputs["Color"], bsdf.inputs["Roughness"])
    if "Normal" in bsdf.inputs:
        links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])


def _material_aluminum():
    mat, bsdf, nodes = _new_material("LearnCad Aluminum")
    _set(bsdf, ["Base Color"], (0.76, 0.78, 0.81, 1.0))
    _set(bsdf, ["Metallic"], 1.0)
    _set(bsdf, ["Roughness"], 0.24)
    _set(bsdf, ["Anisotropic IOR Level", "Anisotropic"], 0.45)
    _noise_surface(nodes, mat.node_tree.links, bsdf, scale=38.0, detail=3.0, roughness_low=0.16, roughness_high=0.34, bump_strength=0.12, stretch=(2.0, 110.0, 2.0))
    return mat


def _material_plastic():
    mat, bsdf, nodes = _new_material("LearnCad Plastic")
    _set(bsdf, ["Base Color"], (0.80, 0.16, 0.025, 1.0))
    _set(bsdf, ["Metallic"], 0.0)
    _set(bsdf, ["Roughness"], 0.26)
    _set(bsdf, ["Coat Weight", "Clearcoat"], 1.0)
    _set(bsdf, ["Coat Roughness", "Clearcoat Roughness"], 0.12)
    _noise_surface(nodes, mat.node_tree.links, bsdf, scale=140.0, detail=2.0, roughness_low=0.20, roughness_high=0.32, bump_strength=0.035, stretch=(1.0, 1.0, 1.0))
    return mat


def _material_rubber():
    mat, bsdf, nodes = _new_material("LearnCad Rubber")
    _set(bsdf, ["Base Color"], (0.022, 0.022, 0.025, 1.0))
    _set(bsdf, ["Metallic"], 0.0)
    _set(bsdf, ["Roughness"], 0.82)
    _noise_surface(nodes, mat.node_tree.links, bsdf, scale=90.0, detail=4.0, roughness_low=0.72, roughness_high=0.88, bump_strength=0.22, stretch=(1.0, 1.0, 1.0))
    return mat


def _material_for(name: str):
    lowered = name.lower()
    if "rubber" in lowered:
        return _material_rubber(), "rubber"
    if "plastic" in lowered:
        return _material_plastic(), "plastic"
    return _material_aluminum(), "aluminum"


def _track(obj, target) -> None:
    constraint = obj.constraints.new("TRACK_TO")
    constraint.target = target
    constraint.track_axis = "TRACK_NEGATIVE_Z"
    constraint.up_axis = "UP_Y"


def _light(name: str, location: Vector, target, energy: float, size: float, color=(1.0, 1.0, 1.0), shape="SQUARE", size_y=None):
    data = bpy.data.lights.new(name, type="AREA")
    data.energy = energy
    data.shape = shape
    data.size = size
    if size_y is not None:
        try:
            data.size_y = size_y
        except Exception:
            pass
    data.color = color
    obj = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = location
    _track(obj, target)
    return obj


def _setup_world() -> None:
    scene = bpy.context.scene
    world = bpy.data.worlds.new("LearnCad World") if scene.world is None else scene.world
    scene.world = world
    world.use_nodes = True
    nodes = world.node_tree.nodes
    links = world.node_tree.links
    nodes.clear()
    output = nodes.new("ShaderNodeOutputWorld")
    background = nodes.new("ShaderNodeBackground")
    background.inputs["Strength"].default_value = 0.62
    texcoord = nodes.new("ShaderNodeTexCoord")
    separate = nodes.new("ShaderNodeSeparateXYZ")
    ramp = nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.0
    ramp.color_ramp.elements[0].color = (0.008, 0.007, 0.006, 1.0)
    ramp.color_ramp.elements[1].position = 0.52
    ramp.color_ramp.elements[1].color = (0.19, 0.095, 0.045, 1.0)
    top = ramp.color_ramp.elements.new(0.82)
    top.color = (0.025, 0.042, 0.070, 1.0)
    links.new(texcoord.outputs["Generated"], separate.inputs["Vector"])
    links.new(separate.outputs["Z"], ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], background.inputs["Color"])
    links.new(background.outputs["Background"], output.inputs["Surface"])


def _setup_camera(center: Vector, size: float):
    scene = bpy.context.scene
    target = bpy.data.objects.new("LearnCad Center", None)
    bpy.context.scene.collection.objects.link(target)
    target.location = center

    data = bpy.data.cameras.new("LearnCad Camera")
    data.lens = 58
    data.sensor_width = 36
    camera = bpy.data.objects.new("LearnCad Camera", data)
    bpy.context.scene.collection.objects.link(camera)
    direction = Vector((1.15, -1.55, 0.82)).normalized()
    # Keep generous breathing room around the part; presentations read better
    # with the whole silhouette and some floor visible.
    camera.location = center + direction * (size * 5.6)
    _track(camera, target)
    scene.camera = camera
    return target


def _setup_lights(center: Vector, size: float, target) -> None:
    warm = (1.0, 0.84, 0.68)
    cool = (0.66, 0.80, 1.0)
    orange = (1.0, 0.52, 0.20)
    white = (1.0, 0.98, 0.95)

    _light("LearnCad Key", center + Vector((1.8, -2.4, 2.8)) * size, target, energy=680, size=size * 3.2, color=warm)
    _light("LearnCad Fill", center + Vector((-2.6, -1.4, 1.5)) * size, target, energy=230, size=size * 4.2, color=cool)
    _light("LearnCad Rim", center + Vector((0.2, 2.8, 2.4)) * size, target, energy=460, size=size * 2.2, color=orange)
    _light("LearnCad Top", center + Vector((0.0, 0.3, 3.3)) * size, target, energy=310, size=size * 5.0, color=white)
    _light(
        "LearnCad Strip",
        center + Vector((-2.8, 1.8, 1.4)) * size,
        target,
        energy=280,
        size=size * 0.26,
        color=white,
        shape="RECTANGLE",
        size_y=size * 3.8,
    )
    _light(
        "LearnCad Cool Strip",
        center + Vector((2.8, 1.5, 1.5)) * size,
        target,
        energy=220,
        size=size * 0.24,
        color=cool,
        shape="RECTANGLE",
        size_y=size * 3.4,
    )

    sun_data = bpy.data.lights.new("LearnCad Sun", type="SUN")
    sun_data.energy = 2.8
    sun_data.angle = math.radians(13)
    sun = bpy.data.objects.new("LearnCad Sun", sun_data)
    bpy.context.scene.collection.objects.link(sun)
    sun.rotation_euler = (math.radians(48), 0, math.radians(32))


def _emission_plane(name: str, location: Vector, rotation, size_x: float, size_y: float, strength: float):
    bpy.ops.mesh.primitive_plane_add(size=1.0, location=location, rotation=rotation)
    plane = bpy.context.active_object
    plane.name = name
    plane.scale = (size_x, size_y, 1.0)
    mat = bpy.data.materials.new(name + " Emitter")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    nodes.clear()
    output = nodes.new("ShaderNodeOutputMaterial")
    emission = nodes.new("ShaderNodeEmission")
    emission.inputs["Color"].default_value = (1.0, 0.96, 0.90, 1.0)
    emission.inputs["Strength"].default_value = strength
    mat.node_tree.links.new(emission.outputs["Emission"], output.inputs["Surface"])
    plane.data.materials.append(mat)
    return plane


def _setup_softboxes(center: Vector, size: float) -> None:
    # Large emitters give metal something bright to reflect and lift the shadows.
    _emission_plane(
        "LearnCad Front Softbox",
        center + Vector((0.0, -4.0, 1.6)) * size,
        (math.radians(-90), 0, 0),
        size * 2.8,
        size * 2.2,
        3.6,
    )
    _emission_plane(
        "LearnCad Top Softbox",
        center + Vector((0.0, 0.0, 3.4)) * size,
        (math.radians(180), 0, 0),
        size * 3.6,
        size * 3.6,
        2.8,
    )
    _emission_plane(
        "LearnCad Side Strip",
        center + Vector((-3.0, 0.4, 1.2)) * size,
        (0, math.radians(90), 0),
        size * 0.45,
        size * 2.8,
        4.4,
    )
    _emission_plane(
        "LearnCad Rear Strip",
        center + Vector((3.0, 0.6, 1.3)) * size,
        (0, math.radians(90), 0),
        size * 0.35,
        size * 2.4,
        3.2,
    )


def _setup_ground(minimum: Vector, center: Vector, size: float) -> None:
    bpy.ops.mesh.primitive_plane_add(size=size * 10.0, location=(center.x, center.y, minimum.z - size * 0.002))
    ground = bpy.context.active_object
    ground.name = "LearnCad Ground"
    mat, bsdf, nodes = _new_material("LearnCad Ground")
    _set(bsdf, ["Base Color"], (0.075, 0.070, 0.064, 1.0))
    _set(bsdf, ["Metallic"], 0.0)
    _set(bsdf, ["Roughness"], 0.31)
    ground.data.materials.append(mat)


def _setup_backdrop(center: Vector, size: float) -> None:
    bpy.ops.mesh.primitive_plane_add(size=size * 12.0, location=(center.x, center.y + size * 4.2, center.z + size * 0.8))
    backdrop = bpy.context.active_object
    backdrop.name = "LearnCad Backdrop"
    backdrop.rotation_euler = (math.radians(90), 0, 0)
    mat, bsdf, nodes = _new_material("LearnCad Backdrop")
    _set(bsdf, ["Base Color"], (0.028, 0.025, 0.022, 1.0))
    _set(bsdf, ["Metallic"], 0.0)
    _set(bsdf, ["Roughness"], 0.55)
    backdrop.data.materials.append(mat)


def _bevel_and_smooth(obj, size: float) -> None:
    bevel = obj.modifiers.new("LearnCad Bevel", "BEVEL")
    bevel.width = size * 0.006
    bevel.segments = 3
    bevel.limit_method = "ANGLE"
    bevel.angle_limit = math.radians(30)
    try:
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        bpy.ops.object.shade_smooth()
    except Exception:
        pass
    try:
        bpy.ops.object.shade_auto_smooth(angle=math.radians(30))
    except Exception:
        try:
            obj.data.use_auto_smooth = True
            obj.data.auto_smooth_angle = math.radians(30)
        except Exception:
            pass


def _configure_viewports() -> None:
    try:
        for screen in bpy.data.screens:
            for area in screen.areas:
                if area.type != "VIEW_3D":
                    continue
                for space in area.spaces:
                    if space.type != "VIEW_3D":
                        continue
                    try:
                        space.shading.type = "MATERIAL"
                    except Exception:
                        pass
                    try:
                        space.region_3d.view_perspective = "CAMERA"
                    except Exception:
                        pass
    except Exception:
        pass


def _setup_render(output: str, engine: str, width: int, height: int, samples: int) -> str:
    scene = bpy.context.scene
    requested = engine.upper()
    chosen = ""
    if requested in ("EEVEE", "BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
        candidates = ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE")
    else:
        candidates = ("CYCLES", "BLENDER_EEVEE_NEXT", "BLENDER_EEVEE")
    for candidate in candidates:
        try:
            scene.render.engine = candidate
            chosen = candidate
            break
        except Exception:
            continue
    if not chosen:
        scene.render.engine = "CYCLES"
        chosen = "CYCLES"

    if chosen == "CYCLES":
        try:
            scene.cycles.samples = samples
            scene.cycles.use_denoising = True
            scene.cycles.use_adaptive_sampling = True
            scene.cycles.adaptive_threshold = 0.02
            scene.cycles.device = "CPU"
            scene.cycles.max_bounces = 8
            scene.cycles.diffuse_bounces = 4
            scene.cycles.glossy_bounces = 6
            scene.cycles.transmission_bounces = 4
        except Exception:
            pass
    else:
        try:
            scene.eevee.taa_render_samples = samples
        except Exception:
            pass
        for attr, value in (
            ("use_gtao", True),
            ("use_shadows", True),
            ("use_soft_shadows", True),
            ("use_raytracing", True),
        ):
            try:
                setattr(scene.eevee, attr, value)
            except Exception:
                pass
        try:
            scene.eevee.ray_tracing_options.use_denoise = True
            scene.eevee.ray_tracing_options.trace_max_roughness = 0.6
        except Exception:
            pass

    scene.render.resolution_x = width
    scene.render.resolution_y = height
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.film_transparent = False
    scene.render.filepath = output
    try:
        scene.view_settings.view_transform = "AgX"
        scene.view_settings.look = "AgX - Medium High Contrast"
    except Exception:
        pass
    try:
        scene.view_settings.exposure = 0.0
    except Exception:
        pass
    return chosen


def main() -> int:
    args = _args()
    if len(args) < 2:
        print("Usage: learncad_render.py -- model.stl output.png [engine] [width] [height] [samples] [material]")
        return 2
    model = args[0]
    output = args[1]
    engine = args[2] if len(args) > 2 else "CYCLES"
    width = int(args[3]) if len(args) > 3 else 1200
    height = int(args[4]) if len(args) > 4 else 800
    samples = int(args[5]) if len(args) > 5 else 64
    material_name = args[6] if len(args) > 6 else "aluminum"
    blend_path = args[7] if len(args) > 7 else ""

    _clear()
    _setup_world()
    obj = _import_model(model)
    minimum, maximum, size = _bounds(obj)
    center = (minimum + maximum) * 0.5

    _bevel_and_smooth(obj, size)
    material, used_material = _material_for(material_name)
    obj.data.materials.append(material)
    _setup_ground(minimum, center, size)
    _setup_backdrop(center, size)
    _setup_softboxes(center, size)
    target = _setup_camera(center, size)
    _setup_lights(center, size, target)
    chosen = _setup_render(output, engine, width, height, samples)
    if blend_path:
        try:
            _configure_viewports()
            bpy.ops.wm.save_as_mainfile(filepath=blend_path)
            print(f"LEARNCAD_BLEND={blend_path}")
        except Exception as exc:
            print(f"LEARNCAD_BLEND_ERROR={exc}")
    print(f"LEARNCAD_ENGINE={chosen}")
    print(f"LEARNCAD_MATERIAL={used_material}")
    bpy.ops.render.render(write_still=True)
    print("LEARNCAD_RENDER_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
