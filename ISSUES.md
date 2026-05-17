# Open Issues — SAR Page Refactor

Three issues for the intern sprint. Read `view/radar.py` and `README.md` (Architecture section) before starting any of them.

---

## Issue 1 — UX: Tighten the SAR page layout and improve user cues

**Label:** `ux` `good first issue`

### Context

The SAR page (`view/radar.py`) was scaffolded quickly and has several layout problems. The dialog is fixed at **800 × 404 px**; with the 38 px header, the SAR page body is **366 px tall**. The card's content area (after the 40 px tab bar and 46 px nav bar) is only **~252 px**. Every pixel counts.

### Problems to fix

#### Tab bar (`setup_radar_page`, lines 284–298)
- The two tab buttons left-align and leave a dead stretch on the right. They should span the full tab bar width equally — give each button a `setSizePolicy(Expanding, Fixed)` and remove the trailing `addStretch`.
- The tab bar background (`#f8f9fa`) bleeds visually into the card. Remove the background color from `sarTabBar` so it reads as part of the card header, not a separate stripe.

#### Back button and step label (`setup_radar_page`, lines 333–342)
- `btn_back` is always visible but disabled on step 1 (line 362). A disabled Back button on the first tab is confusing — there is nowhere to go back to. **Hide it on step 1** (`setVisible(False)`), show it only on step 2.
- `step_lbl` ("Step 1 of 2", line 363) is redundant — the tab buttons already communicate position. Remove the label and reclaim the space in the nav bar. The nav bar can then drop from 46 px to 38 px.

#### "Run" button (`setup_radar_page`, lines 346–370)
- `btn_next` is labeled "Run" and is hidden on the Results tab (`setVisible(index == 0)`, line 364). When the user is on Results, there is no way to re-run the query without going back manually. **Keep the button visible on both tabs.** On Results, change the label to "Run Again".
- The button at the bottom-right of the nav bar is the primary CTA — give it a wider fixed size (`120, 30`) so it is easier to spot.

#### Inputs tab spacing (`_build_inputs_tab`, lines 74–150)
- `lay.setSpacing(10)` is too loose. Tighten to **6 px** so all controls fit without the trailing `addStretch` pushing things around.
- The three processing-option checkboxes (lines 140–148) are stacked vertically and take ~90 px. Lay them out in a **2 + 1 grid** (two on the first row, one on the second) using a `QHBoxLayout` inside a `QVBoxLayout`, saving ~30 px of height.
- The "PROCESSING OPTIONS" field label above the checkboxes (line 139) reads oddly next to plain checkboxes. Change it to a lighter section separator: a thin 1 px `#e0e0e0` `QFrame(HLine)` followed by the label inline, or just drop the label and rely on the checkbox text alone.

#### Results tab empty state (`_build_results_tab`, lines 153–206)
- `sar_web_view` is blank white before a query runs. Add an HTML placeholder loaded at construction time:
  ```python
  dialog.sar_web_view.setHtml(
      "<body style='margin:0;display:flex;align-items:center;justify-content:center;"
      "height:100%;font-family:sans-serif;color:#bdbdbd;font-size:13px;background:#f8f9fa;'>"
      "Run a query to see results.</body>"
  )
  ```
- The date row (line 181–200) mixes a "Date" label, a combo, a stretch, and two action buttons in one `QHBoxLayout`. The two action buttons ("Preview" and "Download & Preview") are hard to distinguish at a glance. Restructure: put the date combo + "Preview" on the left, "Download & Preview" on the right, and give "Batch Download (All Dates)" its own row at the bottom with a left-align.

#### User cues (general)
- When the query is running (future backend work), `btn_next`/`btn_back` should be disabled and a `QLabel` status line should appear above the nav bar reading "Querying GEE…". Reserve a fixed 16 px `QLabel` (`dialog.sar_status_lbl`) for this now (hidden by default, text empty) so the backend issue can use it without touching the layout again.
- Date fields (`sar_date_start`, `sar_date_end`) have no format hint beyond the placeholder. Add `setToolTip("Format: YYYY-MM-DD")` to both.

### Files to touch

- `view/radar.py` — all layout changes go here, nowhere else
- No service imports, no signal wiring — this issue is **view only**

### Acceptance criteria

- [ ] Back button hidden on Inputs tab, visible on Results tab
- [ ] Step label removed; nav bar height reduced to 38 px
- [ ] "Run" / "Run Again" button always visible, 120 px wide
- [ ] Tab buttons span the full tab bar width equally
- [ ] Inputs tab spacing tightened to 6 px; checkboxes in 2+1 layout
- [ ] `sar_web_view` shows a placeholder message before any query runs
- [ ] `dialog.sar_status_lbl` reserved (hidden) in the nav bar
- [ ] Date fields have tooltips
- [ ] No regressions on the auth or AOI/DEM pages

---

## Issue 2 — Backend: Inputs tab — SAR query service and signal wiring

**Label:** `backend` `sar`

### Context

