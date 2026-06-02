# Soulstruct for Blender — Elden Ring / Nightreign Animation Dev Notes

Working notes for the `dosier` fork setup. Covers (1) what actually works today, (2) the
single-PyCharm-project layout with submodules, (3) hot-reload workflow, and (4) the
quickest path to "full mesh + anim + skeleton" plus the export roadmap.

> **TL;DR — the big correction.** The premise "soulstruct doesn't support Elden Ring
> animations" is only true for **export**. ER **mesh + skeleton (FLVER)** and ER
> **animation _import_** already work. Proven on real Nightreign data
> (`chr/c7720.anibnd.dcx`): the stock library path loads a **137-bone skeleton** and
> decodes a spline animation to **71 interleaved frames** using the Elden Ring `hk2018`
> classes. No Havok re-implementation from HavokMax is needed to *load* animations.

---

## 1. What works today (verified)

| Capability (Elden Ring / Nightreign) | Status | Where |
|---|---|---|
| FLVER mesh import | ✅ Works | `flver/models/...` (`Sekiro_EldenRing` FLVER version) |
| Skeleton / armature import (from FLVER) | ✅ Works | same as above |
| Animation **import** (ANIBND → Blender action) | ✅ Works | `animation/import_operators.py` → `eldenring.AnimationHKX`/`SkeletonHKX` |
| HK2018 tagfile (`20180100`) + `.compendium` read | ✅ Works | `soulstruct.havok` tagfile unpacker + `DivBinder` |
| Spline-compressed → interleaved decode | ✅ Works | `soulstruct.havok` `spline_compression.py` |
| Animation **export** (Blender → game ANIBND) | ⚠️ Incomplete | `animation/export_operators.py` (see §4) |
| Asset (`aeg`) animation export | ❌ Missing | TODO in `export_operators.py` |

Nightreign uses the **same HK2018 tagfile format** as Elden Ring, so the ER classes parse
NR `chr` data directly. The only thing that was broken on the stock path was a binder API
name skew between the two libraries (now fixed — see §3).

---

## 2. Project layout (one PyCharm project, submodules)

