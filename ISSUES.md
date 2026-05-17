# Open Issues — SAR Page Refactor

Three issues for the intern sprint. Read `view/radar.py` and `README.md` (Architecture section) before starting any of them.

---

## Issue 1 — UX: Tighten the SAR page layout and improve user cues

**Label:** `ux` `good first issue`

### Context

The SAR page (`view/radar.py`) was scaffolded quickly and has several layout and usability problems. The dialog is fixed at **800 × 404 px**; with the 38 px header, the body is **366 px tall**. The card's usable content area (after the tab bar and nav bar) is around **252 px** — tight enough that wasted space is noticeable.

### What's wrong

**Tab bar** — tab buttons left-align and leave dead space to the right. The tab bar background visually separates from the card, making it look like two components instead of one.

**Back button** — visible but disabled on the Inputs tab. There is nowhere to go back to from the first tab, so a disabled button is just noise.

**Step label** ("Step 1 of 2") — redundant with the tab buttons, which already communicate position. Wastes nav bar height.

**"Run" button** — disappears when the user switches to the Results tab. There is no way to re-run the query without going back manually. It should stay visible on both tabs, with a label that reflects context ("Run" on Inputs, "Run Again" on Results).

**Inputs tab spacing** — controls are spaced too loosely. The three processing-option checkboxes stacked vertically take disproportionate vertical space for what they convey.

**Results tab empty state** — `sar_web_view` is blank white before a query runs. There is no cue telling the user what to do.

**Results tab action area** — the date picker, Preview, Download & Preview, and Batch Download buttons are laid out in a way that makes the hierarchy of actions unclear.

**User cues** — no status area reserved for backend feedback ("Querying GEE…", "Downloading…"). Adding one later will require touching this file again. Reserve a hidden `dialog.sar_status_lbl` now so the backend issues don't need to change the layout.

### Scope

- `view/radar.py` only — no service imports, no signal wiring
- Keep all existing widget attribute names on `dialog` (they are referenced by future backend issues)
- Add `dialog.sar_status_lbl` as a new hidden label in the nav area

### Acceptance criteria

- [ ] Tab buttons fill the tab bar width evenly; no dead space to the right
- [ ] Back button hidden on the Inputs tab, visible on the Results tab
- [ ] Step label removed
- [ ] "Run" / "Run Again" button always visible; label changes by tab
- [ ] Inputs tab controls fit without excess whitespace at the bottom
- [ ] Processing-option checkboxes are not stacked in a single column
- [ ] `sar_web_view` shows a clear placeholder before any query runs
- [ ] Results tab action area has a readable visual hierarchy
- [ ] `dialog.sar_status_lbl` exists, is hidden by default, and is accessible from `aglgis.py`
- [ ] No regressions on the auth or AOI/DEM pages

---

## Issue 2 — Backend: Inputs tab — SAR query service and signal wiring

**Label:** `backend` `sar`

### Context

The Inputs tab has all its widgets (`view/radar.py`, `_build_inputs_tab`) but no service exists and no signals are wired. This issue covers everything from the user pressing "Run" to the results being ready for the Results tab.

The plugin wraps the `ee-s1-ard` package (see README — Supported Parameters for the full parameter set). The pattern to follow is the existing `dem_handler.py` + `services/dem_service.py` pairing: a service class owns the `ee` SDK calls, a handler or controller method owns the QGIS state, and `aglgis.py` is the only file that wires them together.

### Deliverables

A working `services/sar_service.py` that wraps the `ee-s1-ard` query and returns enough data for the Results tab to display (dates, per-date statistics, and a reference to the processed collection for later download).

Signal wiring in `aglgis.py` (inside `_finish_init`) connecting the "Run" button to the service, with input validation before the query fires and appropriate UI feedback (via `dialog.sar_status_lbl` and `dialog.pop_message`) on success, failure, and while running.

GEE queries must run off the main thread so QGIS stays responsive.

### Architecture constraints (non-negotiable)

- `services/sar_service.py` — no Qt imports
- `view/radar.py` — do not modify (layout is Issue 1)
- `aglgis.py` — the only file that connects UI widgets to service calls

### Acceptance criteria

- [ ] "Run" button triggers a GEE query using all Inputs tab parameters
- [ ] Query runs off the main thread; QGIS UI stays responsive
- [ ] Invalid inputs (no layer, bad or missing dates, unauthenticated) surface a warning and do not start the query
- [ ] `sar_status_lbl` is visible while the query runs, hidden otherwise
- [ ] A successful result is stored and the UI transitions to the Results tab
- [ ] A failed query surfaces an error message and stays on the Inputs tab
- [ ] No `ee` imports outside `services/`
- [ ] No Qt widget imports inside `services/sar_service.py`

---

## Issue 3 — Backend: Results tab — display, preview, and download

**Label:** `backend` `sar`

### Depends on

Issue 2 merged. The query result (dates, statistics, processed collection) is available in `aglgis.py` after a successful run.

### Context

The Results tab (`_build_results_tab` in `view/radar.py`) has a `QWebView` for a time-series chart and five action buttons. None are wired. This issue makes all of them functional.

The chart should show mean backscatter over time for the queried AOI. It must work offline (no CDN) — the plugin is used in field environments. Look at what is already in `extlibs/` before pulling in a new charting dependency.

For image download, follow the pattern in `services/dem_service.py` and `services/dem_renderer.py`. Output files should be named consistently with the existing `AGLgis_` prefix convention.

### Deliverables

After a successful query: the date combo is populated, the chart renders in `sar_web_view`, and all five buttons work:

- **Open in Browser** — opens the chart in the system browser
- **Download as CSV** — exports the time-series data
- **Preview** — downloads the selected date's GeoTIFF and loads it into QGIS
- **Download & Preview** — same, but also saves to a user-chosen path
- **Batch Download (All Dates)** — downloads every date to a folder, with progress reported in `sar_status_lbl`

All downloads must run off the main thread.

### Architecture constraints (non-negotiable)

- Chart generation logic belongs in a new service file, not in `aglgis.py`
- No CDN dependencies in the chart HTML
- No `ee` imports outside `services/`
- No Qt widget imports inside service files
- `view/radar.py` — do not modify

### Acceptance criteria

- [ ] Date combo populated and chart visible after a successful query
- [ ] Chart uses no external CDN
- [ ] "Open in Browser" opens the chart in the system default browser
- [ ] "Download as CSV" saves a valid file and confirms success via message bar
- [ ] "Preview" loads the selected date's raster into QGIS with a color ramp applied
- [ ] "Download & Preview" additionally persists the file to a user-chosen path
- [ ] "Batch Download" saves all dates and reports progress in `sar_status_lbl`
- [ ] All downloads run off the main thread; QGIS UI stays responsive
- [ ] No `ee` imports outside `services/`; no Qt widget imports inside service files
