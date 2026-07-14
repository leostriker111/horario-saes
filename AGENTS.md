# AGENTS.md — horario-saes

Tkinter GUI app for building class schedules from SAES (university enrollment system) TXT exports. Imports groups, resolves credit values/equivalencies, and exports schedules as PDF/PNG/JPG/SVG.

## Commands

- `python -m horario_saes.main` — launch GUI (use `pythonw` on Windows to detach terminal)
- `horario.cmd` — Windows launcher (hidden terminal via `pythonw`)

## Architecture

- `horario_saes/main.py` — app entrypoint (`main()`), App (tk.Tk) orchestrates layout, events, refresh
- `horario_saes/modulos/parser_saes.py` — SAES TXT parser (`parsear()`), `Opcion`/`Sesion` dataclasses, `chocan()` conflict detection, plan/equivalency table extraction (heuristic column detection), credit matching via fuzzy name comparison
- `horario_saes/modulos/modelo.py` — `Estado` holds all state (opciones, ramas, creditos, favoritos, seleccion), persists to `~/.horario_saes/sesion.json`, branching support (`Rama`)
- `horario_saes/modulos/dialogos.py` — modal dialogs: export, plan view, checklist, block creator, filters, professor view, branch tree
- `horario_saes/modulos/exportar.py` — render schedules to Pillow image or SVG string; PDF via Pillow multi-page save
- `horario_saes/modulos/reloj.py` — custom clock-style time picker widget

## Key facts

- Only dependency: `pillow>=10`
- Session auto-saves to `~/.horario_saes/sesion.json` on every refresh
- Migrates legacy session from `datos/sesion.json` (repo sibling) on first run
- TXT format: tab-separated SAES copy-paste (10+ columns: grupo, materia, profesor, edificio, salon, then 5 day-columns with time ranges like `7:00-8:50`). Optional plan/equivalency tables at end.
- 7:00–22:00 hardcoded schedule window (`HORA_INI=7, HORA_FIN=22`)
- Branching: fork a branch from current selection, rename/delete via tree view
- Export dialog offers: current branch, all branches, or selected branches
- Font fallback: expects Segoe UI (`C:/Windows/Fonts/segoeui*.ttf`), falls back to PIL default on Linux
- `__pycache__/`, `datos/`, `dist/`, `*.egg-info/`, `build/` are gitignored
