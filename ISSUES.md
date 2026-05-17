# Open Issues — SAR Page Refactor

Read `view/radar.py` and `README.md` before starting.

---

## Issue 1 — UX: SAR page polish

**Label:** `ux` `good first issue`

The SAR page layout feels unfinished. Controls are spaced too loosely for the fixed dialog size, some buttons are confusing in context (Back on the first tab, Run disappearing on the second), and the Results tab gives no feedback before a query runs. The processing-option checkboxes also take up disproportionate space.

Fix the layout, spacing, and user cues. Add a hidden `dialog.sar_status_lbl` somewhere sensible so the backend issues can surface query progress without touching the view again.

**Scope:** `view/radar.py` only. Do not rename existing `dialog.*` attributes.

---

## Issue 2 — Backend: run the SAR query

**Label:** `backend` `sar`

Wire the "Run" button to a real GEE query using the `ee-s1-ard` package (see README — Supported Parameters). Validate inputs before firing. Keep the UI responsive while the query runs. Surface errors via `dialog.pop_message` and transition to the Results tab on success.

Follow the layer separation in `README.md`: `ee` SDK calls belong in a new service file, signal wiring belongs in `aglgis.py`.

---

## Issue 3 — Backend: Results tab actions

**Label:** `backend` `sar`

**Depends on Issue 2.**

Make all five Results tab buttons functional: chart display in the web view (no CDN — plugin runs offline), open in browser, CSV export, single-date preview in QGIS, and batch download with progress feedback. Downloads must not block the UI.

Follow the file naming and rendering conventions already established in `services/dem_service.py` and `services/dem_renderer.py`.
