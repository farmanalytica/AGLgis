# SAR Results Tab - Filter Dates Feature Implementation

## Summary

Implemented a **non-modal, modern date filter dialog** for the SAR Results tab with **real-time chart updates** and improved UX. The feature allows users to:
- **Keep the dialog open while viewing the chart** — non-modal design lets you move the dialog around
- Uncheck dates and see the chart update **instantly** without clicking Apply
- Persistent filtering — chart updates persist as you adjust selections
- **Months expanded by default** — all dates visible immediately
- **Card-based layout** — each month shown in a styled card with selection count (e.g., "12/15")
- **Visual hierarchy** — year headers (bold, colored), month cards with subtle styling
- **Bulk operations** — Select All / Deselect All buttons
- **Cancel to revert** — closing with Cancel reverts the chart to its previous state

## Files Modified/Created

### New Files
- **`view/sar_date_filter_dialog.py`** (new)
  - `SARDateFilterDialog` class - a QDialog with hierarchical year→month→date checkboxes
  - `applied` signal emits `list[str]` of selected dates when Apply/Ok is clicked
  - Supports cascading selection (year checkbox → all months/dates; month checkbox → all dates)
  - Collapsible month sections with ▶/▼ toggle buttons
  - Select All / Deselect All convenience buttons

### Modified Files

#### `controllers/sar_ctrl.py`
- Added `self._active_dates = None` in `__init__()` to track active filter state
- Reset `self._active_dates = None` in `_on_sar_done()` when new SAR data is loaded
- Updated `_render_timeseries()` to filter dataframe before rendering chart:
  ```python
  if self._active_dates is not None:
      df = df[df["dates"].isin(self._active_dates)]
  ```
- Added `handle_filter_dates()` - opens the filter dialog
- Added `_on_filter_applied(selected_dates)` - updates filter state and re-renders chart

#### `aglgis.py`
- Wired up button signal in main dialog setup (line 196-198):
  ```python
  self.dlg.sar_btn_filter_dates.clicked.connect(
      self.sar_ctrl.handle_filter_dates
  )
  ```

## UI/UX Flow

1. User runs SAR analysis → Results tab shows chart with all dates
2. User clicks "Filter dates" button
3. **Non-modal dialog opens** (floating, can be repositioned):
   - Year headers in green, bold text (2024, 2025, etc.)
   - **All months are expanded by default** — all dates visible immediately
   - Each month in a styled card showing "(selected/total)" count
   - Individual date checkboxes clearly organized
4. User can **move the dialog to the side** and see the chart behind it
5. User unchecks date(s) → **chart updates immediately** while dialog remains open
   - Month count updates in real-time as selections change (e.g., "12/15" → "11/15")
6. User can continue adjusting filters and watch chart change in real-time
7. **Select All / Deselect All buttons** for quick bulk operations
8. User clicks **Ok** → dialog closes, **filter persists**, chart shows filtered data
9. User clicks **Cancel** → dialog closes, **chart reverts to the filter state before dialog was opened**
10. If user clicks "Filter dates" again, dialog opens with previous selections preserved
11. If user re-runs SAR → filter resets to show all dates

## UI/UX Design

### Window Size & Layout
- **Dialog size:** 500×620 px (improved from 400×480)
- **Minimum size:** 480×450 px for responsiveness
- Better proportions for scrollable content vs. button area