The add-on repo is now the single project root. The two libraries are git **submodules**
under `io_soulstruct_lib/` (this matches the add-on author's stated intent):

```
S:\_modding\tools\soulstruct-blender\        ← open THIS in PyCharm
├── io_soulstruct\                            ← Blender add-on (UI/operators only)
│   └── soulstruct\blender\                   ← the `soulstruct.blender` package
├── io_soulstruct_lib\
│   ├── soulstruct\                           ← submodule: git@github.com:dosier/soulstruct.git (main, 2.4.0)
│   └── soulstruct-havok\                      ← submodule: Grimrukh/soulstruct-havok (1.3.0)
├── .gitmodules
└── DEV_ER_ANIMATION.md                       ← this file
```

`.gitmodules`:

```ini
[submodule "io_soulstruct_lib/soulstruct"]
	path = io_soulstruct_lib/soulstruct
	url = git@github.com:dosier/soulstruct.git
[submodule "io_soulstruct_lib/soulstruct-havok"]
	path = io_soulstruct_lib/soulstruct-havok
	url = https://github.com/Grimrukh/soulstruct-havok.git
```

Clone-from-scratch on another machine:

```bash
git clone --recurse-submodules <soulstruct-blender remote>
# or, after a plain clone:
git submodule update --init --recursive
```

### Blender wiring (junctions, already created on this machine)

The add-on's `io_soulstruct/__init__.py` looks for `io_soulstruct_lib` **next to**
`io_soulstruct` in Blender's `scripts/addons`. We link both to the repo:

```
%APPDATA%\Blender Foundation\Blender\5.1\scripts\addons\
├── io_soulstruct       --> S:\_modding\tools\soulstruct-blender\io_soulstruct        (junction)
├── io_soulstruct_lib   --> S:\_modding\tools\soulstruct-blender\io_soulstruct_lib    (junction)
└── modules\            ← editable installs of soulstruct + soulstruct-havok land here
```

Recreate if needed (no admin required):

```powershell
$addons = "$env:APPDATA\Blender Foundation\Blender\5.1\scripts\addons"
cmd /c mklink /J "$addons\io_soulstruct"     "S:\_modding\tools\soulstruct-blender\io_soulstruct"
cmd /c mklink /J "$addons\io_soulstruct_lib" "S:\_modding\tools\soulstruct-blender\io_soulstruct_lib"
```

On first **interactive** enable (`Edit > Preferences > Add-ons > Soulstruct`), the add-on
pip-installs the two libs editable into `addons\modules`. Open **Window > Toggle System
Console** first to watch for errors.

> Headless enable (`blender --background`) fails with a GPU-draw error from the MSB module
> — that's expected; it is **not** an import/registration failure. Validate in the GUI.

---

## 3. The compat fix (lives in the `dosier/soulstruct` fork)

`soulstruct-havok` 1.3.0 calls `binder.find_entries_matching_name(...)`
(`soulstruct-havok/src/soulstruct/havok/core.py:189`, on the ER ANIBND `load_from_entries`
path), but `soulstruct` 2.4.0 only implements `find_entries_by_name_regex(...)`. Fix =
two alias methods in the fork:

`io_soulstruct_lib/soulstruct/src/soulstruct/containers/core.py` (class `Binder`, after
`find_entries_by_name_regex`):

```python
# Compatibility alias for soulstruct-havok (expects *_matching_name).
def find_entry_matching_name(
    self, pattern: str | re.Pattern, flags=0, escape=False,
) -> BinderEntry:
    return self.find_entry_by_name_regex(pattern, flags=flags, escape=escape)

# Compatibility alias for soulstruct-havok (expects *_matching_name).
def find_entries_matching_name(
    self, pattern: str | re.Pattern, flags=0, escape=False,
) -> list[BinderEntry]:
    return self.find_entries_by_name_regex(pattern, flags=flags, escape=escape)
```

Currently an **uncommitted working-tree change** in the submodule. Commit & push to your
fork when ready:

```bash
cd io_soulstruct_lib/soulstruct
git checkout -b fix/binder-matching-name-alias
git commit -am "Add find_(entry|entries)_matching_name aliases for soulstruct-havok compat"
git push -u origin fix/binder-matching-name-alias
```

Verification (passes from the fork via the test venv):

```
soulstruct.__path__ -> ...\io_soulstruct_lib\soulstruct\src\soulstruct
bones: 137
animation count: 80
sample animation id: 20  (spline -> 71 interleaved frames)  OK
```

---

## 4. PyCharm setup

- **Interpreter:** use Blender's embedded Python for runtime parity:
  `C:\Program Files\Blender Foundation\Blender 5.1\5.1\python\bin\python.exe`
  (Python 3.13). Or a venv on the same Python; the test venv at
  `S:\_modding\tools\_research\.venv` already has both libs editable-installed.
- **Sources roots** (Settings > Project Structure):
  - `io_soulstruct` (the add-on)
  - `io_soulstruct_lib/soulstruct/src`
  - `io_soulstruct_lib/soulstruct-havok/src`
- **`bpy` autocomplete:** `pip install fake-bpy-module` into the interpreter, then run
  `blender-stubs/split_bpy_types.py` (chunks the huge stub so PyCharm can index it; it
  also injects Soulstruct property types via `blender-stubs/soulstruct_extra_stubs.py`).
  `File > Invalidate Caches` afterward.
- Submodules appear as normal subfolders; edits to `soulstruct` go to your `dosier` fork,
  edits to `soulstruct-havok` track upstream (fork it too if you need to push Havok fixes).

---

## 5. Hot reload

This add-on is built for Blender's built-in reload and pre-reloads its own
`soulstruct.blender.*` modules in `io_soulstruct/__init__.py` to avoid partial-import
`isinstance` bugs.

| You changed… | Reload method |
|---|---|
| `soulstruct.blender.*` (the add-on UI/operators) | **F3 → `Reload Scripts`** (fast loop) |
| `io_soulstruct/__init__.py` (class/menu registration) | Reload Scripts; restart if it errors |
| `soulstruct` / `soulstruct-havok` core libs (the submodules) | **Restart Blender** — the auto-reloader only re-imports `soulstruct.blender` |
| First-time pip bootstrap / new dependency | **Restart Blender** |

So for day-to-day work in `soulstruct.blender` operators you stay in Blender and hit
Reload Scripts. When you change the Havok/core libs (which is where ER **export** work
happens), restart Blender (or reload those modules manually).

---

## 6. Quickest path to "full mesh + anim + skeleton" in Blender

**Loading (import): essentially done.** Order of operations in Blender:

1. General Settings → set Game = **Elden Ring**, set Game/Project directories.
2. Import the character FLVER (`chr/c7720.chrbnd` → mesh + armature/skeleton).
3. With the FLVER/armature selected, **Animation tab → Import Character Anim** → pick from
   the ANIBND. Set Scene FPS to 60 (the add-on interpolates 30→60 by default).

The remaining "make import bulletproof" items are small and live in this fork:

- Confirm `ANIBND` is re-exported from `soulstruct.havok.fromsoft.eldenring.__init__`
  (currently import via `...eldenring.anibnd import ANIBND`).
- Exercise `tests/animations` `test_er()` against a real ER (not just NR) ANIBND.
- Validate end-to-end in the GUI (headless can't, due to the MSB GPU draw call).

## 7. Export roadmap (the real "⚠️ partial" work)

This is the only part that needs new code. In priority order:

1. **`div_id` plumbing (blocking, tiny).** The ER entry-path template needs `{div_id}`:
   `io_soulstruct/soulstruct/blender/animation/types.py:64-65`
   ```
   "N:\\GR\\data\\INTERROOT_win64\\chr\\{model_name}\\hkx_{div_id}compendium\\{animation_stem}.hkx"
   ```
   but the export call omits it (`animation/export_operators.py:403-405`), so ER character
   export raises `KeyError: 'div_id'`. Derive `div_id` from the binder/compendium stem
   (e.g. `c7720_div00.compendium` → `div00_`) and pass it into `.format(...)`.
2. **Use `DivBinder` on the export path** (import already does; export uses a plain
   `Binder`), plus load skeleton/animation **with the compendium** for round-trip.
3. **Spline re-compression.** `soulstruct-havok` already exports via an interleaved →
   hk2010 → `CompressAnim.exe` → hk2010-spline → hk2018 bridge
   (`fromsoft/eldenring/file_types.py`). Confirm the bundled `CompressAnim.exe` ships and
   runs. (Pure-Python spline *encode* is incomplete — ThreeComp40 quats only — so keep the
   exe bridge for now.)
4. **Tagfile write correctness.** Vanilla ER anim HKX use `TCRF` (type ref into the
   compendium); the tagfile packer currently writes a full inline `TYPE` section and has
   no `TCRF`/`TCM0` writer. Add an ER tagfile round-trip test
   (`soulstruct-havok/tests/test_tagfile.py` has a `# TODO: ER tagfile test.`) and decide
   whether the game accepts inline-`TYPE` anim files or requires `TCRF`.
5. **Asset (`aeg`) animation export.** Mirror `ImportAssetHKXAnimation` for GEOMBND →
   nested ANIBND writeback (`export_operators.py:524` TODO; add an `aeg` entry to the
   asset animation info table at `types.py:96`).

### Why HavokMax matters (and where it doesn't)

HavokMax/HavokLib confirm the format facts (HK2018 tagfile, `.compendium`, NURBS spline
decode, the FromSoft Y↔Z permutation) but HavokMax **only exports interleaved Havok XML**
— it does **not** write spline-compressed HKX or tagfiles either (it relies on Havok
Content Tools to recompress). So HavokMax is a **reference for reading**, which
`soulstruct-havok` already does. For game-ready **writeback**, `soulstruct-havok`'s
`CompressAnim.exe` bridge is actually further along than HavokMax. Conclusion: don't port
HavokMax — finish the export plumbing above.