The Inputs tab widgets are in place (`view/radar.py`, `_build_inputs_tab`, lines 74–150) but no service exists and no signals are wired. This issue covers everything from the user pressing "Run" to the results being ready for the Results tab to display.

The plugin already uses `ee-s1-ard` (see README — Supported Parameters). The pattern to follow is `dem_handler.py` + `services/dem_service.py`: a handler class owns the QGIS state, a service class owns the `ee` SDK calls, and `aglgis.py` wires the signals.

### Architecture boundary (mandatory)

- `services/sar_service.py` — owns all `ee` SDK and `ee-s1-ard` calls. **No Qt imports.**
- `aglgis.py` — wires `dialog.sar_btn_next.clicked` → handler. This is the **only** file that imports both UI and services.
- `view/radar.py` — **do not touch** for this issue (layout is handled in Issue 1).

### Tasks

#### 1. Create `services/sar_service.py`

Implement a `SARService` class. Constructor signature:
```python
class SARService:
    def __init__(self, gee_service: GEEService): ...
```

It must expose one public method:
```python
def run_query(
    self,
    geometry,           # ee.FeatureCollection from AOIService
    start_date: str,    # "YYYY-MM-DD"
    end_date: str,      # "YYYY-MM-DD"
    polarization: str,  # "VV" | "VH" | "VVVH"
    output_format: str, # "DB" | "LINEAR"
    apply_border_noise: bool,
    apply_terrain_flattening: bool,
    apply_speckle_filtering: bool,
) -> dict:
    ...
```

`run_query` calls the `ee-s1-ard` package and returns a dict with at least:
```python
{
    "dates": ["2023-01-05", ...],          # sorted list of acquisition dates
    "mean_backscatter": [−12.3, ...],      # mean dB value per date over AOI
    "collection": ee.ImageCollection,      # the processed collection, for later download
}
```

Export `SARService` from `services/__init__.py`.

#### 2. Create a QThread worker

Running GEE queries on the main thread blocks the UI. Add a `SARQueryWorker(QThread)` class — either in `services/sar_service.py` or a new `services/sar_worker.py`. It receives the same parameters as `run_query`, calls it in `run()`, and emits:
```python
query_finished = pyqtSignal(dict)
query_failed = pyqtSignal(str)   # human-readable error message
```

#### 3. Input validation (before firing the worker)

Before starting the worker, validate in `aglgis.py` (or a thin helper):
- AOI layer is selected and not empty (`sar_layer_combo.currentLayer() is not None`).
- Both date strings match `YYYY-MM-DD` and `start_date < end_date`.
- User is authenticated (`gee_service.is_authenticated`).

On failure, call `dialog.pop_message(message, level=Qgis.Warning)` and return early. Do **not** switch to the Results tab.

#### 4. Wire signals in `aglgis.py` (inside `_finish_init`)

```python
# sar_btn_next is labeled "Run" / "Run Again"
self.dialog.sar_btn_next.clicked.connect(self._on_sar_run)
```

`_on_sar_run` should:
1. Validate inputs (see §3).
2. Disable `sar_btn_next` and `sar_btn_back`, show `sar_status_lbl` with "Querying GEE…".
3. Get the AOI via `aoi_service.get_aoi_from_layer(layer)`.
4. Start the `SARQueryWorker`.
5. Connect `worker.query_finished` → `_on_sar_query_done`.
6. Connect `worker.query_failed` → `_on_sar_query_failed`.

`_on_sar_query_done(result: dict)`:
1. Store `result` on `self` (needed by Issue 3).
2. Switch to Results tab (`dialog.sar_stack.setCurrentIndex(1)` via `_set_tab` if exposed, otherwise `dialog.sar_stack.setCurrentIndex(1)`).
3. Re-enable buttons, hide `sar_status_lbl`.

`_on_sar_query_failed(msg: str)`:
1. `dialog.pop_message(msg, level=Qgis.Critical)`.
2. Re-enable buttons, hide `sar_status_lbl`.

### Files to create / touch

| File | Action |
|---|---|
| `services/sar_service.py` | Create |
| `services/__init__.py` | Export `SARService` |
| `aglgis.py` | Import `SARService`, instantiate in `_finish_init`, add `_on_sar_run`, `_on_sar_query_done`, `_on_sar_query_failed` |

### Acceptance criteria

- [ ] `SARService.run_query` calls `ee-s1-ard` and returns the expected dict
- [ ] Query runs on a `QThread` — QGIS UI stays responsive during execution
- [ ] Invalid inputs (no layer, bad dates, unauthenticated) show a warning and do not start the worker
- [ ] Successful query switches to the Results tab automatically
- [ ] Failed query shows an error message bar and stays on the Inputs tab
- [ ] `sar_status_lbl` visible while query runs, hidden otherwise
- [ ] No `ee` imports in `view/` or `aglgis_dialog.py`
- [ ] No Qt widget imports in `services/sar_service.py`

---

