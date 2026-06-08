"""Viewport scene lighting for Stan's Tools (3-point + world sky/HDRI)."""
from __future__ import annotations

__all__ = [
    "STAN_LIGHTING_COLLECTION",
    "is_scene_lighting_active",
    "get_lighting_target_location",
    "apply_scene_lighting",
    "remove_scene_lighting",
]

import os
from mathutils import Vector

import bpy

STAN_LIGHTING_COLLECTION = "StanTools_Lighting"

STAN_KEY_LIGHT = "Stan_Key"
STAN_FILL_LIGHT = "Stan_Fill"
STAN_RIM_LIGHT = "Stan_Rim"

_KEY_COLOR = (1.0, 0.95, 0.88, 1.0)
_FILL_COLOR = (0.82, 0.9, 1.0, 1.0)
_RIM_COLOR = (1.0, 0.98, 0.95, 1.0)

_STUDIO_BG_COLOR = (0.03, 0.03, 0.035, 1.0)
_STUDIO_BG_STRENGTH = 0.25

_LIGHT_SETUP = (
    (STAN_KEY_LIGHT, (2.5, -2.0, 2.8), _KEY_COLOR, "scene_lighting_key_energy", 2.5),
    (STAN_FILL_LIGHT, (-2.5, -1.5, 2.0), _FILL_COLOR, "scene_lighting_fill_energy", 2.0),
    (STAN_RIM_LIGHT, (0.0, 2.5, 2.5), _RIM_COLOR, "scene_lighting_rim_energy", 2.0),
)


def is_scene_lighting_active() -> bool:
    """True when the StanTools lighting collection exists."""
    return STAN_LIGHTING_COLLECTION in bpy.data.collections


def _bbox_center_world(obj: bpy.types.Object) -> Vector:
    corners = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    mins = Vector((min(c[i] for c in corners) for i in range(3)))
    maxs = Vector((max(c[i] for c in corners) for i in range(3)))
    return (mins + maxs) / 2.0


def _objects_bbox_center(objects: list[bpy.types.Object]) -> Vector | None:
    if not objects:
        return None
    all_corners: list[Vector] = []
    for obj in objects:
        all_corners.extend(obj.matrix_world @ Vector(corner) for corner in obj.bound_box)
    if not all_corners:
        return None
    mins = Vector((min(c[i] for c in all_corners) for i in range(3)))
    maxs = Vector((max(c[i] for c in all_corners) for i in range(3)))
    return (mins + maxs) / 2.0


def get_lighting_target_location(context: bpy.types.Context, stan_settings) -> Vector:
    """Center of character armature bbox, else active object, else default."""
    if stan_settings.character_model:
        from .npc_param import find_character_armature

        armature = find_character_armature(context, stan_settings.character_model)
        if armature is not None:
            meshes = [
                child for child in armature.children
                if child.type == "MESH" and child.visible_get()
            ]
            center = _objects_bbox_center([armature, *meshes])
            if center is not None:
                return center

    if context.active_object is not None:
        return _bbox_center_world(context.active_object)

    return Vector((0.0, 0.0, 1.0))


def _get_or_create_lighting_collection(scene: bpy.types.Scene) -> bpy.types.Collection:
    coll = bpy.data.collections.get(STAN_LIGHTING_COLLECTION)
    if coll is None:
        coll = bpy.data.collections.new(STAN_LIGHTING_COLLECTION)
        scene.collection.children.link(coll)
    elif coll.name not in [c.name for c in scene.collection.children]:
        scene.collection.children.link(coll)
    return coll


def _get_or_create_area_light(
    coll: bpy.types.Collection,
    name: str,
) -> bpy.types.Object:
    obj = bpy.data.objects.get(name)
    if obj is None:
        light_data = bpy.data.lights.new(name=name, type="AREA")
        obj = bpy.data.objects.new(name, light_data)
        coll.objects.link(obj)
    elif obj.name not in coll.objects:
        coll.objects.link(obj)
    if obj.data is None or obj.data.type != "AREA":
        if obj.data:
            bpy.data.lights.remove(obj.data)
        obj.data = bpy.data.lights.new(name=f"{name}_data", type="AREA")
    return obj


def _look_at(obj: bpy.types.Object, target: Vector) -> None:
    direction = target - obj.location
    if direction.length > 1e-6:
        obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def _configure_lights(
    coll: bpy.types.Collection,
    target: Vector,
    stan_settings,
) -> int:
    count = 0
    for name, offset, color, energy_prop, size in _LIGHT_SETUP:
        obj = _get_or_create_area_light(coll, name)
        light = obj.data
        light.type = "AREA"
        light.color = color[:3]
        light.energy = getattr(stan_settings, energy_prop)
        light.size = size
        light.shape = "SQUARE"
        obj.location = target + Vector(offset)
        _look_at(obj, target)
        count += 1
    return count


