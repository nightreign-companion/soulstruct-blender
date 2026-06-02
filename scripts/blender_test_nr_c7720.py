r"""Headless Blender smoke test: Nightreign c7720 FLVER import via Soulstruct (no UI).

Run from repo root (PowerShell):

    & 'C:\Program Files\Blender Foundation\Blender 5.1\blender.exe' `
        --background --factory-startup `
        --python 'S:\_modding\tools\soulstruct-blender\scripts\blender_test_nr_c7720.py'

Use --factory-startup so Blender does not auto-enable the installed io_soulstruct add-on
(which hits GPU draw code and fails in --background).

Set env vars to override paths:

    SOULSTRUCT_BLENDER_REPO  — path to soulstruct-blender clone
    NR_GAME_ROOT              — folder containing chr\\ (e.g. ...\\NIGHTREIGN\\Game)
    NR_CHRBND                 — optional full path to c7720.chrbnd.dcx

Exits 0 on success, 1 on failure. Does not enable the full io_soulstruct add-on (avoids MSB GPU
draw handlers that break in --background).
"""

from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path


def _repo_root() -> Path:
    env = os.environ.get("SOULSTRUCT_BLENDER_REPO")
    if env:
        return Path(env).resolve()
    return Path(__file__).resolve().parents[1]


def _setup_python_path(repo: Path) -> None:
    lib = repo / "io_soulstruct_lib"
    paths = [
        repo / "io_soulstruct",
        lib / "soulstruct" / "src",
        lib / "soulstruct-havok" / "src",
    ]
    for p in paths:
        s = str(p.resolve())
        if s not in sys.path:
            sys.path.insert(0, s)


def _register_minimal_scene_props() -> None:
    import bpy
    from soulstruct.blender.flver.material.properties import (
        FLVERGXItemProps,
        FLVERMaterialProps,
        FLVERMaterialSettings,
    )
    from soulstruct.blender.flver.models.properties import (
        FLVERBoneProps,
        FLVERDummyProps,
        FLVERImportSettings,
        FLVERProps,
        FLVERSubmeshProps,
    )
    from soulstruct.blender.general.properties import SoulstructSettings
    from soulstruct.blender.types import SoulstructType

    for cls in (
        FLVERGXItemProps,
        FLVERSubmeshProps,
        FLVERBoneProps,
        FLVERProps,
        FLVERDummyProps,
        FLVERImportSettings,
        FLVERMaterialProps,
        FLVERMaterialSettings,
        SoulstructSettings,
    ):
        try:
            bpy.utils.register_class(cls)
        except ValueError:
            pass  # already registered (re-run in same session)

    if not hasattr(bpy.types.Scene, "flver_import_settings"):
        bpy.types.Scene.flver_import_settings = bpy.props.PointerProperty(type=FLVERImportSettings)
    if not hasattr(bpy.types.Scene, "flver_material_settings"):
        bpy.types.Scene.flver_material_settings = bpy.props.PointerProperty(type=FLVERMaterialSettings)
    if not hasattr(bpy.types.Scene, "soulstruct_settings"):
        bpy.types.Scene.soulstruct_settings = bpy.props.PointerProperty(type=SoulstructSettings)

    if not hasattr(bpy.types.Bone, "FLVER_BONE"):
        bpy.types.Bone.FLVER_BONE = bpy.props.PointerProperty(type=FLVERBoneProps)

    if not hasattr(bpy.types.Material, "FLVER_MATERIAL"):
        bpy.types.Material.FLVER_MATERIAL = bpy.props.PointerProperty(type=FLVERMaterialProps)

    if not hasattr(bpy.types.Object, "FLVER"):
        bpy.types.Object.FLVER = bpy.props.PointerProperty(type=FLVERProps)
    if not hasattr(bpy.types.Object, "FLVER_DUMMY"):
        bpy.types.Object.FLVER_DUMMY = bpy.props.PointerProperty(type=FLVERDummyProps)

    if not hasattr(bpy.types.Object, "soulstruct_type"):
        bpy.types.Object.soulstruct_type = bpy.props.EnumProperty(
            name="Soulstruct Object Type",
            items=[
                (SoulstructType.NONE, "None", ""),
                (SoulstructType.FLVER, "FLVER", "FLVER mesh model"),
                (SoulstructType.FLVER_DUMMY, "FLVER Dummy", "FLVER dummy object"),
            ],
            default=SoulstructType.NONE,
        )


def _make_log_op():
    from soulstruct.blender.utilities.operators import LoggingOperator

    class _LogOp:
        settings = staticmethod(LoggingOperator.settings)
        to_object_mode = staticmethod(LoggingOperator.to_object_mode)
        to_edit_mode = staticmethod(LoggingOperator.to_edit_mode)
        deselect_all = staticmethod(LoggingOperator.deselect_all)

        def debug(self, msg: str) -> None:
            print(f"DEBUG: {msg}")

        def warning(self, msg: str) -> None:
            print(f"WARNING: {msg}")

        def info(self, msg: str) -> None:
            print(f"INFO: {msg}")

        def error(self, msg: str) -> None:
            raise RuntimeError(msg)

    return _LogOp()


def main() -> int:
    repo = _repo_root()
    _setup_python_path(repo)

    import bpy
    from soulstruct.containers import Binder
    from soulstruct.flver import FLVER
    from soulstruct.blender.flver.utilities import get_flvers_from_binder
    from soulstruct.blender.flver.models.types.bl_flver.core import BlenderFLVER

    game_root = Path(
        os.environ.get(
            "NR_GAME_ROOT",
            r"s:\SteamLibrary\steamapps\common\ELDEN RING NIGHTREIGN\Game",
        )
    )
    chrbnd = Path(
        os.environ.get(
            "NR_CHRBND",
            game_root / "chr" / "c7720.chrbnd.dcx",
        )
    )
    if not chrbnd.is_file():
        print(f"FAIL: CHRBND not found: {chrbnd}")
        return 1

    _register_minimal_scene_props()

    settings = bpy.context.scene.soulstruct_settings
    settings.game_enum = "ELDEN_RING"
    settings.eldenring_game_root_str = str(game_root)

    imp = bpy.context.scene.flver_import_settings
    imp.import_textures = False
    imp.merge_mesh_vertices = True
    imp.omit_default_bone = False
    imp.add_name_suffix = False

    print(f"Loading binder: {chrbnd}")
    binder = Binder.from_path(chrbnd)
    flvers = get_flvers_from_binder(binder, chrbnd, allow_multiple=True)
    if not flvers:
        print("FAIL: no FLVER entries in binder")
        return 1

    flver = flvers[0]
    print(
        f"FLVER: version={flver.version.name} bones={len(flver.bones)} meshes={len(flver.meshes)} "
        f"any_dynamic={flver.any_dynamic()} all_dynamic={flver.all_dynamic()}"
    )

    op = _make_log_op()
    try:
        bl_flver = BlenderFLVER.new_from_soulstruct_obj(
            op,
            bpy.context,
            flver,
            name="c7720",
            image_import_manager=None,
        )
    except Exception:
        traceback.print_exc()
        print("FAIL: BlenderFLVER.new_from_soulstruct_obj raised")
        return 1

    mesh = bl_flver.mesh
    arm = bl_flver.armature
    print(
        f"OK: mesh={mesh.name} verts={len(mesh.data.vertices)} "
        f"armature={arm.name if arm else None} bones={len(arm.data.bones) if arm else 0}"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)
