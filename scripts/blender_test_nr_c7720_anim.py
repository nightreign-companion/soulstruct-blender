r"""Headless Blender smoke test: Nightreign c7720 HKX animation import via Soulstruct (no UI).

Run from repo root (PowerShell):

    & 'C:\Program Files\Blender Foundation\Blender 5.1\blender.exe' `
        --background --factory-startup `
        --python 'S:\_modding\tools\soulstruct-blender\scripts\blender_test_nr_c7720_anim.py'

Use --factory-startup so Blender does not auto-enable the installed io_soulstruct add-on
(which hits GPU draw code and fails in --background).

Set env vars to override paths:

    SOULSTRUCT_BLENDER_REPO  — path to soulstruct-blender clone
    NR_GAME_ROOT              — folder containing chr\\ (e.g. ...\\NIGHTREIGN\\Game)
    NR_CHRBND                 — optional full path to c7720.chrbnd.dcx
    NR_ANIM_STEM              — animation entry stem without extension (default a000_000020)

Exits 0 on success, 1 on failure. Does not enable the full io_soulstruct add-on (avoids MSB GPU
draw handlers that break in --background).
"""

from __future__ import annotations

import enum
import importlib.util
import os
import re
import sys
import traceback
import types as pytypes
from pathlib import Path

SKELETON_ENTRY_RE = re.compile(r"skeleton\.hkx(\.dcx)?", flags=re.IGNORECASE)


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
    from soulstruct.blender.animation.properties import AnimationExportSettings
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
        AnimationExportSettings,
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
    if not hasattr(bpy.types.Scene, "animation_export_settings"):
        bpy.types.Scene.animation_export_settings = bpy.props.PointerProperty(type=AnimationExportSettings)
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


def _stub_msb_for_headless() -> None:
    """Avoid importing msb/__init__.py (GPU draw handlers) when loading animation code."""

    class BlenderMSBPartSubtype(enum.Enum):
        Character = "CHARACTER"
        Object = "OBJECT"

    class BaseBlenderMSBPart:
        @staticmethod
        def parse_msb_part_obj(_obj):
            from soulstruct.blender.exceptions import SoulstructTypeError

            raise SoulstructTypeError()

    parts_mod = pytypes.ModuleType("soulstruct.blender.msb.properties.parts")
    parts_mod.BlenderMSBPartSubtype = BlenderMSBPartSubtype

    props_mod = pytypes.ModuleType("soulstruct.blender.msb.properties")
    props_mod.parts = parts_mod

    base_parts_mod = pytypes.ModuleType("soulstruct.blender.msb.types.base.parts")
    base_parts_mod.BaseBlenderMSBPart = BaseBlenderMSBPart

    types_base_mod = pytypes.ModuleType("soulstruct.blender.msb.types.base")
    types_base_mod.parts = base_parts_mod

    types_mod = pytypes.ModuleType("soulstruct.blender.msb.types")
    types_mod.base = types_base_mod

    msb_mod = pytypes.ModuleType("soulstruct.blender.msb")
    msb_mod.properties = props_mod
    msb_mod.types = types_mod

    for name, mod in (
        ("soulstruct.blender.msb", msb_mod),
        ("soulstruct.blender.msb.properties", props_mod),
        ("soulstruct.blender.msb.properties.parts", parts_mod),
        ("soulstruct.blender.msb.types", types_mod),
        ("soulstruct.blender.msb.types.base", types_base_mod),
        ("soulstruct.blender.msb.types.base.parts", base_parts_mod),
    ):
        sys.modules[name] = mod


def _load_animation_types_module(repo: Path):
    """Load animation utilities + types without animation/__init__.py (pulls MSB GPU)."""
    anim_dir = repo / "io_soulstruct" / "soulstruct" / "blender" / "animation"
    anim_pkg = pytypes.ModuleType("soulstruct.blender.animation")
    anim_pkg.__path__ = [str(anim_dir)]
    anim_pkg.__package__ = "soulstruct.blender.animation"
    sys.modules["soulstruct.blender.animation"] = anim_pkg

    for submodule in ("utilities", "types"):
        full_name = f"soulstruct.blender.animation.{submodule}"
        spec = importlib.util.spec_from_file_location(
            full_name,
            anim_dir / f"{submodule}.py",
            submodule_search_locations=[str(anim_dir)],
        )
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot load {full_name}")
        mod = importlib.util.module_from_spec(spec)
        sys.modules[full_name] = mod
        spec.loader.exec_module(mod)

    return sys.modules["soulstruct.blender.animation.types"].SoulstructAnimation


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


