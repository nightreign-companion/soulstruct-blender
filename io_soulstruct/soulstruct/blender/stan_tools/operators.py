from __future__ import annotations

__all__ = [
    "AutoDetectGameDirectory",
    "StanRefreshNpcParamList",
    "StanApplyNpcParamDrawMask",
    "StanShowAllCharacterMeshes",
]

from pathlib import Path

import bpy

from soulstruct.blender.general.properties import SoulstructSettings
from soulstruct.blender.utilities import LoggingOperator

from .steam_paths import detect_game_root
from .mesh_mask_visibility import show_all_character_meshes
from .npc_param import find_character_armature, _resolve_npc_param_xml_path


class AutoDetectGameDirectory(LoggingOperator):
    """Find the game install via Steam and set Game Root (+ default Mod Folder)."""

    bl_idname = "stan_tools.auto_detect_game_dir"
    bl_label = "Auto-Detect Game Directory"
    bl_description = (
        "Scan Steam library folders for the selected game's install and set Game Root. "
        "If Mod Folder is empty, defaults to <Game Root>/mod"
    )

    def execute(self, context):
        settings = SoulstructSettings.from_context(context)
        game = settings.game
        if not game:
            return self.error("Select a game first.")

        root = detect_game_root(game.variable_name)
        if root is None:
            return self.warning(
                f"Could not find {game.name} under Steam libraries. Set Game Root manually."
            )

        prop_name = settings.get_game_root_prop_name()
        setattr(settings, prop_name, str(root))
        settings.auto_set_game()
        self.info(f"Set game root: {root}")

        mod_prop = settings.get_mod_root_prop_name()
        if not getattr(settings, mod_prop, ""):
            mod_path = root / "mod"
            setattr(settings, mod_prop, str(mod_path))
            self.info(f"Set mod folder: {mod_path}")

        return {"FINISHED"}


class StanRefreshNpcParamList(LoggingOperator):
    """Reload NpcParam rows for the active character from NpcParam.param.xml."""

    bl_idname = "stan_tools.refresh_npc_param_list"
    bl_label = "Refresh NPC Param List"
    bl_description = "Reload NpcParam variants for the selected character from NpcParam.param.xml"

    def execute(self, context):
        stan = context.scene.stan_tools_settings
        settings = SoulstructSettings.from_context(context)
        if not _resolve_npc_param_xml_path(settings, context.scene.stan_tools_settings):
            return self.warning(
                "NpcParam.param.xml not found. Set NpcParam XML in Setup or add "
                "regulation-bin/NpcParam.param.xml under Project Root."
            )
        if stan.refresh_npc_param_list(context):
            self.info(f"Loaded NPC Param rows for {stan.character_model}.")
            return {"FINISHED"}
        return self.warning("Could not find NPC Param rows. Import a character (c####) first.")


class StanApplyNpcParamDrawMask(LoggingOperator):
    """Apply the selected NpcParam draw mask to character mesh visibility."""

    bl_idname = "stan_tools.apply_npc_param_draw_mask"
    bl_label = "Apply NPC Param Visibility"
    bl_description = "Show/hide FLVER mesh parts using the selected NpcParam model display masks"

    def execute(self, context):
        stan = context.scene.stan_tools_settings
        err = stan.apply_active_npc_param(context)
        if err:
            return self.warning(err)
        armature = find_character_armature(context, stan.character_model)
        if armature and armature.get("stan_mesh_mask_split"):
            self.info("Updated mesh visibility (split by material / display mask).")
        else:
            self.info("Updated mesh visibility from NPC Param draw mask.")
        return {"FINISHED"}


class StanShowAllCharacterMeshes(LoggingOperator):
    """Show all mesh children of the active character (ignore draw masks)."""

    bl_idname = "stan_tools.show_all_character_meshes"
    bl_label = "Show All Meshes"
    bl_description = "Unhide every mesh part of the active character armature"

    def execute(self, context):
        stan = context.scene.stan_tools_settings
        if not stan.character_model:
            return self.warning("No active character. Import one first.")
        armature = find_character_armature(context, stan.character_model)
        if armature is None:
            return self.warning(f"Armature not found for {stan.character_model}.")
        count = show_all_character_meshes(armature)
        self.info(f"Showing {count} mesh object(s).")
        return {"FINISHED"}