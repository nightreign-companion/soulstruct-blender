# Contributing to soulstruct-blender

## Commit messages

Use [Conventional Commits](https://www.conventionalcommits.org/) so history stays scannable and changelog-friendly.

### Format

```
<type>(<scope>): <short summary>

Optional body wrapped at ~72 characters. Explain motivation and behavior,
not a file list.
```

- **type:** `feat`, `fix`, `docs`, `test`, `chore`, `refactor`, `build`, `ci`
- **scope:** area of change, e.g. `stan-tools`, `animation`, `flver`, `shaders`, `submodules`, `blender`, `havok`
- **summary:** imperative mood, lowercase, no trailing period, ≤72 characters

### Examples

```
feat(stan-tools): add character search and ANIBND clip picker
fix(animation): resolve multi-div compendium on ER character import
chore(submodules): bump soulstruct-havok for hk2018 propertyBag export
docs(stan-tools): document DSAS and ModEngine 3 workflow
test(blender): add headless Nightreign c7720 import smoke test
```

### Submodule repos

Commits inside `io_soulstruct_lib/soulstruct` and `io_soulstruct_lib/soulstruct-havok` follow the same rules. Parent-repo `chore(submodules):` commits should only bump pointers with a one-line reason.

### Breaking changes

Append `!` after the type/scope or add a `BREAKING CHANGE:` footer when behavior is incompatible.
