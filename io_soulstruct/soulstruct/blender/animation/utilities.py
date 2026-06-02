from __future__ import annotations

__all__ = [
    "SKELETON_TYPING",
    "ANIMATION_TYPING",
    "read_animation_hkx_entry",
    "read_skeleton_hkx_entry",
    "load_anibnd_compendium",
    "load_skeleton_hkx_from_path",
    "derive_er_hkx_div_id",
    "get_chr_animation_hkx_entry_path",
    "resolve_character_anibnd_path",
    "get_armature_frames",
    "get_root_motion",
    "get_animation_name",
    "get_active_flver_or_part_armature",
]

import re
import typing as tp
from pathlib import Path

import bpy

import numpy as np

from soulstruct.havok.core import HKX
from soulstruct.havok.utilities.maths import TRSTransform
from soulstruct.havok.fromsoft.base import BaseAnimationHKX, BaseSkeletonHKX
from soulstruct.havok.fromsoft import demonssouls, darksouls1ptde, darksouls1r, bloodborne, eldenring
from soulstruct.containers import Binder, BinderEntry, EntryNotFoundError
from soulstruct.games import Game, ELDEN_RING, NIGHTREIGN


def is_er_family_game(game: Game) -> bool:
    return game in (ELDEN_RING, NIGHTREIGN)

from soulstruct.blender.exceptions import UnsupportedGameError, SoulstructTypeError
from soulstruct.blender.flver.models.types import BlenderFLVER
from soulstruct.blender.msb.properties.parts import BlenderMSBPartSubtype
from soulstruct.blender.msb.types.base.parts import BaseBlenderMSBPart
from soulstruct.blender.types import ArmatureObject, MeshObject
from soulstruct.blender.utilities import get_model_name

ANIMATION_TYPING = tp.Union[
    demonssouls.AnimationHKX,
    darksouls1ptde.AnimationHKX,
    darksouls1r.AnimationHKX,
    bloodborne.AnimationHKX,
    eldenring.AnimationHKX,
]
SKELETON_TYPING = tp.Union[
    demonssouls.SkeletonHKX,
    darksouls1ptde.SkeletonHKX,
    darksouls1r.SkeletonHKX,
    bloodborne.SkeletonHKX,
    eldenring.SkeletonHKX,
]


def read_animation_hkx_entry(hkx_entry: BinderEntry, compendium: HKX = None) -> ANIMATION_TYPING:
    """Read animation HKX file from a Binder entry and return the appropriate `AnimationHKX` subclass instance."""
    data = hkx_entry.get_uncompressed_data()
    packfile_version = data[0x28:0x38]
    tagfile_version = data[0x10:0x18]
    if packfile_version.startswith(b"Havok-4.5.0-r1"):  # DeS (c9900)
        hkx = demonssouls.AnimationHKX.from_bytes(data, compendium=compendium)
    elif packfile_version.startswith(b"Havok-5.5.0-r1"):  # DeS
        hkx = demonssouls.AnimationHKX.from_bytes(data, compendium=compendium)
    elif packfile_version.startswith(b"hk_2010.2.0-r1"):  # PTDE
        hkx = darksouls1ptde.AnimationHKX.from_bytes(data, compendium=compendium)
    elif tagfile_version == b"20150100":  # DSR
        hkx = darksouls1r.AnimationHKX.from_bytes(data, compendium=compendium)
    elif packfile_version.startswith(b"hk_2014.1.0-r1"):  # BB
        hkx = bloodborne.AnimationHKX.from_bytes(data, compendium=compendium)
    elif tagfile_version == b"20180100":  # ER
        hkx = eldenring.AnimationHKX.from_bytes(data, compendium=compendium)
    else:
        raise UnsupportedGameError(
            f"Cannot support this HKX skeleton file version in Soulstruct and/or Blender.\n"
            f"   Possible packfile version: {packfile_version}\n"
            f"   Possible tagfile version: {tagfile_version}"
        )
    hkx.path = Path(hkx_entry.name)
    return hkx


