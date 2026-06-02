"""Bundled character model id -> display name maps for search UI."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from soulstruct.blender.general.properties import SoulstructSettings

_DIR = Path(__file__).parent


@lru_cache(maxsize=None)
def _load_json(path: Path) -> dict[int, str]:
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {int(k): v for k, v in data.items()}


def reload_character_names() -> None:
    """Clear cached name maps (call after editing overrides)."""
    _load_json.cache_clear()


def _load_character_models_fallback(submodule_name: str) -> dict[int, str]:
    try:
        if submodule_name == "eldenring":
            from soulstruct.eldenring.constants import CHARACTER_MODELS

            return dict(CHARACTER_MODELS)
        if submodule_name == "darksouls1ptde":
            from soulstruct.darksouls1ptde.constants import CHARACTER_MODELS

            return dict(CHARACTER_MODELS)
        if submodule_name == "darksouls1r":
            from soulstruct.darksouls1r.constants import CHARACTER_MODELS

            return dict(CHARACTER_MODELS)
        if submodule_name == "demonssouls":
            from soulstruct.demonssouls.constants import CHARACTER_MODELS

            return dict(CHARACTER_MODELS)
    except ImportError:
        pass
    return {}


def get_character_name_map(settings: SoulstructSettings) -> dict[int, str]:
    """Return model number -> display name for the active game."""
    game = settings.game
    if not game:
        return {}

    names: dict[int, str] = {}
    submodule = game.submodule_name
    names.update(_load_json(_DIR / f"{submodule}.json"))
    # Nightreign modders often keep game_enum on Elden Ring; merge NR param names too.
    if submodule == "eldenring":
        names.update(_load_json(_DIR / "nightreign.json"))
    names.update(_load_json(_DIR / "overrides.json"))

    if not names:
        names.update(_load_character_models_fallback(submodule))

    return names
