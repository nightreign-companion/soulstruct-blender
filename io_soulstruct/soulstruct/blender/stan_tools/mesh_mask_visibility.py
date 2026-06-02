"""Split merged FLVER meshes by material mask and toggle visibility from NpcParam draw masks."""
from __future__ import annotations

import bpy

from soulstruct.flver.material import Material

from .npc_param import DRAW_MASK_COUNT

_MESH_SPLIT_PROP = "stan_mesh_mask_split"
_SOURCE_MESH_PROP = "stan_source_mesh"
_DISPLAY_MASK_PROP = "stan_display_mask"


def material_display_mask_id(material: bpy.types.Material | None) -> int | None:
    if material is None:
        return None
    if match := Material.DISPLAY_MASK_RE.match(material.name):
        return int(match.group(1))
    return None


def _mesh_object_mask_id(mesh_obj: bpy.types.Object) -> int:
    """Return display mask id for a mesh object, or -1 if always visible (no mask / mixed)."""
    mesh = mesh_obj.data
    if not isinstance(mesh, bpy.types.Mesh) or not mesh.materials:
        return -1

    mask_ids: set[int | None] = set()
    used_indices = {poly.material_index for poly in mesh.polygons}
    for mat_index in used_indices:
        if mat_index >= len(mesh.materials):
            continue
        mask_ids.add(material_display_mask_id(mesh.materials[mat_index]))

    mask_ids.discard(None)
    if len(mask_ids) == 1:
        return next(iter(mask_ids))
    if not mask_ids:
        return -1
    return -1


def _copy_armature_modifier(source: bpy.types.Object, target: bpy.types.Object, armature: bpy.types.Object) -> None:
    for mod in source.modifiers:
        if mod.type != "ARMATURE":
            continue
        new_mod = target.modifiers.new(name=mod.name, type="ARMATURE")
        new_mod.object = armature
        break
    else:
        new_mod = target.modifiers.new(name="Armature", type="ARMATURE")
        new_mod.object = armature


def ensure_mesh_parts_split(context: bpy.types.Context, armature_obj: bpy.types.Object) -> None:
    """Split a single merged FLVER mesh into per-material objects so masks can be toggled."""
    if armature_obj.get(_MESH_SPLIT_PROP):
        return

    mesh_children = [child for child in armature_obj.children if child.type == "MESH"]
    if len(mesh_children) != 1:
        armature_obj[_MESH_SPLIT_PROP] = True
        for child in mesh_children:
            if _DISPLAY_MASK_PROP not in child:
                child[_DISPLAY_MASK_PROP] = _mesh_object_mask_id(child)
        return

    source = mesh_children[0]
    view_layer = context.view_layer
    prev_active = view_layer.objects.active
    prev_mode = prev_active.mode if prev_active else "OBJECT"
    prev_selection = {obj: obj.select_get() for obj in view_layer.objects}

    try:
        for obj in view_layer.objects:
            obj.select_set(False)
        source.select_set(True)
        view_layer.objects.active = source
        if bpy.ops.object.mode_set.poll():
            bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.mesh.separate(type="MATERIAL")
        if bpy.ops.object.mode_set.poll():
            bpy.ops.object.mode_set(mode="OBJECT")
    except Exception:
        armature_obj[_MESH_SPLIT_PROP] = True
        source[_DISPLAY_MASK_PROP] = _mesh_object_mask_id(source)
        raise

    split_objects = [obj for obj in view_layer.objects if obj.select_get() and obj.type == "MESH"]
    if len(split_objects) <= 1:
        armature_obj[_MESH_SPLIT_PROP] = True
        source[_DISPLAY_MASK_PROP] = _mesh_object_mask_id(source)
        return

    for obj in split_objects:
        obj[_DISPLAY_MASK_PROP] = _mesh_object_mask_id(obj)
        obj.parent = armature_obj
        _copy_armature_modifier(source, obj, armature_obj)
        for collection in source.users_collection:
            if obj.name not in collection.objects:
                collection.objects.link(obj)

    source.hide_viewport = True
    source.hide_render = True
    source[_SOURCE_MESH_PROP] = True
    armature_obj[_MESH_SPLIT_PROP] = True

    for obj, was_selected in prev_selection.items():
        obj.select_set(was_selected)
    if prev_active:
        view_layer.objects.active = prev_active
        if prev_active.mode != prev_mode and bpy.ops.object.mode_set.poll():
            try:
                bpy.ops.object.mode_set(mode=prev_mode)
            except RuntimeError:
                pass


def apply_draw_mask_to_character(
    armature_obj: bpy.types.Object,
    draw_mask: tuple[bool, ...],
    context: bpy.types.Context,
) -> tuple[int, int]:
    """Set viewport/render visibility on mask-split mesh children."""
    ensure_mesh_parts_split(context, armature_obj)

    shown = hidden = 0
    for child in armature_obj.children:
        if child.type != "MESH" or child.get(_SOURCE_MESH_PROP):
            continue

        mask_id = int(child.get(_DISPLAY_MASK_PROP, -1))
        if mask_id < 0:
            visible = True
        else:
            visible = mask_id < DRAW_MASK_COUNT and draw_mask[mask_id]

        child.hide_viewport = not visible
        child.hide_render = not visible
        if visible:
            shown += 1
        else:
            hidden += 1
    return shown, hidden


def show_all_character_meshes(armature_obj: bpy.types.Object) -> int:
    count = 0
    for child in armature_obj.children:
        if child.type != "MESH" or child.get(_SOURCE_MESH_PROP):
            continue
        child.hide_viewport = False
        child.hide_render = False
        count += 1
    return count