def read_skeleton_hkx_entry(hkx_entry: BinderEntry, compendium: HKX = None) -> SKELETON_TYPING:
    """Read skeleton HKX file from a Binder entry and return the appropriate `SkeletonHKX` subclass instance."""
    hkx = read_skeleton_hkx_entry_from_bytes(hkx_entry.get_uncompressed_data(), compendium=compendium)
    hkx.path = Path(hkx_entry.name)
    return hkx


def load_skeleton_hkx_from_path(
    skeleton_path: Path,
    game: Game,
) -> SKELETON_TYPING:
    """Load a skeleton HKX from a loose file or a Binder (ANIBND) path."""
    if skeleton_path.name.endswith((".hkx", ".hkx.dcx")):
        return read_skeleton_hkx_entry_from_bytes(skeleton_path.read_bytes(), compendium=None)

    if is_er_family_game(game):
        from soulstruct.eldenring.containers import DivBinder

        binder = DivBinder.from_path(skeleton_path)
    else:
        binder = Binder.from_path(skeleton_path)

    try:
        skeleton_entry = binder[SKELETON_ENTRY_RE]
    except EntryNotFoundError as ex:
        raise EntryNotFoundError(
            f"Could not find 'skeleton.hkx' in binder: '{skeleton_path}'"
        ) from ex

    compendium = load_anibnd_compendium(binder) if is_er_family_game(game) else None
    return read_skeleton_hkx_entry(skeleton_entry, compendium)


def read_skeleton_hkx_entry_from_bytes(
    data: bytes,
    compendium: HKX = None,
) -> SKELETON_TYPING:
    """Like `read_skeleton_hkx_entry` but from raw bytes (loose skeleton file)."""
    packfile_version = data[0x28:0x38]
    tagfile_version = data[0x10:0x18]
    if packfile_version.startswith(b"Havok-4.5.0-r1"):
        hkx = demonssouls.SkeletonHKX.from_bytes(data, compendium=compendium)
    elif packfile_version.startswith(b"Havok-5.5.0-r1"):
        hkx = demonssouls.SkeletonHKX.from_bytes(data, compendium=compendium)
    elif packfile_version.startswith(b"hk_2010.2.0-r1"):
        hkx = darksouls1ptde.SkeletonHKX.from_bytes(data, compendium=compendium)
    elif tagfile_version == b"20150100":
        hkx = darksouls1r.SkeletonHKX.from_bytes(data, compendium=compendium)
    elif packfile_version.startswith(b"hk_2014.1.0-r1"):
        hkx = bloodborne.SkeletonHKX.from_bytes(data, compendium=compendium)
    elif tagfile_version == b"20180100":
        hkx = eldenring.SkeletonHKX.from_bytes(data, compendium=compendium)
    else:
        raise UnsupportedGameError(
            f"Cannot support this HKX skeleton file version.\n"
            f"   Possible packfile version: {packfile_version}\n"
            f"   Possible tagfile version: {tagfile_version}"
        )
    return hkx


SKELETON_ENTRY_RE = re.compile(r"skeleton\.hkx(\.dcx)?", flags=re.IGNORECASE)


def load_anibnd_compendium(anibnd: Binder) -> HKX | None:
    """Load compendium HKX from an ANIBND, if present."""
    try:
        compendium_entry = anibnd.find_entry_matching_name(r".*\.compendium")
    except EntryNotFoundError:
        return None
    return HKX.from_binder_entry(compendium_entry)


def derive_er_hkx_div_id(anibnd: Binder, model_name: str) -> str:
    """Elden Ring HKX path div prefix from compendium entry stem, e.g. ``''`` or ``'div00_'``.

    Matches paths like ``hkx_compendium\\`` vs ``hkx_div00_compendium\\``.
    """
    try:
        compendium_entry = anibnd.find_entry_matching_name(r".*\.compendium")
    except EntryNotFoundError:
        return ""
    stem = compendium_entry.stem
    model_lower = model_name.lower()
    if stem.lower() == model_lower:
        return ""
    prefix = f"{model_name}_"
    if not stem.lower().startswith(prefix.lower()):
        return ""
    suffix = stem[len(model_name) + 1 :]
    if suffix.lower().startswith("div"):
        return suffix.lower() + "_"
    return ""


