"""Scene properties for Stan's Tools."""
from __future__ import annotations

__all__ = [
    "StanToolsSettings",
]

import bpy

from soulstruct.blender.bpy_base.property_group import SoulstructPropertyGroup
from soulstruct.blender.animation.utilities import get_active_flver_or_part_armature

from .mesh_mask_visibility import apply_draw_mask_to_character, show_all_character_meshes
from .npc_param import find_character_armature, get_npc_param_variants_for_model
from .scene_lighting import is_scene_lighting_active


def _npc_param_enum_items(self, context) -> list[tuple[str, str, str]]:
    return StanToolsSettings._npc_param_items


def _on_npc_param_row_changed(self, context: bpy.types.Context) -> None:
    """Apply draw mask when the user picks a row (skipped during import list refresh)."""
    if StanToolsSettings._suppress_npc_param_update:
        return
    if not self.npc_param_row_id or not self.character_model:
        return
    self.apply_active_npc_param(context)


class StanToolsSettings(SoulstructPropertyGroup):
    """Per-scene settings for Stan's Tools workflow."""

    _npc_param_items: list[tuple[str, str, str]] = [("", "<none>", "")]
    _suppress_npc_param_update: bool = False

    npc_param_xml_path: bpy.props.StringProperty(
        name="NpcParam XML",
        description=(
            "Optional path to Witchy NpcParam.param.xml (e.g. regulation-bin from souls-script-kt). "
            "If empty, searches Project Root/regulation-bin/ and Game Root"
        ),
        subtype="FILE_PATH",
        default="",
    )

    character_model: bpy.props.StringProperty(
        name="Active Character",
        description="Last imported character model stem (c####)",
        default="",
    )

    npc_param_row_id: bpy.props.EnumProperty(
        name="NPC Param",
        description="NpcParam row controlling which #XX# masked mesh parts are visible (like DSAS)",
        items=_npc_param_enum_items,
    )

    scene_lighting_sky_strength: bpy.props.FloatProperty(
        name="Sky Strength",
        description="World background strength for procedural sky or HDRI",
        default=0.4,
        min=0.0,
        max=5.0,
    )

    scene_lighting_key_energy: bpy.props.FloatProperty(
        name="Key Light",
        description="Energy of the warm key area light",
        default=800.0,
        min=0.0,
        max=10000.0,
    )

    scene_lighting_fill_energy: bpy.props.FloatProperty(
        name="Fill Light",
        description="Energy of the cool fill area light",
        default=200.0,
        min=0.0,
        max=10000.0,
    )

    scene_lighting_rim_energy: bpy.props.FloatProperty(
        name="Rim Light",
        description="Energy of the rim area light behind the subject",
        default=400.0,
        min=0.0,
        max=10000.0,
    )

    scene_lighting_hdri_path: bpy.props.StringProperty(
        name="HDRI (optional)",
        description="Optional environment map image; uses procedural sky when empty",
        subtype="FILE_PATH",
        default="",
    )

    def scene_lighting_is_active(self, context: bpy.types.Context) -> bool:
        """True when StanTools viewport lighting collection is present."""
        del context
        return is_scene_lighting_active()

    def _set_npc_param_row_id(self, row_id: str) -> None:
        """Assign enum by identifier; avoids TypeError when items just changed."""
        StanToolsSettings._suppress_npc_param_update = True
        try:
            self["npc_param_row_id"] = row_id
        finally:
            StanToolsSettings._suppress_npc_param_update = False

    def refresh_npc_param_list(self, context: bpy.types.Context, model_stem: str | None = None) -> bool:
        """Rebuild NPC Param enum for `model_stem` (or current character_model)."""
        if model_stem:
            self.character_model = model_stem
        elif not self.character_model:
            armature, _, name, is_part = get_active_flver_or_part_armature(context)
            if armature and name.startswith("c") and not is_part:
                self.character_model = name[:5].lower() if len(name) >= 5 else name.lower()

        if not self.character_model:
            StanToolsSettings._npc_param_items = [("", "<import a character>", "")]
            self._set_npc_param_row_id("")
            return False

        settings = context.scene.soulstruct_settings
        variants = get_npc_param_variants_for_model(settings, self, self.character_model)
        if not variants:
            StanToolsSettings._npc_param_items = [
                (
                    "",
                    "<no NpcParam — optional for ER/NR mesh masks>",
                    "DS1/DSR/DeS do not use NpcParam draw masks; ER/NR: point to NpcParam.param.xml",
                )
            ]
            self._set_npc_param_row_id("")
            return False

        StanToolsSettings._npc_param_items = [
            (str(v.row_id), v.label, f"NpcParam row {v.row_id}") for v in variants
        ]
        valid_ids = {item[0] for item in StanToolsSettings._npc_param_items}
        if self.npc_param_row_id not in valid_ids:
            self._set_npc_param_row_id(StanToolsSettings._npc_param_items[0][0])
        return True

    def apply_active_npc_param(self, context: bpy.types.Context) -> str | None:
        """Apply draw mask for current enum selection. Returns error message or None."""
        if not self.character_model or not self.npc_param_row_id:
            return "Select an NPC Param row."
        armature = find_character_armature(context, self.character_model)
        if armature is None:
            return f"Could not find armature for {self.character_model}."
        for variant in get_npc_param_variants_for_model(context.scene.soulstruct_settings, self, self.character_model):
            if str(variant.row_id) == self.npc_param_row_id:
                apply_draw_mask_to_character(armature, variant.draw_mask, context)
                return None
        return "NPC Param row not found."
