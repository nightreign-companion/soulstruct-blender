"""Optional display labels for HKX animation stems (from character TAE when parseable)."""
from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from soulstruct.containers import Binder, BinderEntry

_HKX_STEM_RE = re.compile(r"^(a\d{3}_\d{6})\.hkx", re.IGNORECASE)


def animation_stem_from_entry_name(entry_name: str) -> str | None:
    match = _HKX_STEM_RE.match(entry_name)
    return match.group(1).lower() if match else None


def binder_entry_id_to_stem(entry_id: int) -> str:
    """Map ANIBND entry id (e.g. 1000003023) to HKX stem (a000_003023)."""
    suffix = entry_id % 1_000_000
    return f"a000_{suffix:06d}"


def load_tae_labels_for_binder(binder: Binder) -> dict[str, str]:
    """Return stem -> label from embedded TAE when Soulstruct's TAE reader works.

    ER/NR TAE often has no per-clip display names; this returns {} on failure.
    Keys are lowercase HKX stems like ``a000_003023``.
    """
    try:
        tae_entry = binder.find_entry_matching_name(r".*\.tae")
    except Exception:
        return {}

    try:
        tae_bytes = tae_entry.get_uncompressed_data()
    except Exception:
        return {}

    try:
        from soulstruct.base.animations.tae.core import TAE
    except Exception:
        return {}

    try:
        tae = TAE.from_bytes(tae_bytes)
    except Exception:
        return {}

    labels: dict[str, str] = {}
    for anim in tae.animations:
        if not anim.animation_file_name:
            stem = binder_entry_id_to_stem(anim.animation_id)
            continue
        name = anim.animation_file_name.replace("\\", "/").split("/")[-1]
        stem_match = _HKX_STEM_RE.match(name)
        if stem_match:
            stem = stem_match.group(1).lower()
        else:
            stem = binder_entry_id_to_stem(anim.animation_id)
        labels[stem] = name
    return labels


def label_for_animation_entry(entry: BinderEntry, tae_labels: dict[str, str]) -> str:
    stem = animation_stem_from_entry_name(entry.name)
    if stem is None:
        return entry.name
    extra = tae_labels.get(stem)
    if extra and extra.lower() != f"{stem}.hkx":
        return f"{stem} — {extra}"
    return stem