def load_character_anibnd_bundle(
    settings,
    model_name: str,
    sub_c0000_binder: str = "None",
) -> tuple[Binder, SKELETON_TYPING, HKX | None]:
    """Load character ANIBND, skeleton HKX, and compendium without instantiating a Blender operator."""
    from soulstruct.blender.animation.types import SoulstructAnimation
    from soulstruct.blender.exceptions import AnimationImportError
    from soulstruct.eldenring.containers import DivBinder

    try:
        game_anim_info = SoulstructAnimation.GAME_ANIMATION_INFO_CHR[settings.game]
    except KeyError as ex:
        raise AnimationImportError(f"Game '{settings.game}' is not supported for character animation import.") from ex

    relative_anibnd_path = Path(game_anim_info.relative_binder_path.format(model_name=model_name))
    anibnd_path = settings.get_import_file_path(relative_anibnd_path)
    if not anibnd_path or not anibnd_path.is_file():
        raise FileNotFoundError(f"Cannot find ANIBND for character '{model_name}' in game directory.")
    skeleton_anibnd = anibnd = DivBinder.from_path(anibnd_path)

    if sub_c0000_binder != "None":
        sub_path = settings.get_import_file_path(
            game_anim_info.relative_binder_path.format(model_name=sub_c0000_binder)
        )
        if not sub_path or not sub_path.is_file():
            raise FileNotFoundError(f"Cannot find ANIBND for c0000 sub-ANIBND '{sub_c0000_binder}'.")
        anibnd = DivBinder.from_path(sub_path)

    compendium = load_anibnd_compendium(anibnd)
    try:
        skeleton_entry = skeleton_anibnd[SKELETON_ENTRY_RE]
    except EntryNotFoundError as ex:
        raise AnimationImportError(f"ANIBND '{skeleton_anibnd.path_name}' has no skeleton HKX.") from ex
    skeleton_hkx = read_skeleton_hkx_entry(skeleton_entry, compendium)
    return anibnd, skeleton_hkx, compendium


def import_character_hkx_animation_entry(
    operator,
    context: bpy.types.Context,
    *,
    entry: BinderEntry,
    binder: Binder,
    armature_obj: ArmatureObject,
    part_mesh_obj: MeshObject | None,
    model_name: str,
    skeleton_hkx: SKELETON_TYPING,
    compendium: HKX | None,
) -> set[str]:
    """Import one HKX animation entry onto `armature_obj` (shared by binder-choice and Stan's Tools)."""
    import time
    import traceback

    from soulstruct.blender.animation.types import SoulstructAnimation

    p = time.perf_counter()
    animation_hkx = read_animation_hkx_entry(entry, compendium)
    operator.info(f"Read `AnimationHKX` Binder entry '{entry.name}' in {time.perf_counter() - p:.3f} s.")

    if part_mesh_obj and not armature_obj.animation_data:
        part_mesh_obj["MSB Translate"] = armature_obj.location
        part_mesh_obj["MSB Rotate"] = armature_obj.rotation_euler
        part_mesh_obj["MSB Scale"] = armature_obj.scale

    anim_name = entry.name.split(".")[0]
    try:
        operator.info(f"Creating animation '{anim_name}' in Blender.")
        SoulstructAnimation.new_from_hkx_animation(
            operator,
            context,
            animation_hkx,
            skeleton_hkx=skeleton_hkx,
            name=anim_name,
            armature_obj=armature_obj,
            model_name=model_name,
        )
    except Exception as ex:
        traceback.print_exc()
        return operator.error(
            f"Cannot import HKX animation {anim_name} from '{binder.path_name}'. Error: {ex}"
        )
    operator.debug(f"Created animation action in {time.perf_counter() - p:.3f} s.")
    return {"FINISHED"}


def resolve_character_anibnd_path(settings, model_name: str) -> Path | None:
    """Return absolute path to a character's ANIBND from game/project roots, if it exists."""
    from soulstruct.blender.animation.types import SoulstructAnimation

    try:
        game_anim_info = SoulstructAnimation.GAME_ANIMATION_INFO_CHR[settings.game]
    except KeyError:
        return None

    relative_anibnd_path = Path(game_anim_info.relative_binder_path.format(model_name=model_name))
    try:
        return settings.get_import_file_path(relative_anibnd_path)
    except FileNotFoundError:
        return None