def _sky_types_to_try() -> tuple[str, ...]:
    sky_node = getattr(bpy.types, "ShaderNodeTexSky", None)
    if sky_node is None:
        return ()
    prop = sky_node.bl_rna.properties.get("sky_type")
    if prop is None:
        return ("NISHITA",)
    available = {item.identifier for item in prop.enum_items}
    order = ("NISHITA", "PREETHAM", "HOSEK_WILKIE", "HOSEK")
    preferred = tuple(candidate for candidate in order if candidate in available)
    if preferred:
        return preferred
    return (next(iter(available)),) if available else ("NISHITA",)


def _configure_world(
    world: bpy.types.World,
    stan_settings,
) -> None:
    world.use_nodes = True
    tree = world.node_tree
    tree.nodes.clear()

    output = tree.nodes.new("ShaderNodeOutputWorld")
    output.location = (300, 0)
    background = tree.nodes.new("ShaderNodeBackground")
    background.location = (0, 0)
    background.inputs["Strength"].default_value = stan_settings.scene_lighting_sky_strength

    hdri_path = bpy.path.abspath(stan_settings.scene_lighting_hdri_path)
    if hdri_path and os.path.isfile(hdri_path):
        env = tree.nodes.new("ShaderNodeTexEnvironment")
        env.location = (-300, 0)
        try:
            env.image = bpy.data.images.load(hdri_path, check_existing=True)
        except RuntimeError:
            env.image = None
        if env.image is not None:
            tree.links.new(env.outputs["Color"], background.inputs["Color"])
        else:
            _link_sky_texture(tree, background)
    else:
        _link_sky_texture(tree, background)

    tree.links.new(background.outputs["Background"], output.inputs["Surface"])


def _link_sky_texture(tree: bpy.types.NodeTree, background: bpy.types.Node) -> None:
    sky = tree.nodes.new("ShaderNodeTexSky")
    sky.location = (-300, 0)
    for sky_type in _sky_types_to_try():
        try:
            sky.sky_type = sky_type
            break
        except (TypeError, AttributeError):
            continue
    tree.links.new(sky.outputs["Color"], background.inputs["Color"])


def _configure_studio_world(world: bpy.types.World) -> None:
    world.use_nodes = True
    tree = world.node_tree
    tree.nodes.clear()

    output = tree.nodes.new("ShaderNodeOutputWorld")
    output.location = (300, 0)
    background = tree.nodes.new("ShaderNodeBackground")
    background.location = (0, 0)
    background.inputs["Color"].default_value = _STUDIO_BG_COLOR
    background.inputs["Strength"].default_value = _STUDIO_BG_STRENGTH
    tree.links.new(background.outputs["Background"], output.inputs["Surface"])


def _hint_material_viewport_shading(context: bpy.types.Context) -> None:
    space = context.space_data
    if space is None or getattr(space, "type", None) != "VIEW_3D":
        return
    shading = getattr(space, "shading", None)
    if shading is not None and shading.type == "SOLID":
        shading.type = "MATERIAL"


def apply_scene_lighting(
    context: bpy.types.Context,
    stan_settings,
) -> tuple[int, str]:
    """Create or update 3-point lighting and world environment. Returns (light_count, message)."""
    scene = context.scene
    target = get_lighting_target_location(context, stan_settings)
    coll = _get_or_create_lighting_collection(scene)
    light_count = _configure_lights(coll, target, stan_settings)

    world = scene.world
    if world is None:
        world = bpy.data.worlds.new("StanTools_World")
        scene.world = world
    _configure_world(world, stan_settings)

    scene["stan_tools_scene_lighting_active"] = True
    _hint_material_viewport_shading(context)

    msg = f"Scene lighting applied ({light_count} lights) at {target.x:.2f}, {target.y:.2f}, {target.z:.2f}"
    return light_count, msg


def remove_scene_lighting(context: bpy.types.Context) -> None:
    """Remove StanTools lights and reset world to a simple dark studio."""
    coll = bpy.data.collections.get(STAN_LIGHTING_COLLECTION)
    if coll is not None:
        for obj in list(coll.objects):
            light_data = obj.data
            bpy.data.objects.remove(obj, do_unlink=True)
            if light_data and light_data.users == 0:
                bpy.data.lights.remove(light_data)
        bpy.data.collections.remove(coll)

    world = context.scene.world
    if world is None:
        world = bpy.data.worlds.new("StanTools_World")
        context.scene.world = world
    _configure_studio_world(world)

    context.scene["stan_tools_scene_lighting_active"] = False