## Issue 3 — Backend: Results tab — display, preview, and download

**Label:** `backend` `sar`

### Depends on

Issue 2 must be merged first. This issue assumes `aglgis.py` stores the query result dict (`self._sar_result`) and that the Results tab is shown after a successful query.

### Context

The Results tab (`_build_results_tab`, lines 153–206 in `view/radar.py`) has a `QWebView` for a time-series chart and several action buttons. None of them do anything yet. This issue wires each button to a real action.

### Tasks

#### 1. Populate the date combo and render the chart

In `_on_sar_query_done` (from Issue 2), after storing the result:

```python
# Populate date picker
combo = dialog.sar_result_date_combo
combo.clear()
combo.addItems(result["dates"])

# Render chart
html = _build_chart_html(result["dates"], result["mean_backscatter"])
dialog.sar_web_view.setHtml(html)
```

Write `_build_chart_html(dates, values) -> str` in a new helper `services/sar_chart.py`. It must return a self-contained HTML string (no CDN dependencies — embed a minimal chart using inline SVG or the vendored Plotly bundle if one exists in `extlibs/`). The chart should be a simple line + scatter of mean backscatter (dB) over time. Style it to match the plugin palette (`#1b6b39` for the line, `#f5f5f5` page background).

#### 2. "Open in Browser" button (`sar_btn_open_browser`)

```python
dialog.sar_btn_open_browser.clicked.connect(self._on_sar_open_browser)
```

`_on_sar_open_browser`:
1. Write `dialog.sar_web_view.page().mainFrame().toHtml()` to a temp `.html` file.
2. Open it with `QDesktopServices.openUrl(QUrl.fromLocalFile(path))`.

#### 3. "Download as CSV" button (`sar_btn_download_csv`)

```python
dialog.sar_btn_download_csv.clicked.connect(self._on_sar_download_csv)
```

`_on_sar_download_csv`:
1. Open a `QFileDialog.getSaveFileName` with filter `"CSV (*.csv)"`.
2. Write two columns (`date`, `mean_backscatter_db`) from `self._sar_result`.
3. On success, call `dialog.pop_message("CSV saved.", level=Qgis.Success)`.

#### 4. "Preview" button (`sar_btn_preview`)

Loads the selected date's SAR image into QGIS as a temporary raster layer (no file saved to disk).

```python
dialog.sar_btn_preview.clicked.connect(self._on_sar_preview)
```

`_on_sar_preview`:
1. Get selected date from `sar_result_date_combo.currentText()`.
2. Call a new `SARService.download_image(collection, date, aoi, output_format)` method that clips the collection to the given date and AOI and returns a GeoTIFF path (follow `DEMService.download_dem` as the model — same temp-file pattern, output named `AGLgis_SAR_<date>.tif`).
3. Pass the path to a renderer (either `DEMRenderer.load_dem_to_qgis` or a new `SARRenderer` if the color ramp should differ — a diverging blue-white-red ramp suits backscatter).
4. Add the layer to the QGIS canvas.
5. Show progress: disable the button during download, re-enable on completion.

The download must run on a `QThread` (same pattern as Issue 2's worker).

#### 5. "Download & Preview" button (`sar_btn_download_preview`)

Same as "Preview" but prompts for a save path with `QFileDialog.getSaveFileName` before downloading, then copies the temp file to that path after loading into QGIS.

#### 6. "Batch Download (All Dates)" button (`sar_btn_batch_download`)

Downloads every date in `self._sar_result["dates"]` as a separate GeoTIFF.

`_on_sar_batch_download`:
1. Prompt for a **folder** with `QFileDialog.getExistingDirectory`.
2. Loop over dates in the worker thread, calling `SARService.download_image` for each.
3. Emit a progress signal (`int` 0–100) so the UI can update `sar_status_lbl` with "Downloading 3 / 12…".
4. On completion, show a summary message bar with the count and folder path.

### Files to create / touch

| File | Action |
|---|---|
| `services/sar_chart.py` | Create — `_build_chart_html(dates, values) -> str` |
| `services/sar_service.py` | Add `download_image` method (from Issue 2) |
| `services/__init__.py` | Export any new helpers |
| `aglgis.py` | Add handlers for all five buttons |

### Acceptance criteria

- [ ] After a successful query, `sar_result_date_combo` is populated and the chart renders in `sar_web_view`
- [ ] "Open in Browser" opens the chart HTML in the system browser
- [ ] "Download as CSV" saves a valid two-column CSV and shows a success message
- [ ] "Preview" downloads the selected date's GeoTIFF, loads it into QGIS, and applies a color ramp
- [ ] "Download & Preview" additionally saves to a user-chosen path
- [ ] "Batch Download" saves all dates to a folder and reports progress in `sar_status_lbl`
- [ ] All downloads run on a `QThread` — UI stays responsive
- [ ] Chart uses no external CDN (plugin works offline after extlibs are installed)
- [ ] No `ee` imports outside `services/`; no Qt widget imports inside `services/`
