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

# Compatibility alias for io_soulstruct Blender operators (expects find_entry_id).
def find_entry_id(self, entry_id: int) -> BinderEntry:
    return self.find_entry_by_id(entry_id)
```

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

**Loading (import): essentially done.** All Soulstruct operators live in the **3D Viewport
sidebar** (not the top menu bar). Prerequisite: add-on enabled under
`Edit > Preferences > Add-ons`, search **Soulstruct**.

### Where "General Settings" actually is

**General Settings** is a **collapsible panel inside the right-hand sidebar** of the 3D
View. The same controls are duplicated on several sidebar **tabs** (one copy per tab):

| How to open the sidebar | |
|---|---|
| Press **`N`** in the 3D View, **or** | |
| Click the **`<` / `>` arrow** on the right edge of the 3D Viewport | |

At the **top of that sidebar**, you will see Soulstruct tabs such as **`FLVER`**,
**`Animation`**, **`Collision`**, **`MSB`**, etc. (added by the add-on when it loads.)

On **any** of those tabs, scroll if needed and expand the panel named **`General Settings`**
(it is **collapsed by default** — click the panel header to open it). The **`Animation`**
tab is the most convenient when you are doing animation work; **`FLVER`** works too for
step 1.

**Alternative (same data, different place):** open the **Properties** editor (usually the
vertical panel on the right of the Blender window) → select the **Scene** context (tab
with the **render / scene** icon, not the camera/object icons) → expand **`Soulstruct
Settings`**. That panel is the Scene-properties copy of the same settings (`SCENE_PT_soulstruct_settings`).

There is **no** top-level `General Settings` menu under `Edit` or `Window`.

### Step-by-step (e.g. Artorias / `c7720`)

**0. Unpack game files first.** Soulstruct reads unpacked binders on disk (e.g. WitchyBND).
You need at least:

- `chr\c7720.chrbnd.dcx` (mesh)
- `chr\c7720.anibnd.dcx` (animations + skeleton HKX)

**1. General Settings — game + folders**

In the 3D View sidebar → **`FLVER`** or **`Animation`** tab → expand **`General Settings`**:

1. **`Game`** dropdown (top of panel) → choose **`Elden Ring`**.  
   (Nightreign uses the same Havok classes and a newer FLVER revision `0x20021`; keep
   **Elden Ring** selected in Soulstruct — the fork adds `FLVERVersion.Nightreign` for
   mesh import.)
2. **`Game Root:`** → folder picker → directory that **contains** a `chr\` folder with your
   binders. For Nightreign on this machine, for example:  
   `s:\SteamLibrary\steamapps\common\ELDEN RING NIGHTREIGN\Game`  
   For vanilla Elden Ring, the folder that contains `Game\chr\` (often the install root
   with the `.exe`, depending on how you unpacked).
3. **`Project Root:`** (optional) → mod output tree mirroring `Game\`; leave empty if you
   only import from the game install.
4. Confirm the **Animation** tab’s **Import** section does **not** show *"No game root
   path set."* — that message means `Game Root` is still empty or wrong.

Optional: expand **`Import/Export Settings`** inside the same panel (`Prefer Import from
Project`, etc.).

**2. Import mesh + armature (FLVER)**

Still in the 3D View sidebar → **`FLVER`** tab → expand **`FLVER Import`** → click
**`Import Character`**.

- File browser opens filtered to `*.chrbnd` / `*.chrbnd.dcx`.
- Navigate to `chr\` under your Game Root and pick **`c7720.chrbnd.dcx`** (or unpacked
  `.chrbnd`).
- Follow the operator’s file-browser options (textures, merge submeshes, etc.) and confirm.

Result: a mesh object parented to an **Armature** (skeleton). Select the armature or mesh
before the next step.

**3. Import animation (HKX from ANIBND)**

3D View sidebar → **`Animation`** tab:

1. Expand **`General Settings`** if you have not set Game Root on this tab yet (same as
   step 1).
2. Expand **`Animation Import/Export`** → sub-panel **`Import`**.
3. Click **`Import Character Anim`** (only enabled when a character FLVER/armature is
   selected; character model names usually start with **`c`**).
4. In the popup list, choose an animation entry (e.g. `a000_000020.hkx` inside
   `c7720.anibnd`).

**4. Timing (30 Hz, 1:1 frames)**

Game animations are **30 Hz** (same as **DSAS**). Import places one Blender keyframe per
game sample and sets the scene to **30 fps**. Blender frame **N** = game sample **N**.
Re-import clips if you imported before this behavior was enforced.

Press **Space** with the armature selected to preview.

### Headless smoke tests (no UI)

From the repo root, with Blender 5.1 and Nightreign `Game` on disk:

```powershell
# Mesh + armature only
& 'C:\Program Files\Blender Foundation\Blender 5.1\blender.exe' `
    --background --factory-startup `
    --python 'S:\_modding\tools\soulstruct-blender\scripts\blender_test_nr_c7720.py'

# Mesh + armature + HKX animation (default a000_000020.hkx)
& 'C:\Program Files\Blender Foundation\Blender 5.1\blender.exe' `
    --background --factory-startup `
    --python 'S:\_modding\tools\soulstruct-blender\scripts\blender_test_nr_c7720_anim.py'
```

Override paths with `NR_GAME_ROOT`, `NR_CHRBND`, `NR_ANIM_STEM`. The animation script
stubs MSB modules so it does not hit the MSB GPU draw import (full add-on enable still
requires the GUI).

Verified on `c7720`: spline `a000_000020.hkx` → Blender action `c7720|a000_000020`,
scene frame end **70** at 30 fps (71 game frames, 1:1).

### Remaining "make import bulletproof" items (code, not UI)

The remaining "make import bulletproof" items are small and live in this fork:

- Confirm `ANIBND` is re-exported from `soulstruct.havok.fromsoft.eldenring.__init__`
  (currently import via `...eldenring.anibnd import ANIBND`).
- Exercise `tests/animations` `test_er()` against a real ER (not just NR) ANIBND.
- Validate end-to-end in the GUI (playback preview, action assignment on armature).

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
