from __future__ import annotations

__all__ = [
    "StanSetupPanel",
    "StanCharactersPanel",
    "StanAnimationPanel",
    "StanViewportPanel",
]

from pathlib import Path

import bpy

from soulstruct.blender.bpy_base.panel import SoulstructPanel
from soulstruct.blender.general.properties import SoulstructSettings
from soulstruct.blender.stan_tools.character_search import _iter_chr_directories
from soulstruct.blender.animation.export_operators import ExportCharacterHKXAnimation

from .character_search import StanSearchCharacterToImport
from .animation_search import StanSearchCharacterAnimation
from .operators import (
    AutoDetectGameDirectory,
    StanRefreshNpcParamList,
    StanApplyNpcParamDrawMask,
    StanShowAllCharacterMeshes,
    StanApplySceneLighting,
    StanRemoveSceneLighting,
)
from .npc_param import _resolve_npc_param_xml_path
from .scene_lighting import is_scene_lighting_active

STAN_TOOLS_CATEGORY = "Stan's Tools"


class _StanToolsPanel(SoulstructPanel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = STAN_TOOLS_CATEGORY


class StanSetupPanel(_StanToolsPanel):
    bl_label = "Setup"
    bl_idname = "VIEW_PT_stan_tools_setup"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        settings = context.scene.soulstruct_settings
        export_settings = context.scene.animation_export_settings

        layout.label(text="Game & folders for animation modding", icon="INFO")

        layout.prop(settings, "game_enum")
        game = settings.game
        if not game:
            layout.label(text="Unsupported game.", icon="ERROR")
            return

        row = layout.row(align=True)
        row.label(text="Game Root:")
        row.operator(AutoDetectGameDirectory.bl_idname, text="", icon="VIEWZOOM")
        layout.prop(settings, settings.get_game_root_prop_name(), text="")

        layout.label(text="Project Root (optional export workspace):")
        layout.prop(settings, settings.get_project_root_prop_name(), text="")

        layout.label(text="Mod Folder (DSAS / ModEngine):")
        layout.prop(settings, settings.get_mod_root_prop_name(), text="")

        layout.prop(settings, "prefer_import_from_project")
        layout.prop(export_settings, "auto_repack_to_mod")

        stan = context.scene.stan_tools_settings
        layout.label(text="NpcParam (mesh visibility states):")
        layout.prop(stan, "npc_param_xml_path", text="")
        xml_path = _resolve_npc_param_xml_path(settings, stan)
        if xml_path:
            layout.label(text=f"Using: {xml_path.name}", icon="CHECKMARK")
        elif stan.npc_param_xml_path or settings.project_root_path:
            layout.label(text="NpcParam.param.xml not found", icon="ERROR")

        chr_dirs = _iter_chr_directories(settings)
        if chr_dirs:
            count = sum(1 for d in chr_dirs for _ in d.glob("c*.chrbnd*"))
            layout.label(text=f"chr\\ found: {count} binder(s) in {len(chr_dirs)} folder(s)", icon="CHECKMARK")
        elif settings.game_root_path or settings.project_root_path:
            layout.label(text="chr\\ missing — set Game Root to unpacked .../Game", icon="ERROR")
        else:
            layout.label(text="Set Game Root or use Auto-Detect", icon="ERROR")


class StanCharactersPanel(_StanToolsPanel):
    bl_label = "Characters"
    bl_idname = "VIEW_PT_stan_tools_characters"

    @classmethod
    def poll(cls, context):
        return SoulstructSettings.from_context(context).has_import_dir_path("chr")

    def draw(self, context):
        layout = self.layout
        layout.label(text="Search by name or c#### id, then import the model")
        layout.operator(StanSearchCharacterToImport.bl_idname, icon="VIEWZOOM")
        layout.label(text="Load animation (uses last imported c####):")
        layout.operator(StanSearchCharacterAnimation.bl_idname, icon="ANIM")

        stan = context.scene.stan_tools_settings
        box = layout.box()
        box.label(text="NPC Param Selection (mesh visibility)", icon="MODIFIER")
        if stan.character_model:
            box.label(text=f"Character: {stan.character_model}")
        row = box.row(align=True)
        row.prop(stan, "npc_param_row_id", text="")
        row.operator(StanRefreshNpcParamList.bl_idname, text="", icon="FILE_REFRESH")
        row = box.row(align=True)
        row.operator(StanApplyNpcParamDrawMask.bl_idname, icon="HIDE_OFF")
        row.operator(StanShowAllCharacterMeshes.bl_idname, icon="RESTRICT_VIEW_OFF")
        box.label(text="NPC Param applies on selection; Apply re-runs if needed")


class StanAnimationPanel(_StanToolsPanel):
    bl_label = "Animation"
    bl_idname = "VIEW_PT_stan_tools_animation"

    @classmethod
    def poll(cls, context):
        return SoulstructSettings.from_context(context).game_config.supports_animation

    def draw(self, context):
        layout = self.layout
        settings = context.scene.soulstruct_settings
        export_settings = context.scene.animation_export_settings

        if not settings.game_config.supports_animation:
            layout.label(text="Animation not supported for this game.")
            return

        layout.prop(export_settings, "selected_frames_only")
        layout.label(text="Export active action on selected character armature:")
        self.maybe_draw_export_operator(
            context,
            ExportCharacterHKXAnimation.bl_idname,
            text="Export Character Animation",
            icon="EXPORT",
        )
        if settings.mod_root_path:
            layout.label(text=f"Mod copy: {settings.mod_root_path / 'chr'}", icon="FILE_FOLDER")
        elif export_settings.auto_repack_to_mod:
            layout.label(text="Set Mod Folder in Setup to auto-copy ANIBND", icon="ERROR")


class StanViewportPanel(_StanToolsPanel):
    bl_label = "Viewport"
    bl_idname = "VIEW_PT_stan_tools_viewport"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        stan = context.scene.stan_tools_settings

        layout.label(
            text="3-point lights + world sky for Material Preview / Rendered",
            icon="LIGHT_SUN",
        )

        layout.prop(stan, "scene_lighting_sky_strength")
        layout.prop(stan, "scene_lighting_key_energy")
        layout.prop(stan, "scene_lighting_fill_energy")
        layout.prop(stan, "scene_lighting_rim_energy")
        layout.prop(stan, "scene_lighting_hdri_path", text="HDRI")

        row = layout.row(align=True)
        row.operator(StanApplySceneLighting.bl_idname, icon="LIGHT_AREA")
        row.operator(StanRemoveSceneLighting.bl_idname, icon="TRASH")

        if is_scene_lighting_active():
            layout.label(text="Scene lighting: ON", icon="CHECKMARK")
        else:
            layout.label(text="Scene lighting: OFF", icon="BLANK1")
