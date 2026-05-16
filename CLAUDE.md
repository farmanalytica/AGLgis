# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commits

Do not include `Co-Authored-By` or any Claude/AI attribution in commit messages.

## Environment

This is a QGIS plugin. Python runtime is the one bundled with OSGeo4W (`C:\OSGeo4W\apps\qgis-ltr\bin\python-qgis-ltr.exe`). There is no standalone test runner or build step — the plugin is loaded directly by QGIS.

To reload the plugin during development, use the **Plugin Reloader** plugin inside QGIS.

Vendored dependencies live in `extlibs/` and are added to `sys.path` by `__init__.py`. Do not install packages into the system Python.

## Architecture

### Strict layer separation

`easy.py` is the **only** file that imports both UI and services. It instantiates `EasyDemDialog`, `GEEService`, and `DEMHandler`, then wires all signals in one place. Maintain this boundary:

- `view/` — Qt widgets only; no `ee` SDK, no business logic, no service imports.
- `services/` — pure logic; no Qt widgets, no dialog references.
- `dem_handler.py` — orchestrator; receives the dialog and services as constructor arguments, never imports them globally.

### How widgets are exposed

`view/auth.py` and `view/download_dem.py` attach widgets directly onto the `dialog` object (e.g. `dialog.btn_authenticate`, `dialog.layer_combo`). `easy.py` and `dem_handler.py` then access them via those attributes. Do not return widget references from the setup functions.

### Signal flow

```
UI event → easy.py handler or DEMHandler method → service call → dialog.pop_message() / messageBar()
```

### DEM catalog

`assets/dem_catalog.json` is the source of truth for available datasets. Each entry has `is_collection` (bool) controlling whether `DEMRegistry` wraps it as `ee.ImageCollection` or `ee.Image`, and `coverage_bbox` used for pre-filtering before hitting GEE.

### Sidebar

`view/sidebar.py` — `Sidebar(QFrame)` collapses to 64 px (icons only) / expands to 184 px on hover. `set_active_page('auth'|'download')` drives highlight state. Width is animated via `QPropertyAnimation`.

### Dialog layout

Fixed size 800×404 px. Root `QVBoxLayout`: white header (38 px) → body `QHBoxLayout` (sidebar + right column) → right column `QVBoxLayout` (stack + footer). Footer (36 px, transparent) is inside the right column, not at root level, so the sidebar spans full height.

### Translations

User-visible strings are wrapped with `_tr()` (`QCoreApplication.translate("EasyDem", text)`) in every module. Translation context name is `"EasyDem"` everywhere — never `"easydem"` or anything else.

Source files are `i18n/easydem_<locale>.ts` (Qt TS XML). Compiled binaries are `i18n/easydem_<locale>.qm`. `easy.py` loads the `.qm` matching the active QGIS locale on plugin init and removes it on unload.

**OSGeo4W does not ship `lrelease`.** Compile with the included script instead:

```bat
python-qgis-ltr compile_translations.py
```

Run from the plugin root in the OSGeo4W Shell. Supported locales: `pt_BR`, `fr`, `it`, `es`, `hi`, `zh_CN`. English is the default — no `.qm` needed.
