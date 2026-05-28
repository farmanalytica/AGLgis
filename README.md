## AGLgis

AGLgis is a graphical interface designed to simplify the use of the [Sentinel-1 SAR Backscatter Analysis Ready Data Preparation in Google Earth Engine](https://pypi.org/project/ee-s1-ard/) package in QGIS.

This plugin allows users to configure and run Sentinel-1 SAR data processing without the need to write code.

**Requirements:** a Google Earth Engine account and a Google Cloud Console project with the Earth Engine API enabled.

### Main features

- **DEM Module**: Download and visualize elevation data with interactive filtering and styling.
- **SAR Module**: Process Sentinel-1 SAR data with full control over acquisition parameters and preprocessing options.
  - Support for multiple spectral indices: VV/VH Ratio, RVI (Radar Vegetation Index), DpRVI (Dual-pol SAR Vegetation Index)
  - Flexible render modes: RGB composites and single-band pseudocolor with Viridis palette
  - Batch download with progress tracking and cancellation support
  - Interactive time-series visualization with date filtering
  - CSV export of results
- Border noise correction, terrain flattening, and speckle filtering options.
- Non-modal dialogs for filter and preview operations with immediate chart updates.
- Automatic layer management: new layers appear at top of Layers panel, basemaps stay at bottom.

### Supported Parameters

| Parameter                     | Type         | Description                                         | Default      |
|-------------------------------|--------------|-----------------------------------------------------|--------------|
| geometry                      | ee.Geometry  | Area of interest                                    | Required     |
| start_date                    | str          | Start date (YYYY-MM-DD)                             | Required     |
| stop_date                     | str          | End date (YYYY-MM-DD)                               | Required     |
| polarization                  | str          | Polarization (VV, VH, VVVH)                         | VVVH         |
| apply_border_noise_correction | bool         | Apply border noise correction                       | True         |
| apply_terrain_flattening      | bool         | Apply terrain flattening                            | True         |
| apply_speckle_filtering       | bool         | Apply speckle filtering                             | True         |
| output_format                 | str          | Output format (LINEAR, DB)                          | DB           |

---

## Project Structure

```
AGLgis/
├── __init__.py              # QGIS entry point — registers the plugin via classFactory()
├── aglgis.py                # Plugin controller — owns the QGIS lifecycle (initGui, unload, run)
├── aglgis_dialog.py         # UI layer — dialog shell (header, stack, footer) and page navigation
├── build_plugin.py          # Full build script — clean extlibs, install deps, compile translations, zip
├── compile_translations.py  # Compiles i18n/*.ts → *.qm without needing lrelease
├── extlibs_manager.py       # Background extlibs downloader (QThread); triggered by __init__.py on first run when extlibs/ is absent
├── assets/
│   └── dem_catalog.json     # DEM dataset definitions (name, collection, band, resolution, bbox)
├── i18n/
│   ├── aglgis_pt_BR.ts/.qm  # Portuguese (Brazil)
│   ├── aglgis_fr.ts/.qm     # French
│   ├── aglgis_it.ts/.qm     # Italian
│   ├── aglgis_es.ts/.qm     # Spanish
│   ├── aglgis_hi.ts/.qm     # Hindi
│   └── aglgis_zh_CN.ts/.qm  # Chinese (Simplified)
├── controllers/
│   ├── __init__.py          # Controllers package marker
│   ├── auth_ctrl.py         # Auth page controller — handles authentication, reset, and folder selection
│   ├── dem_ctrl.py          # DEM page controller — orchestrates AOI management and service calls
│   └── sar_ctrl.py          # SAR page controller — orchestrates SAR processing, preview, filtering, and export
├── view/
│   ├── __init__.py                  # View package marker
│   ├── auth.py                      # Authentication page widget construction (setup_auth_page)
│   ├── download_dem.py              # AOI/DEM page widget construction (setup_download_dem_page)
│   ├── radar.py                     # Radar (SAR) page widget construction (setup_radar_page)
│   ├── sar_plot.py                  # SAR time-series chart rendering with Plotly
│   ├── sar_date_filter_dialog.py    # Non-modal date filter dialog with cascading checkboxes
│   ├── sidebar.py                   # Permanent collapsible navigation sidebar (Sidebar, SidebarNavButton)
│   └── styles.py                    # Shared Qt stylesheet constants (STYLE_DIALOG, STYLE_BTN_PRIMARY, …)
└── services/
    ├── __init__.py                  # Exports service classes
    ├── gee_service.py               # Google Earth Engine business logic and authentication
    ├── aoi_service.py               # AOI extraction and conversion to EE objects
    ├── dem_service.py               # Downloads DEM GeoTIFF from Google Earth Engine
    ├── dem_registry.py              # Loads and queries the DEM catalog; checks dataset availability
    ├── dem_renderer.py              # DEM layer loading with Magma color ramp
    ├── dataset_manager.py           # Dataset availability queries and UI updates
    ├── settings_manager.py          # Settings persistence (QgsSettings)
    ├── map_utils.py                 # Map-related utility functions (Google Hybrid basemap)
    ├── sar_service.py               # SAR data processing with spectral indices (RVI, DpRVI, VV/VH Ratio)
    ├── sar_worker.py                # Background workers: SARWorker, SARPreviewWorker, SARBatchDownloadWorker
    ├── sar_renderer.py              # SAR layer loading with RGB composites and pseudocolor rendering
    ├── raster_renderer_utils.py     # Common utilities for pseudocolor rendering (shared by DEM and SAR)
    └── sar_metadata_dialog.py       # Metadata display dialogs
```

---

## Architecture

The codebase follows a **UI / Controller / Service** separation:

### `aglgis.py` — Plugin Entry Point
The QGIS plugin entry point. Handles toolbar/menu registration (`initGui`), teardown (`unload`), and launches the dialog (`run`). Service and controller instantiation (`GEEService`, `DEMCtrl`, `AuthCtrl`) and all signal wiring are deferred to `_finish_init()`, which is called only once extlibs are confirmed ready — either already extracted on disk, or after `ExtlibsDownloader` finishes and emits `download_done`. Until extlibs are ready, `run()` shows the loading page and waits for the downloader signal. This is the only place UI and services are wired together.

### `aglgis_dialog.py` — UI Layer
Contains `AGLgisDialog(QDialog)`. Owns the dialog shell only: fixed header, central `QStackedWidget`, and fixed footer. Page widget construction is delegated to `view/auth.py` and `view/download_dem.py`. No knowledge of services or the `ee` SDK — all signal connections are made externally by the controller.

Internal conventions:
- `_setup_ui()` — builds header, body row (sidebar + stack), and footer; calls `setup_auth_page` and `setup_download_dem_page`
- `_build_header()` — white bar with brand label, dynamic page-title label (`_header_title`), and help button
- `_build_footer()` — FARM Analytica logo and attribution text
- `show_loading_page()` / `show_auth_page()` / `show_radar_page()` / `show_aoi_page()` — switch the active stack page
- `_sync_page_state(index)` — connected to `stack.currentChanged`; updates `_header_title` and calls `sidebar.set_active_page()` to keep navigation state in sync regardless of what triggers the page switch
- Four pages managed by a `QStackedWidget`: `loading_page` (first-run dependency download), `auth_page` (shown once extlibs are ready), `radar_page` (SAR data workflow), `aoi_page` (shown after authentication or via the skip shortcut)
- Permanent `Sidebar` instance lives in the body row; its `auth_requested`, `radar_requested`, and `download_requested` signals are connected to `_nav_to_auth`, `_nav_to_radar`, and `_nav_to_download`

### `view/` — Page Modules

Page widget construction is split into isolated modules. Each module exposes a single `setup_*` function that receives the dialog instance and its page widget, then attaches interactive widgets directly to the dialog so `aglgis.py` can wire signals without importing the modules.

#### `view/auth.py`
Builds the authentication page (`setup_auth_page`). Layout: left info column + right credential card + bottom browse-without-auth shortcut.

| Widget | Attribute | Purpose |
|---|---|---|
| `QgsPasswordLineEdit` | `project_id_input` | User-supplied GCP project ID |
| `QPushButton` | `btn_authenticate` | Validates ID and triggers GEE authentication |
| `QPushButton` | `btn_reset_auth` | Clears stored GEE credentials |
| `QPushButton` | `btn_go_to_aoi` | Skips authentication and navigates to AOI page |

#### `view/download_dem.py`
Builds the AOI and DEM download page (`setup_download_dem_page`). Layout: scrollable content area (inputs + metadata + buffer) above a fixed footer (folder picker + action buttons). Also defines `LimitedPopupComboBox`, a `QComboBox` subclass that caps popup height for long dataset catalogs.

| Widget | Attribute | Purpose |
|---|---|---|
| `QgsMapLayerComboBox` | `layer_combo` | Polygon layer selector for AOI |
| `LimitedPopupComboBox` | `dem_combo` | Lists DEM datasets available for the selected AOI |
| `QTextBrowser` | `dem_info` | Shows selected DEM dataset metadata |
| `QSlider` | `buffer_slider` | AOI buffer in metres (−300 … +300) |
| `QLabel` | `buffer_value_lbl` | Live display of current buffer value |
| `QLineEdit` | `folder_input` | Download destination path (read-only display) |
| `QPushButton` | `btn_browse_folder` | Opens folder picker dialog |
| `QPushButton` | `btn_hybrid_layer` | Adds a Google Hybrid basemap layer to QGIS |
| `QPushButton` | `btn_download_dem` | Downloads and loads the selected DEM into QGIS |

#### `view/radar.py`
Builds the Radar (SAR) data page (`setup_radar_page`). Layout: a full-width card with a two-tab interface (Inputs / Results) and a bottom navigation bar. The Inputs tab holds the SAR query parameters; the Results tab is a placeholder until the service layer lands. Tab switching is self-contained — no service dependencies.

| Widget | Attribute | Purpose |
|---|---|---|
| `QgsMapLayerComboBox` | `sar_layer_combo` | Vector layer selector for the SAR AOI |
| `QLineEdit` | `sar_date_start` | Start date input (`YYYY-MM-DD`) |
| `QLineEdit` | `sar_date_end` | End date input (`YYYY-MM-DD`) |
| `QComboBox` | `sar_sensor_combo` | Sentinel-1 product type (GRD / SLC) |
| `QComboBox` | `sar_pol_combo` | Polarization band (VV / VH / VV+VH) |
| `QComboBox` | `sar_format_combo` | Output format (GeoTIFF / COG) |
| `QStackedWidget` | `sar_stack` | Holds Inputs (index 0) and Results (index 1) pages |
| `QPushButton` | `sar_btn_back` | Goes to previous tab; disabled on the Inputs tab |
| `QPushButton` | `sar_btn_next` | Advances to Results tab ("Next") or triggers the query ("Run"); "Run" is disabled until the service layer is wired |
| `QLabel` | `sar_step_lbl` | Step indicator ("Step 1 of 2" / "Step 2 of 2") |

#### `view/sidebar.py`
Defines `Sidebar(QFrame)` and `SidebarNavButton(QPushButton)`. The sidebar is a permanent collapsible navigation rail shown on all pages. It collapses to 64 px (icon only) and expands to 184 px on hover via `QVariantAnimation`.

| Widget / method | Purpose |
|---|---|
| `btn_auth` | Navigates to the authentication page; emits `auth_requested` |
| `btn_radar` | Navigates to the SAR data page; emits `radar_requested` |
| `btn_download` | Navigates to the AOI/download page; emits `download_requested` |
| `set_active_page(page)` | Highlights the button matching `'auth'`, `'radar'`, or `'download'`; called by `_sync_page_state` in the dialog |

#### `view/styles.py`
Shared Qt stylesheet string constants imported by both page modules and `aglgis_dialog.py`.

| Constant | Applied to |
|---|---|
| `STYLE_DIALOG` | `QDialog` base — grey background, dark text, thin scrollbar |
| `STYLE_BTN_PRIMARY` | Solid green call-to-action buttons |
| `STYLE_BTN_SECONDARY` | White/green-border navigation buttons |
| `STYLE_BTN_HELP` | Circular "?" help button in the header |
| `STYLE_AOI_PAGE` | AOI page panel card, field labels, combo boxes, metadata browser |

### `controllers/` — Page Controllers

One controller per page. Each controller receives the dialog and services as constructor arguments and handles all user interactions for that page. Controllers sit between the UI (`view/`) and the business logic (`services/`) — they call service methods and update the dialog, but never import view modules directly.

#### `controllers/auth_ctrl.py` — `AuthCtrl`
Handles all user interactions on the authentication page.

| Method | Signature | Purpose |
|---|---|---|
| `handle_authentication` | `()` | Validates the project ID, calls `GEEService.authenticate`, and navigates to the AOI page on success |
| `handle_reset_authentication` | `()` | Delegates to `GEEService.reset_authentication` and reports the result |
| `handle_folder_selection` | `()` | Opens a folder picker and delegates to `SettingsManager` to persist the choice |

#### `controllers/dem_ctrl.py` — `DEMCtrl`
Orchestrates DEM operations and coordinates between services. Owns the current AOI state and QGIS map canvas interactions.

| Method | Signature | Purpose |
|---|---|---|
| `handle_layer_changed` | `(layer)` | Zooms the map canvas to the selected layer, then debounces 300 ms before loading the AOI and refreshing the dataset combobox |
| `load_available_datasets` | `()` | Queries `DEMRegistry` directly; lists all datasets when unauthenticated, otherwise filters by AOI coverage |
| `handle_dem_service` | `(interface)` | Downloads the selected DEM (with optional buffer) and delegates to `DEMRenderer` to load and style it in QGIS |
| `on_dataset_changed` | `()` | Delegates to `DatasetManager` to update the dataset info panel |
| `handle_hybrid_layer` | `()` | Loads the Google Hybrid basemap via `map_utils.hybrid_function()` and reports success via the message bar |

#### `controllers/sar_ctrl.py` — `SARCtrl`
Orchestrates SAR operations: processing, preview, filtering, export, and batch download. Manages time-series state and filter persistence.

| Method | Signature | Purpose |
|---|---|---|
| `handle_sar_run` | `()` | Validates inputs, triggers `SARWorker`, shows loading spinner, and displays results on completion |
| `handle_preview_image` | `()` | Downloads a single image to temp directory and loads it with selected render mode |
| `handle_download_preview` | `()` | Downloads a single image to user's folder and loads it with selected render mode |
| `handle_batch_download` | `()` | Creates progress dialog and triggers `SARBatchDownloadWorker` for batch download of filtered dates |
| `handle_filter_dates` | `()` | Opens non-modal date filter dialog; emits `filter_changed` signal on checkbox changes |
| `handle_export_csv` | `()` | Exports filtered time-series data to CSV with user-selected filename |
| `handle_open_browser` | `()` | Opens the time-series chart in the default browser with full Plotly toolbar |
| `handle_layer_changed` | `()` | Zooms map canvas to the selected AOI layer |

### `services/gee_service.py` — GEE Service
Contains `GEEService`. Imports `ee` and owns all Earth Engine SDK calls.

| Method | Signature | Purpose |
|---|---|---|
| `get_saved_project_id` | `()` | Returns the saved GCP project ID from `QSettings`, or empty string |
| `save_project_id` | `(project_id)` | Persists the GCP project ID to `QSettings`; connected to `project_id_input.textChanged` |
| `authenticate` | `(project_id: str)` | Authenticates with GEE using the given project; sets `is_authenticated = True` on success |
| `reset_authentication` | `()` | Clears stored GEE credentials and resets `is_authenticated` |

### `services/aoi_service.py` — AOI Service
Contains `AOIService`. Extracts geometry from a QGIS layer and converts it to an `ee.FeatureCollection`.

| Method | Signature | Purpose |
|---|---|---|
| `get_aoi_from_layer` | `(layer: QgsVectorLayer)` | Returns `(ee.FeatureCollection, bbox)` from a layer object; bbox is `(min_x, min_y, max_x, max_y)` in EPSG:4326, computed locally from the QGIS geometry |
| `get_aoi_from_layer_id` | `(layer_id: str)` | Same, but looks up the layer by ID from the current project |

### `services/dem_service.py` — DEM Service
Contains `DEMService`. Downloads a DEM GeoTIFF from Google Earth Engine for a given AOI and dataset. Output files are named `AGLgis_<dataset>.tif`.

| Method | Signature | Purpose |
|---|---|---|
| `download_dem` | `(aoi_feature_collection, dataset_name: str)` | Clips the selected EE image to the AOI, downloads it as a GeoTIFF, and returns the temporary file path |

### `services/dem_registry.py` — DEM Registry
Contains `DEMDataset` and `DEMRegistry`. Loads dataset definitions from `assets/dem_catalog.json` and provides lookup and availability-check operations against Google Earth Engine.

| Method | Signature | Purpose |
|---|---|---|
| `list_datasets` | `()` | Returns all registered `DEMDataset` objects |
| `get_dataset` | `(name: str)` | Returns the `DEMDataset` for the given name |
| `get_image` | `(name: str)` | Returns the `ee.Image` for the given dataset |
| `is_available` | `(name: str, region, aoi_bbox=None)` | Checks whether the dataset has EE coverage over the given geometry; pass pre-computed `aoi_bbox` to skip the remote GEE bounds call |

### `services/raster_renderer_utils.py` — Common Raster Rendering Utilities
Contains `RasterRendererUtils`. Provides reusable methods for pseudocolor rendering shared by DEM and SAR modules.

| Method | Signature | Purpose |
|---|---|---|
| `apply_pseudocolor_renderer` | `(layer, band_idx, color_ramp_name, min_val, max_val, num_stops=256)` | Applies pseudocolor rendering with a named color ramp to a raster layer |
| `add_layer_to_project` | `(layer, at_top=True)` | Adds a raster layer to the project at top or bottom of the Layers panel |
| `load_pseudocolor_raster` | `(path, layer_name, band_idx, color_ramp_name, at_top=True)` | Loads and styles a raster with pseudocolor in one call |

### `services/dem_renderer.py` — DEM Renderer
Contains `DEMRenderer`. Delegates to `RasterRendererUtils` for color ramp creation and layer management.

| Method | Signature | Purpose |
|---|---|---|
| `load_dem_to_qgis` | `(path: str, dataset_name: str)` | Loads a DEM GeoTIFF into QGIS with Magma color ramp and adds it to the layer tree |

### `services/dataset_manager.py` — Dataset Manager
Contains `DatasetManager`. Manages dataset availability queries and UI updates for the dataset combobox and info panel.

| Method | Signature | Purpose |
|---|---|---|
| `load_available_datasets` | `(dem_combo, current_aoi, current_aoi_bbox, on_error=None)` | Queries `DEMRegistry` for available datasets and populates the given combobox; executes with a wait cursor |
| `update_dataset_info` | `(dem_combo, dem_info_widget)` | Updates the dataset info panel when a different dataset is selected in the combobox |

### `services/settings_manager.py` — Settings Manager
Contains `SettingsManager`. Handles persistence of user preferences in QGIS settings under the `qgis-AGLgis/` prefix.

| Method | Signature | Purpose |
|---|---|---|
| `save_download_folder` | `(folder_path: str)` | Persists the chosen download folder in `QgsSettings` |
| `load_download_folder` | `()` | Returns the previously saved download folder, or an empty string if not set |

### `services/sar_service.py` — SAR Service
Contains `SARService`. Manages Sentinel-1 SAR data processing with spectral index support.

| Method | Signature | Purpose |
|---|---|---|
| `get_collection` | `(aoi, start_date, end_date, polarization, ...)` | Creates an Earth Engine image collection filtered by AOI, date range, and processing options |
| `add_vvvh_ratio_band` | `(image)` | Computes VV/VH Ratio spectral index |
| `add_rvi_band` | `(image)` | Computes Radar Vegetation Index (4 × VH / (VV + VH)) |
| `add_dprvi_band` | `(image)` | Computes Dual-pol SAR Vegetation Index (VH / (VH + VV)) |
| `get_index_timeseries` | `(collection, aoi, band_name)` | Computes mean values over AOI for the specified spectral index |
| `get_image_for_date` | `(collection, aoi, date, index_band)` | Retrieves a single image for a given date with all 5 bands |
| `download_image` | `(image, aoi, date, output_folder, ...)` | Downloads image as GeoTIFF with embedded band descriptions |

### `services/sar_worker.py` — SAR Background Workers
Contains `SARWorker`, `SARPreviewWorker`, `SARBatchDownloadWorker`. Manages off-UI-thread SAR operations with progress tracking and cancellation.

### `services/sar_renderer.py` — SAR Renderer
Contains `SARRenderer`. Loads SAR GeoTIFFs with flexible render modes: RGB composites or single-band pseudocolor with Viridis palette. Delegates common rendering logic to `RasterRendererUtils`.

---

## Translations

The plugin ships UI strings in 7 languages: English (default), Portuguese (pt\_BR), French (fr), Italian (it), Spanish (es), Hindi (hi), and Chinese Simplified (zh\_CN).

The translation system follows the Qt standard: `.ts` XML source files are compiled to binary `.qm` files that `QTranslator` loads at runtime. The active locale is read from QGIS (`Settings → Options → General → Override system locale`).

### How it works

`aglgis.py` installs a `QTranslator` on plugin load and removes it on unload. Every user-visible string in `view/`, `aglgis_dialog.py`, `controllers/`, and `services/gee_service.py` is wrapped with `_tr()` — a thin helper over `QCoreApplication.translate("AGLgis", text)`.

### Editing translations

Edit the relevant `i18n/aglgis_<locale>.ts` file (standard Qt TS XML — one `<message>` per string, `<source>` matches the English literal, `<translation>` holds the target language text), then recompile.

### Compiling `.ts` → `.qm`

OSGeo4W does not bundle `lrelease`. Use the included Python script instead. Run in the **OSGeo4W Shell**:

```bat
cd C:\OSGeo4W\apps\qgis-ltr\python\plugins\AGLgis
python-qgis-ltr compile_translations.py
```

This writes a `.qm` binary next to each `.ts` file. Reload the plugin in QGIS to pick up changes.

### Adding a new language

1. Create `i18n/aglgis_<locale>.ts` (copy an existing file, update `language=` attribute and all `<translation>` entries).
2. Add the locale to the mapping in `aglgis.py` if its 2-char prefix differs from the file suffix (e.g. `'pt': 'pt_BR'`).
3. Run `compile_translations.py`.

---

## Adding a New Feature

1. **UI changes** — add widgets in the appropriate page module (`view/auth.py`, `view/download_dem.py`, etc.). Attach them to `dialog` so controllers and `aglgis.py` can reach them. Add shared styles to `view/styles.py`.
2. **Business logic** — add a method to the relevant service (or create a new service file under `services/`).
3. **Controller logic** — add the event handler to the relevant controller (`controllers/auth_ctrl.py`, `controllers/dem_ctrl.py`), or create a new one for a new page.
4. **Wire them up** — in `aglgis.py`, connect the new widget's signal to the controller method.
5. **Translations** — wrap every new user-visible string with `_tr()`. Add a matching `<message>` entry to each `i18n/aglgis_<locale>.ts` file, then run `compile_translations.py`.

> Keep the dialog ignorant of the GEE SDK. Keep the service ignorant of Qt widgets.

---

## For LLMs and AI Agents

If you are an AI assistant working on this codebase, read this before making changes.

**Layer boundaries — never cross these:**
- The UI (`aglgis_dialog.py` and `view/`) must not import `ee` or any service directly.
- Services (`services/`) must not import Qt widgets or reference QGIS APIs.
- Controllers (`controllers/`) receive the dialog as a constructor argument but must not import `view/` modules directly.
- `aglgis.py` is the only file allowed to wire UI signals to controller methods.

**Where things live:**
- New widgets on the auth page → `view/auth.py` (`setup_auth_page`)
- New widgets on the SAR/radar page → `view/radar.py` (`setup_radar_page`)
- New widgets on the AOI/download page → `view/download_dem.py` (`setup_download_dem_page`)
- Sidebar navigation changes (buttons, icons, expand/collapse behaviour) → `view/sidebar.py`
- New shared stylesheet constants → `view/styles.py`
- New signal connections → `aglgis.py` (inside `_finish_init()`)
- Auth page event handlers → `controllers/auth_ctrl.py`
- DEM page event handlers and orchestration → `controllers/dem_ctrl.py`
- SAR page event handlers and orchestration → `controllers/sar_ctrl.py`
- New pseudocolor rendering logic (shared by DEM and SAR) → `services/raster_renderer_utils.py`
- DEM-specific rendering → `services/dem_renderer.py`
- SAR-specific rendering → `services/sar_renderer.py`
- SAR data processing and spectral indices → `services/sar_service.py`
- SAR background workers (preview, batch download) → `services/sar_worker.py`
- New dataset management logic → `services/dataset_manager.py`
- New settings persistence logic → `services/settings_manager.py`
- New GEE logic → `services/gee_service.py`
- New AOI/geometry logic → `services/aoi_service.py`
- New DEM download logic → `services/dem_service.py`
- New DEM dataset entries → `assets/dem_catalog.json`
- New unrelated service → new file under `services/`, exported from `services/__init__.py`

---

## Development Setup

This plugin supports **QGIS 3.x LTR** and **QGIS 4.0+**.

**Clone the repository**

Clone directly into the QGIS plugins folder so QGIS can discover it:

```bash
# Windows QGIS 3.x
cd %APPDATA%\QGIS\QGIS3\profiles\default\python\plugins

# Windows QGIS 4.0+
cd %APPDATA%\QGIS\profiles\default\python\plugins

# Linux QGIS 3.x
cd ~/.local/share/QGIS/QGIS3/profiles/default/python/plugins

# Linux QGIS 4.0+
cd ~/.local/share/QGIS/profiles/default/python/plugins

git clone https://github.com/caioarantes/aglgis AGLgis
```

**Build and package**

Run `build_plugin.py` from the **OSGeo4W Shell** to do a full release build — clean extlibs, reinstall dependencies, compile translations, and produce a distributable zip:

```bat
cd C:\OSGeo4W\apps\qgis-ltr\python\plugins\AGLgis
python-qgis-ltr build_plugin.py
```

Output: `dist/AGLgis.zip`

To vendor only the Python dependencies without building the zip:

```bat
python-qgis-ltr -m pip install -r requirements.txt --target extlibs --upgrade --no-compile
```

**Compile translations**

After editing any `.ts` file, recompile in the **OSGeo4W Shell** (OSGeo4W does not bundle `lrelease`; use the included script instead):

```bat
cd C:\OSGeo4W\apps\qgis-ltr\python\plugins\AGLgis
python-qgis-ltr compile_translations.py
```

**Hot-reload during development**

Install the [Plugin Reloader](https://plugins.qgis.org/plugins/plugin_reloader/) QGIS plugin to reload AGLgis without restarting QGIS after each code change.
