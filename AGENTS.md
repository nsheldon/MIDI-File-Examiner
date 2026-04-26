# AGENTS.md

## Project Scope
- This repository is a Python desktop utility for inspecting MIDI files.
- The main analysis logic lives in `midi_examiner.py`.
- The GUI layer lives in `midi_examiner_gui.py`.
- Patch/instrument lookup support lives in `midi_patches_db.py` with data in `midi_patches.db`.
- App bundling/build support lives in `create_app.py`.
- Packaged macOS app output exists under `MIDI File Examiner.app/`; treat it as a build artifact unless the task is explicitly about packaging metadata.

## Working Rules
- Keep changes tightly scoped to the user’s request.
- Prefer fixing core logic in source files over editing generated or packaged app contents.
- Do not modify `__pycache__/` contents.
- Do not replace `midi_patches.db` unless the task explicitly requires a database update or migration.
- Preserve current file/module names unless the user asks for a structural refactor.

## Python Workflow
- Use the project root `MIDI File Examiner/` as the working directory for commands.
- Read dependencies from `requirements.txt` and project metadata from `pyproject.toml`.
- When adding Python code, follow existing style in the touched file and keep imports simple.
- Prefer small, direct functions over broad rewrites.
- Avoid adding new dependencies unless clearly necessary.

## Expected Entry Points
- `midi_examiner.py`: core MIDI parsing/examination behavior.
- `midi_examiner_gui.py`: UI wiring and user-facing interactions.
- `create_app.py`: build/package automation for the macOS app bundle.

## Validation
- For logic-only changes, run the smallest practical check first.
- If tests do not exist, validate by running the relevant Python entry point or a targeted syntax check.
- For packaging changes, validate through `create_app.py` rather than editing `.app` bundle contents by hand.
- If a command cannot be run, state that clearly in the final response.

## Editing Guidance
- Update `README.md` when behavior, usage, or setup steps change.
- Update `CHANGELOG.md` only if the user asks for release-note maintenance or the repo already expects it for the requested change.
- Keep comments brief and only where the code would otherwise be hard to follow.
- Prefer ASCII unless a file already requires other characters.

## Safety Notes
- Treat the checked-in `.app` bundle as derived output.
- Avoid destructive file operations on user MIDI assets or the patch database.
- If a request would require guessing the intended MIDI analysis behavior, inspect existing logic first and preserve current output conventions unless the user asks to change them.