### Visual Hierarchy
- **Year headers**: Bold, 11pt font, green color (#1b6b39) for visual emphasis
- **Month cards**: Styled frames with light background (#fafafa), subtle border
- **Selection counts**: Each month shows "(selected/total)" count in gray (e.g., "12/15")
- **Checkbox text**: Hierarchical sizing (11px for years, 11px for months, 10px for dates)

### Layout & Organization
- **Months expanded by default** — all dates visible immediately, no need to click toggles
- **Card-based design** — each month in its own card for clarity
- **Proper indentation** — visual grouping of dates under months
- **Consistent spacing** — 12px main margins, 8px month spacing, 6px date spacing

### Styling Details
- Border: 1px light gray (#e0e0e0) on scroll area
- Month cards: Light background (#fafafa) with subtle border (#e8e8e8)
- Text colors: #1b6b39 (year headers), #333333 (month names), #555555 (dates), #999999 (counts)
- Checkbox styling: Color and font-size per hierarchy level
- Select All / Deselect All buttons: Max width 120px for compact button bar

### Dynamic Count Updates
- Each time a date is checked/unchecked, the month's count updates in real-time
- Selecting/deselecting a month updates all its dates and the count
- Bulk operations (Select All / Deselect All) update all counts efficiently

## Implementation Details

### State Tracking
- `self._active_dates: list[str] | None`
  - `None` = no filter (all dates visible)
  - `list[str]` = list of `"YYYY-MM-DD"` strings to display
- Filter state persists across Apply clicks; resets on new SAR run

### Date Grouping
Uses `pandas.groupby()` on `datetime.year` and `datetime.month` to build the hierarchy.

### Chart Updates
The `_render_timeseries()` method handles both filtered and unfiltered cases:
- Filtered: renders only selected dates
- Unfiltered: renders all dates (same as before)

### Dialog Behavior
- **Non-modal**: Dialog floats on top but doesn't block interaction with main window. User can move it to see the chart while filtering.
- **Checkbox interactions**: Each unchecked/checked date triggers immediate chart update
- **Select All / Deselect All**: convenience bulk operations; chart updates immediately
- **Ok** button: closes dialog, **keeps the current filter active**
- **Cancel** button: closes dialog, **emits the previous filter state to revert the chart**
- **Clicking "Filter dates" again**: If dialog is already open, it raises to front; if closed, it reopens with previous selections

## Testing Checklist

### Manual Testing (in QGIS)
1. Open QGIS with AGLgis plugin
2. Go to **SAR** → **Inputs** tab
3. Select an AOI layer and date range spanning ≥6 acquisition dates
4. Click **Run** to fetch SAR data
5. Switch to **Results** tab (chart displays all dates)

#### Test the Filter Dialog
6. Click **"Filter dates"** button
   - ✓ Dialog opens (400×520 px)
   - ✓ Title: "Date Selection for Time Series"
   - ✓ Shows year sections with "Select All in YYYY" checkboxes
   - ✓ Years are expandable (indented)

#### Test Hierarchical Selection
7. Under a year, click ▶ button next to a month (e.g., "2024-01")
   - ✓ Month expands showing individual dates
   - ✓ Arrow changes to ▼
   - ✓ Month has "Select All in 2024-01" checkbox
   - ✓ Individual date checkboxes show (e.g., "2024-01-15")

#### Test Non-Modal Behavior
8. The dialog is floating and doesn't block the main window
   - ✓ Can move dialog around by dragging title bar
   - ✓ Chart is visible behind/beside the dialog
   - ✓ Can interact with other parts of the UI while dialog is open

#### Test Immediate Updates
9. Uncheck 2-3 individual dates (without clicking anything)
   - ✓ Chart updates **instantly** as you uncheck
   - ✓ Chart shows fewer data points immediately
   - ✓ Dialog stays open
   - ✓ You can see the chart change while adjusting filters

#### Test Cascading Selection
10. Click a year checkbox
    - ✓ All dates in that year toggle
    - ✓ Chart updates immediately
    - ✓ All month checkboxes in that year toggle

11. Uncheck a month checkbox
    - ✓ All dates in that month uncheck
    - ✓ Chart updates immediately

#### Test Convenience Buttons
12. Click **Deselect All**
    - ✓ All checkboxes uncheck at all levels
    - ✓ Chart shows empty/no data immediately

13. Click **Select All**
    - ✓ All checkboxes check
    - ✓ Chart returns to full dataset immediately

#### Test Dialog Closure and Reopen
14. Make changes (chart updates in real-time) and click **Ok**
    - ✓ Dialog closes
    - ✓ Filter persists (chart shows filtered data)

15. Click **"Filter dates"** again
    - ✓ Dialog reopens in same position
    - ✓ Previously selected dates remain checked (state preserved)

16. Click **Cancel** after making new changes
    - ✓ Dialog closes
    - ✓ **Chart reverts to the filter state from step 14** (before dialog was reopened)

#### Test Multiple Dialog Opens
17. Click "Filter dates" while dialog is already open
    - ✓ Dialog raises to front (doesn't create duplicate)
    - ✓ Dialog is activated/focused

#### Test Filter Reset on New Run
18. Click **"Run"** to re-fetch SAR data
    - ✓ Filter is cleared
    - ✓ All dates are displayed again
    - ✓ If filter dialog was open, it closes

## Integration Notes

- No changes to existing SAR workflow (Intro, Inputs, Results tabs)
- Filter is purely UI-side (no changes to GEE service calls)
- Placeholder button was fully wired; no breaking changes
- Compatible with existing preview, download, and "Open in Browser" features
- Filter state does not affect the date combo box (single-date selector for previews)
- Chart updates are triggered via `_render_timeseries()` which respects the active filter
- Closing dialog with **Cancel** preserves previous filter state via local state tracking

## Code Quality

- All Python files compile without syntax errors
- Follows existing code style (imports, docstrings, signal naming)
- Uses existing utilities (`_tr()` for translation, existing styling)
- No external dependencies beyond pandas (already used)
- **Non-modal dialog management**: Prevents duplicate dialogs via single reference (`self._filter_dialog`)
- **Proper cleanup**: Dialog reference cleared when dialog closes (via `finished` signal)
- **State tracking**: Stores initial filter state to support Cancel revert
- Handles edge cases:
  - Empty date lists (dialog won't crash)
  - All dates deselected → shows empty chart
  - Multiple "Filter dates" clicks → raises existing dialog instead of creating new one
  - Cancel reverts to pre-dialog state correctly
