from __future__ import annotations

__all__ = [
    "AnimationExportSettings",
]

import bpy


class AnimationExportSettings(bpy.types.PropertyGroup):

    selected_frames_only: bpy.props.BoolProperty(
        name="Selected Frames Only",
        description="Export only frames between current start and end (inclusive) of Blender timeline. Otherwise, "
                    "first to last keyframe times will be exported",
        default=False,
    )
