# AGLgis — Issues

## Phase 1 — No dependencies (parallel)

### #1 Working directory option on Authentication page
**Goal:** Add a working directory field to the Authentication page. If the user has a saved QGIS project open, default to that project's folder. Otherwise, default to a system temp folder. The user can override the path manually.

**Acceptance:**
- Field is visible on the Auth page before and after authentication.
- When a saved project is open, the field pre-fills with the project's folder on page load.
- When no project is open, the field pre-fills with the system temp folder.
- If the project changes while the plugin is open, the field updates accordingly.
- The chosen path is used by all download/export operations as the output directory.

### #2 AOI layer selector never populated
**Goal:** Populate the AOI selector with the user's loaded QGIS vector layers.
**Acceptance:** On opening the SAR page, the selector lists all vector layers currently loaded in QGIS and updates if layers are added or removed.

### #3 SAR page UI fixes
**Goal:** Fix layout and interaction inconsistencies on the SAR page.

Issues found:
- **Date inputs are plain text fields.** Replace with proper date picker widgets so invalid dates are impossible to enter.
- **"Run" button doubles as tab navigation.** Separate the navigation action from the run action — navigating to Results should not suggest work was done.
- **Results tab has no empty state.** Show a placeholder (e.g. "Run a query to see results") so users know the state.
- **"Back" button is visible but disabled on the first tab.** Hide it instead of disabling it.
- **"Filter dates" is grouped with export buttons.** It is a filter action, not an export — move it near the date selector where it acts.
- **"Batch Download" is full-width while all other actions are inline.** Align it with the rest of the button row style.

**Acceptance:** Each point above is resolved. No regressions on tab switching or the nav bar layout.

---

## Phase 2 — Foundational (blocks everything below)

### #4 No SAR service layer
**Goal:** Implement a service that queries Sentinel-1 imagery from GEE given an AOI and parameters.
**Acceptance:** The plugin can fetch a list of available SAR image dates for a given AOI, date range, and polarization without errors.

---

## Phase 3 — Requires #4 (parallel)

### #5 No signal wiring
**Goal:** Connect all SAR UI buttons to their respective handlers.
**Acceptance:** Every button on the SAR page triggers a response (even a stub). No button is silently dead.

### #6 Results tab has no data source
**Goal:** Populate the date selector in the Results tab after a query runs.
**Acceptance:** After running a query, the date selector lists the available acquisition dates returned by GEE.

---

## Phase 4 — Requires #6

### #7 No time-series plot
**Goal:** Display a time-series plot of SAR backscatter values in the Results tab.
**Acceptance:** After a query, a chart renders in the plot area showing backscatter over time for the selected AOI.

### Filter Dates feature — Requires #4 and #6
**Goal:** Let the user narrow the Results date selector to a specific date range without re-querying GEE.

**UI:** A button opens a compact dialog with a From / To date picker. Confirming applies the filter.

**Backend:** The service caches the full date list from the last query and exposes a filter operation. No new GEE request is made.

**Acceptance:**
- Filtered date selector shows only dates within the chosen range.
- Clearing the filter restores the full date list.
- No GEE call is triggered by filtering.