def _load_binder_compendium(op, binder):
    from soulstruct.containers import EntryNotFoundError
    from soulstruct.havok.core import HKX

    try:
        compendium_entry = binder.find_entry_matching_name(r".*\.compendium")
    except EntryNotFoundError:
        op.info("Did not find any compendium HKX in Binder.")
        return None
    op.info(f"Loading compendium HKX from entry: {compendium_entry.name}")
    return HKX.from_binder_entry(compendium_entry)


def _read_skeleton(op, skeleton_anibnd, compendium):
    from soulstruct.containers import EntryNotFoundError
    from soulstruct.blender.animation.utilities import read_skeleton_hkx_entry

    try:
        skeleton_entry = skeleton_anibnd[SKELETON_ENTRY_RE]
    except EntryNotFoundError:
        raise RuntimeError(
            f"ANIBND with path '{skeleton_anibnd.path}' has no skeleton HKX file."
        ) from None
    op.info(f"Loading skeleton HKX from entry: {skeleton_entry.name}")
    return read_skeleton_hkx_entry(skeleton_entry, compendium)


def _action_fcurve_stats(action) -> tuple[int, int]:
    """Return (fcurve_count, keyframe_count) for legacy or Blender 5 layered actions."""
    fcurves = getattr(action, "fcurves", None)
    if fcurves is not None:
        return len(fcurves), sum(len(fc.keyframe_points) for fc in fcurves)

    fcurve_count = 0
    keyframe_count = 0
    for layer in getattr(action, "layers", []):
        for strip in getattr(layer, "strips", []):
            channelbag = getattr(strip, "channelbag", None)
            if channelbag is None:
                continue
            for fc in getattr(channelbag, "fcurves", []):
                fcurve_count += 1
                keyframe_count += len(fc.keyframe_points)
    return fcurve_count, keyframe_count


def main() -> int:
    repo = _repo_root()
    _setup_python_path(repo)

    import bpy

    _stub_msb_for_headless()
    SoulstructAnimation = _load_animation_types_module(repo)

    from soulstruct.containers import Binder, EntryNotFoundError
    from soulstruct.eldenring.containers import DivBinder
    from soulstruct.blender.animation.utilities import read_animation_hkx_entry
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
    anim_stem = os.environ.get("NR_ANIM_STEM", "a000_000020")
    anibnd_path = game_root / "chr" / "c7720.anibnd.dcx"
    model_name = "c7720"

    if not chrbnd.is_file():
        print(f"FAIL: CHRBND not found: {chrbnd}")
        return 1
    if not anibnd_path.is_file():
        print(f"FAIL: ANIBND not found: {anibnd_path}")
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

    op = _make_log_op()

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

    try:
        bl_flver = BlenderFLVER.new_from_soulstruct_obj(
            op,
            bpy.context,
            flver,
            name=model_name,
            image_import_manager=None,
        )
    except Exception:
        traceback.print_exc()
        print("FAIL: BlenderFLVER.new_from_soulstruct_obj raised")
        return 1

    armature = bl_flver.armature
    if armature is None:
        print("FAIL: imported FLVER has no armature")
        return 1

    for obj in bpy.context.view_layer.objects:
        obj.select_set(False)
    armature.select_set(True)
    bpy.context.view_layer.objects.active = armature

    print(f"Loading ANIBND: {anibnd_path}")
    anibnd = DivBinder.from_path(anibnd_path)
    skeleton_anibnd = anibnd

    compendium = _load_binder_compendium(op, anibnd)
    try:
        skeleton_hkx = _read_skeleton(op, skeleton_anibnd, compendium)
    except Exception:
        traceback.print_exc()
        print("FAIL: could not read skeleton HKX from ANIBND")
        return 1

    anim_pattern = rf"{re.escape(anim_stem)}\.hkx(\.dcx)?"
    try:
        anim_entry = anibnd.find_entry_matching_name(anim_pattern)
    except EntryNotFoundError:
        print(f"FAIL: animation entry not found in ANIBND: {anim_stem}.hkx")
        return 1

    print(f"Loading animation HKX entry: {anim_entry.name}")
    try:
        animation_hkx = read_animation_hkx_entry(anim_entry, compendium)
        ss_animation = SoulstructAnimation.new_from_hkx_animation(
            op,
            bpy.context,
            animation_hkx,
            skeleton_hkx=skeleton_hkx,
            name=anim_stem,
            armature_obj=armature,
            model_name=model_name,
        )
    except Exception:
        traceback.print_exc()
        print(f"FAIL: could not import HKX animation '{anim_stem}'")
        return 1

    action = ss_animation.action
    frame_count = bpy.context.scene.frame_end
    fcurve_count, keyframe_count = _action_fcurve_stats(action)

    print(
        f"OK: action={action.name} frames={frame_count} fcurves={fcurve_count} "
        f"keyframes={keyframe_count}"
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