def get_chr_animation_hkx_entry_path(
    game: Game,
    game_anim_info,
    anibnd: Binder,
    model_name: str,
    animation_stem: str,
    animation_id: int,
) -> str:
    """Resolve Binder entry path for a character animation HKX (reuse existing entry path when overwriting)."""
    if animation_id in anibnd.get_entry_ids():
        return anibnd.find_entry_by_id(animation_id).path
    div_id = derive_er_hkx_div_id(anibnd, model_name) if is_er_family_game(game) else ""
    entry_path = game_anim_info.hkx_entry_path.format(
        model_name=model_name,
        animation_stem=animation_stem,
        div_id=div_id,
    )
    return game_anim_info.dcx_type.process_path(entry_path)


def get_root_motion(animation_hkx: BaseAnimationHKX, swap_yz=True) -> np.ndarray | None:
    try:
        root_motion = animation_hkx.animation_container.get_reference_frame_samples()
    except (ValueError, TypeError):
        return None

    if swap_yz:
        # Swap Y and Z axes and negate rotation (now around Z axis). Array is read-only, so we construct a new one.
        root_motion = np.c_[root_motion[:, 0], root_motion[:, 2], root_motion[:, 1], -root_motion[:, 3]]
    return root_motion


def get_armature_frames(
    animation_hkx: BaseAnimationHKX, skeleton_hkx: BaseSkeletonHKX
) -> list[dict[str, TRSTransform]]:
    """Get a list of animation frame dictionaries, which each map bone names to armature-space transforms that frame."""

    # Get track bone names.
    track_bone_indices = animation_hkx.animation_container.get_track_bone_indices()
    track_bone_names = [skeleton_hkx.skeleton.bones[i].name for i in track_bone_indices]

    # Get frames as standard nested lists of transforms.
    interleaved_frames = animation_hkx.animation_container.get_interleaved_data_in_armature_space(skeleton_hkx.skeleton)

    # Convert to dictionary using given `track_bone_names` list.
    arma_frame_dicts = [
        {bone_name: transform for bone_name, transform in zip(track_bone_names, frame)}
        for frame in interleaved_frames
    ]
    return arma_frame_dicts


def get_animation_name(animation_id: int, template: str, prefix="a"):
    """Takes a template like '##_####' and converts `animation_id` int (e.g. 13000) to a string (e.g. 'a01_3000')."""
    parts = template.split('_')
    string_parts = []
    animation_id = str(animation_id)

    if len(template.replace("_", "")) < len(animation_id):
        raise ValueError(
            f"Animation ID '{animation_id}' is too long for template '{template}'."
        )

    for part in reversed(parts):
        length = len(part)  # number of digits we want to take from the end of the animation ID
        string_parts.append(animation_id[-length:].zfill(length))
        animation_id = animation_id[:-length]

    return prefix + '_'.join(reversed(string_parts))


def get_active_flver_or_part_armature(
    context: bpy.types.Context
) -> tuple[ArmatureObject | None, MeshObject | None, str, bool]:
    """Get Armature, Mesh, model name, and `is_part` of active FLVER or MSB Part (Character or Object only)."""
    obj = context.active_object
    if not obj:
        return None, None, "", False

    try:
        armature, mesh = BlenderFLVER.parse_flver_obj(obj)
    except SoulstructTypeError:
        pass
    else:
        if armature:
            return armature, mesh, get_model_name(mesh.name), False

    try:
        armature, mesh = BaseBlenderMSBPart.parse_msb_part_obj(obj)
    except SoulstructTypeError:
        pass
    else:
        if armature and mesh.MSB_PART.model and mesh.MSB_PART.entry_subtype in {
            BlenderMSBPartSubtype.Character, BlenderMSBPartSubtype.Object
        }:
            return armature, mesh, get_model_name(mesh.MSB_PART.model.name), True

    return None, None, "", False
