# -*- coding: utf-8 -*-
"""
Radar (SAR) data page for the AGLgis dialog.

Two-tab layout: Inputs (parameters) → Results (output).
Signal connections will be wired externally by ``aglgis.py`` once the
service layer is in place.
"""

import os

from qgis.core import QgsMapLayerProxyModel, QgsSettings
from qgis.gui import QgsMapLayerComboBox
from qgis.PyQt.QtCore import (
    Qt,
    QCoreApplication,
    QDate,
    QPoint,
    QRect,
    QSize,
    QUrl,
)
from qgis.PyQt.QtWebKitWidgets import QWebView
from qgis.PyQt.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLayout,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .styles import STYLE_BTN_PRIMARY, STYLE_BTN_SECONDARY


def _tr(text):
    return QCoreApplication.translate("AGLgis", text)


_TAB_ACTIVE = """
QPushButton {
    background-color: transparent;
    color: #1b6b39;
    border: none;
    border-bottom: 2px solid #1b6b39;
    font-size: 13px;
    font-weight: bold;
    padding: 0 4px 2px 4px;
    border-radius: 0;
}
"""

_TAB_INACTIVE = """
QPushButton {
    background-color: transparent;
    color: #9e9e9e;
    border: none;
    border-bottom: 2px solid transparent;
    font-size: 13px;
    font-weight: normal;
    padding: 0 4px 2px 4px;
    border-radius: 0;
}
QPushButton:hover {
    color: #616161;
    border-bottom-color: #d0d0d0;
}
"""


_POPUP_VIEW_STYLE = (
    "background-color: #ffffff; color: #212121;"
    " selection-background-color: #e8f5e9; selection-color: #1a1a1a;"
)

_CALENDAR_STYLE = """
QCalendarWidget QWidget {
    background-color: #ffffff;
    color: #212121;
    alternate-background-color: #f5f5f5;
}
QCalendarWidget QAbstractItemView:enabled {
    background-color: #ffffff;
    color: #212121;
    selection-background-color: #1b6b39;
    selection-color: #ffffff;
}
QCalendarWidget QAbstractItemView:disabled {
    color: #bdbdbd;
}
QCalendarWidget QWidget#qt_calendar_navigationbar {
    background-color: #f8f9fa;
    border-bottom: 1px solid #e0e0e0;
    padding: 2px;
}
QCalendarWidget QToolButton {
    background-color: transparent;
    color: #212121;
    border: none;
    padding: 2px 6px;
    font-size: 12px;
    font-weight: bold;
}
QCalendarWidget QToolButton:hover {
    background-color: #e8f5e9;
    border-radius: 4px;
}
QCalendarWidget QSpinBox {
    background-color: #ffffff;
    color: #212121;
    border: 1px solid #d0d0d0;
    border-radius: 4px;
    padding: 2px 4px;
    font-size: 11px;
}
QCalendarWidget QMenu {
    background-color: #ffffff;
    color: #212121;
    border: 1px solid #e0e0e0;
}
"""


def _field_label(text):
    lbl = QLabel(text)
    lbl.setStyleSheet(
        "color: #8f9691; font-size: 10px; font-weight: bold; letter-spacing: 1px;"
        " background: transparent; border: none;"
    )
    return lbl


def _prepare_field(widget, height=30):
    widget.setFixedHeight(height)
    widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    return widget


class FlowLayout(QLayout):
    """Left-to-right layout that wraps items onto new lines when the available
    width runs out. Widening the window packs more controls per line, so fewer
    lines are needed and more options stay visible without scrolling."""

    def __init__(self, parent=None, margin=0, spacing=8):
        super().__init__(parent)
        if parent is not None:
            self.setContentsMargins(margin, margin, margin, margin)
        self.setSpacing(spacing)
        self._items = []

    def __del__(self):
        while self.count():
            self.takeAt(0)

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._do_layout(QRect(0, 0, width, 0), True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do_layout(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        size += QSize(
            margins.left() + margins.right(), margins.top() + margins.bottom()
        )
        return size

    def _do_layout(self, rect, test_only):
        margins = self.contentsMargins()
        effective = rect.adjusted(
            margins.left(), margins.top(), -margins.right(), -margins.bottom()
        )
        x = effective.x()
        y = effective.y()
        line_height = 0
        spacing = self.spacing()
        for item in self._items:
            hint = item.sizeHint()
            next_x = x + hint.width() + spacing
            if next_x - spacing > effective.right() and line_height > 0:
                x = effective.x()
                y = y + line_height + spacing
                next_x = x + hint.width() + spacing
                line_height = 0
            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), hint))
            x = next_x
            line_height = max(line_height, hint.height())
        return y + line_height - rect.y() + margins.bottom()


def _flow(widgets, spacing=8):
    """Wrap ``widgets`` in a container driven by a FlowLayout."""
    container = QWidget()
    container.setStyleSheet("background: transparent;")
    flow = FlowLayout(container, margin=0, spacing=spacing)
    for w in widgets:
        flow.addWidget(w)
    policy = container.sizePolicy()
    policy.setHeightForWidth(True)
    container.setSizePolicy(policy)
    return container


def _group(widgets, spacing=6):
    """Bundle task-related controls into one tight cluster that the flow treats
    as a single item — they stay shoulder-to-shoulder and never wrap apart,
    while the wider gap between clusters signals they're different tasks."""
    box = QWidget()
    box.setStyleSheet("background: transparent;")
    row = QHBoxLayout(box)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(spacing)
    for w in widgets:
        row.addWidget(w)
    return box


def _labeled(text, widget, lbl_width=None):
    """Group a caption label with its control as a single flow item, so they
    never wrap apart from each other."""
    group = QWidget()
    group.setStyleSheet("background: transparent;")
    row = QHBoxLayout(group)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(8)
    lbl = QLabel(text)
    lbl.setStyleSheet(
        "color: #616161; font-size: 12px; background: transparent; border: none;"
    )
    if lbl_width:
        lbl.setFixedWidth(lbl_width)
    row.addWidget(lbl)
    row.addWidget(widget)
    return group


def _caption(text):
    """Small uppercase group caption — a cheap, scannable visual anchor that
    keeps related controls readable as one cluster after the row wraps."""
    lbl = QLabel(text)
    lbl.setStyleSheet(
        "color: #9e9e9e; font-size: 11px; font-weight: bold; letter-spacing: 1px;"
        " background: transparent; border: none;"
    )
    return lbl


def _make_divider():
    divider = QFrame()
    divider.setFrameShape(QFrame.Shape.HLine)
    divider.setStyleSheet("color: #edf0ee; background: transparent;")
    return divider


def _section_panel():
    panel = QFrame()
    panel.setObjectName("sarSectionPanel")
    panel.setStyleSheet("""
        QFrame#sarSectionPanel {
            background-color: #fbfcfb;
            border: 1px solid #e4ebe6;
            border-radius: 8px;
        }
    """)
    return panel


def _build_intro_tab(dialog, parent):
    """Render assets/intro_sar.html directly from the plugin source."""
    outer = QVBoxLayout(parent)
    outer.setContentsMargins(0, 0, 0, 0)
    outer.setSpacing(0)

    view = QWebView()
    view.setStyleSheet("background: #ffffff; border: none;")
    intro_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "assets",
        "intro_sar.html",
    )
    # load() reads the file in place, so relative asset paths resolve from assets/.
    # Pass QGIS UI locale to the page via fragment so it auto-picks the language.
    locale = QgsSettings().value("locale/userLocale", "en_US") or "en_US"
    intro_url = QUrl.fromLocalFile(intro_path)
    intro_url.setFragment("lang=" + locale[:2].lower())
    view.load(intro_url)
    dialog.sar_intro_view = view
    outer.addWidget(view, 1)


def _build_inputs_tab(dialog, parent):
    outer = QVBoxLayout(parent)
    outer.setContentsMargins(0, 0, 0, 0)
    outer.setSpacing(0)

    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

    scroll_w = QWidget()
    scroll_w.setStyleSheet("background: transparent;")
    lay = QVBoxLayout(scroll_w)
    lay.setContentsMargins(6, 16, 6, 14)
    lay.setSpacing(12)

    inputs_panel = _section_panel()
    inputs_lay = QVBoxLayout(inputs_panel)
    inputs_lay.setContentsMargins(16, 14, 16, 14)
    inputs_lay.setSpacing(10)

    inputs_lay.addWidget(_field_label(_tr("AOI LAYER")))

    aoi_row = QWidget()
    aoi_row_lay = QHBoxLayout(aoi_row)
    aoi_row_lay.setContentsMargins(0, 0, 0, 0)
    aoi_row_lay.setSpacing(6)

    dialog.sar_layer_combo = QgsMapLayerComboBox()
    dialog.sar_layer_combo.setFilters(QgsMapLayerProxyModel.VectorLayer)
    _prepare_field(dialog.sar_layer_combo)
    dialog.sar_layer_combo.setAllowEmptyLayer(True)
    dialog.sar_layer_combo.view().setStyleSheet(_POPUP_VIEW_STYLE)
    aoi_row_lay.addWidget(dialog.sar_layer_combo, 1)

    dialog.sar_btn_draw_aoi = QPushButton(_tr("Draw AOI"))
    dialog.sar_btn_draw_aoi.setToolTip(
        _tr("Drag on the map to draw a box (Shift = square, Esc = cancel)")
    )
    dialog.sar_btn_draw_aoi.setFixedHeight(28)
    dialog.sar_btn_draw_aoi.setSizePolicy(
        QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
    )
    dialog.sar_btn_draw_aoi.adjustSize()
    dialog.sar_btn_draw_aoi.setStyleSheet(STYLE_BTN_SECONDARY)
    aoi_row_lay.addWidget(dialog.sar_btn_draw_aoi)

    dialog.sar_btn_hybrid_layer = QPushButton(_tr("Add Google Hybrid Layer"))
    dialog.sar_btn_hybrid_layer.setFixedHeight(28)
    dialog.sar_btn_hybrid_layer.setSizePolicy(
        QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
    )
    dialog.sar_btn_hybrid_layer.adjustSize()
    dialog.sar_btn_hybrid_layer.setStyleSheet(STYLE_BTN_SECONDARY)
    aoi_row_lay.addWidget(dialog.sar_btn_hybrid_layer)

    inputs_lay.addWidget(aoi_row)

    inputs_lay.addSpacing(6)

    fields_grid = QGridLayout()
    fields_grid.setContentsMargins(0, 0, 0, 0)
    fields_grid.setHorizontalSpacing(16)
    fields_grid.setVerticalSpacing(8)
    fields_grid.setColumnStretch(0, 1)
    fields_grid.setColumnStretch(1, 1)

    dialog.sar_date_start = QDateEdit()
    dialog.sar_date_start.setDisplayFormat("yyyy-MM-dd")
    dialog.sar_date_start.setCalendarPopup(True)
    dialog.sar_date_start.setDate(QDate.currentDate().addYears(-1))
    _prepare_field(dialog.sar_date_start)
    dialog.sar_date_end = QDateEdit()
    dialog.sar_date_end.setDisplayFormat("yyyy-MM-dd")
    dialog.sar_date_end.setCalendarPopup(True)
    dialog.sar_date_end.setDate(QDate.currentDate())
    _prepare_field(dialog.sar_date_end)
    for _cal in (
        dialog.sar_date_start.calendarWidget(),
        dialog.sar_date_end.calendarWidget(),
    ):
        if _cal is not None:
            _cal.setStyleSheet(_CALENDAR_STYLE)

    fields_grid.addWidget(_field_label(_tr("START DATE")), 0, 0)
    fields_grid.addWidget(_field_label(_tr("END DATE")), 0, 1)
    fields_grid.addWidget(dialog.sar_date_start, 1, 0)
    fields_grid.addWidget(dialog.sar_date_end, 1, 1)

    dialog.sar_pol_combo = QComboBox()
    dialog.sar_pol_combo.addItems(["VV", "VH", "VVVH"])
    dialog.sar_pol_combo.setCurrentText("VVVH")
    _prepare_field(dialog.sar_pol_combo)
    dialog.sar_pol_combo.view().setStyleSheet(_POPUP_VIEW_STYLE)
    dialog.sar_format_combo = QComboBox()
    dialog.sar_format_combo.addItems(["DB", "LINEAR"])
    _prepare_field(dialog.sar_format_combo)
    dialog.sar_format_combo.view().setStyleSheet(_POPUP_VIEW_STYLE)
    dialog.sar_index_combo = QComboBox()
    dialog.sar_index_combo.addItems(["VV/VH Ratio", "RVI", "DpRVI"])
    dialog.sar_index_combo.setCurrentText("VV/VH Ratio")
    _prepare_field(dialog.sar_index_combo)
    dialog.sar_index_combo.view().setStyleSheet(_POPUP_VIEW_STYLE)

    fields_grid.addWidget(_field_label(_tr("POLARIZATION")), 2, 0)
    fields_grid.addWidget(_field_label(_tr("OUTPUT FORMAT")), 2, 1)
    fields_grid.addWidget(_field_label(_tr("SPECTRAL INDEX")), 4, 0)
    fields_grid.addWidget(dialog.sar_pol_combo, 3, 0)
    fields_grid.addWidget(dialog.sar_format_combo, 3, 1)
    fields_grid.addWidget(dialog.sar_index_combo, 5, 0)
    inputs_lay.addLayout(fields_grid)
    lay.addWidget(inputs_panel)

    # Processing options
    options_panel = _section_panel()
    options_lay = QVBoxLayout(options_panel)
    options_lay.setContentsMargins(16, 12, 16, 14)
    options_lay.setSpacing(10)
    options_lay.addWidget(_field_label(_tr("PROCESSING OPTIONS")))

    options_row = QHBoxLayout()
    options_row.setContentsMargins(0, 0, 0, 0)
    options_row.setSpacing(24)

    dialog.sar_chk_border_noise = QCheckBox(_tr("Border noise correction"))
    dialog.sar_chk_border_noise.setChecked(True)
    dialog.sar_chk_terrain = QCheckBox(_tr("Terrain flattening"))
    dialog.sar_chk_terrain.setChecked(True)
    dialog.sar_chk_speckle = QCheckBox(_tr("Speckle filtering"))
    dialog.sar_chk_speckle.setChecked(True)
    for chk in (
        dialog.sar_chk_border_noise,
        dialog.sar_chk_terrain,
        dialog.sar_chk_speckle,
    ):
        chk.setStyleSheet("""
            QCheckBox {
                color: #212121;
                font-size: 12px;
                background: transparent;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 15px;
                height: 15px;
            }
            QCheckBox::indicator:unchecked {
                background-color: #ffffff;
                border: 1.5px solid #9e9e9e;
                border-radius: 3px;
            }
            QCheckBox::indicator:unchecked:hover {
                border-color: #1b6b39;
            }
        """)
        options_row.addWidget(chk)
    options_row.addStretch(1)
    options_lay.addLayout(options_row)
    lay.addWidget(options_panel)

    lay.addStretch(1)
    scroll.setWidget(scroll_w)
    outer.addWidget(scroll)


def _build_results_tab(dialog, parent):
    outer = QVBoxLayout(parent)
    outer.setContentsMargins(0, 0, 0, 0)
    outer.setSpacing(0)

    # Plot sits above the controls in a draggable vertical splitter: grab the
    # handle to make the plot taller or shorter. Keeps a sane default height
    # instead of the plot eating all the vertical space.
    dialog.sar_results_splitter = QSplitter(Qt.Orientation.Vertical)
    dialog.sar_results_splitter.setChildrenCollapsible(False)
    dialog.sar_results_splitter.setHandleWidth(4)
    dialog.sar_results_splitter.setStyleSheet("""
        QSplitter::handle {
            background: transparent;
            margin: 0px 6px;
            border-top: 2px solid #d6e0d9;
        }
        QSplitter::handle:hover { border-top-color: #1b6b39; }
    """)

    # Plot
    dialog.sar_web_view = QWebView()
    dialog.sar_web_view.setStyleSheet(
        "border: 1px solid #dce6df; border-radius: 8px; background: #ffffff;"
    )
    dialog.sar_web_view.setMinimumHeight(200)
    dialog.sar_results_splitter.addWidget(dialog.sar_web_view)

    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

    scroll_w = QWidget()
    scroll_w.setStyleSheet("background: transparent;")
    lay = QVBoxLayout(scroll_w)
    lay.setContentsMargins(6, 0, 6, 14)
    lay.setSpacing(12)

    controls_panel = _section_panel()
    controls_lay = QVBoxLayout(controls_panel)
    controls_lay.setContentsMargins(16, 14, 16, 14)
    controls_lay.setSpacing(10)

    # ── Time-series exports ───────────────────────────────────────────────
    controls_lay.addWidget(_caption(_tr("TIME SERIES")))
    dialog.sar_btn_open_browser = QPushButton(_tr("Open in Browser"))
    dialog.sar_btn_open_browser.setFixedHeight(30)
    dialog.sar_btn_open_browser.setStyleSheet(STYLE_BTN_SECONDARY)
    dialog.sar_btn_download_csv = QPushButton(_tr("Export CSV"))
    dialog.sar_btn_download_csv.setFixedHeight(30)
    dialog.sar_btn_download_csv.setStyleSheet(STYLE_BTN_SECONDARY)
    dialog.sar_btn_batch_download = QPushButton(_tr("Batch Download (All Dates)"))
    dialog.sar_btn_batch_download.setFixedHeight(30)
    dialog.sar_btn_batch_download.setStyleSheet(STYLE_BTN_SECONDARY)
    controls_lay.addWidget(_flow([
        dialog.sar_btn_open_browser,
        dialog.sar_btn_download_csv,
        dialog.sar_btn_batch_download,
    ]))

    controls_lay.addWidget(_make_divider())

    # ── Single-date image ─────────────────────────────────────────────────
    controls_lay.addWidget(_caption(_tr("SINGLE-DATE IMAGE")))
    dialog.sar_result_date_combo = QComboBox()
    _prepare_field(dialog.sar_result_date_combo, 30)
    dialog.sar_result_date_combo.setFixedWidth(136)
    dialog.sar_btn_filter_dates = QPushButton(_tr("Filter dates"))
    dialog.sar_btn_filter_dates.setFixedHeight(30)
    dialog.sar_btn_filter_dates.setStyleSheet(STYLE_BTN_SECONDARY)

    dialog.sar_render_combo = QComboBox()
    _prepare_field(dialog.sar_render_combo, 30)
    dialog.sar_render_combo.setFixedWidth(240)
    dialog.sar_render_combo.addItems([
        _tr("RGB: VV, VH, VV/VH Ratio"),
        _tr("RGB: VV, RVI, DpRVI"),
        _tr("RGB: VV/VH Ratio, RVI, DpRVI"),
        _tr("Band: VV"),
        _tr("Band: VH"),
        _tr("Band: VV/VH Ratio"),
        _tr("Band: RVI"),
        _tr("Band: DpRVI"),
    ])
    dialog.sar_render_combo.view().setStyleSheet(_POPUP_VIEW_STYLE)

    dialog.sar_btn_preview = QPushButton(_tr("Preview"))
    dialog.sar_btn_preview.setFixedHeight(30)
    dialog.sar_btn_preview.setStyleSheet(STYLE_BTN_PRIMARY)
    dialog.sar_btn_download_preview = QPushButton(
        _tr("Download & Preview").replace("&", "&&")
    )
    dialog.sar_btn_download_preview.setFixedHeight(30)
    dialog.sar_btn_download_preview.setStyleSheet(STYLE_BTN_SECONDARY)

    # Two task clusters: choose-the-date, then render-and-preview. Tight within
    # each cluster, wider gap between them.
    controls_lay.addWidget(_flow([
        _group([
            _labeled(_tr("Date"), dialog.sar_result_date_combo, 34),
            dialog.sar_btn_filter_dates,
        ]),
        _group([
            _labeled(_tr("Render Mode"), dialog.sar_render_combo, 80),
            dialog.sar_btn_preview,
            dialog.sar_btn_download_preview,
        ]),
    ], spacing=18))
    lay.addWidget(controls_panel)

    # ── Synthetic image (composite) ───────────────────────────────────────
    # Reduce the currently selected index over the selected dates into a
    # single composite image, with the same metrics as the Sentinel-2 tool.
    composite_panel = _section_panel()
    composite_lay = QVBoxLayout(composite_panel)
    composite_lay.setContentsMargins(16, 14, 16, 14)
    composite_lay.setSpacing(10)

    composite_title = QLabel(_tr("SYNTHETIC IMAGE (COMPOSITE)"))
    composite_title.setStyleSheet(
        "color: #9e9e9e; font-size: 11px; font-weight: bold; letter-spacing: 1px;"
        " background: transparent; border: none;"
    )
    composite_lay.addWidget(composite_title)

    composite_hint = QLabel(
        _tr("Composite the selected index over the selected dates.")
    )
    composite_hint.setStyleSheet(
        "color: #616161; font-size: 11px; background: transparent; border: none;"
    )
    composite_lay.addWidget(composite_hint)

    # Metric + color-ramp selectors and composite actions — one wrapping row.
    dialog.sar_composite_metric_combo = QComboBox()
    _prepare_field(dialog.sar_composite_metric_combo, 30)
    dialog.sar_composite_metric_combo.setFixedWidth(240)
    dialog.sar_composite_metric_combo.addItems([
        _tr("Mean"),
        _tr("Median"),
        _tr("Min"),
        _tr("Max"),
        _tr("Amplitude"),
        _tr("Standard Deviation"),
        _tr("Sum"),
        _tr("Area Under Curve (AUC)"),
    ])
    dialog.sar_composite_metric_combo.view().setStyleSheet(_POPUP_VIEW_STYLE)

    dialog.sar_composite_ramp_combo = QComboBox()
    _prepare_field(dialog.sar_composite_ramp_combo, 30)
    dialog.sar_composite_ramp_combo.setFixedWidth(240)
    dialog.sar_composite_ramp_combo.addItems([
        "Viridis",
        "Magma",
        "Plasma",
        "Inferno",
        "RdYlGn",
        "Greys",
    ])
    dialog.sar_composite_ramp_combo.view().setStyleSheet(_POPUP_VIEW_STYLE)

    dialog.sar_btn_composite_preview = QPushButton(_tr("Preview Composite"))
    dialog.sar_btn_composite_preview.setFixedHeight(30)
    dialog.sar_btn_composite_preview.setStyleSheet(STYLE_BTN_PRIMARY)
    dialog.sar_btn_composite_download = QPushButton(
        _tr("Download & Preview").replace("&", "&&")
    )
    dialog.sar_btn_composite_download.setFixedHeight(30)
    dialog.sar_btn_composite_download.setStyleSheet(STYLE_BTN_SECONDARY)

    # Configure cluster (metric + ramp) separated from the action cluster.
    composite_lay.addWidget(_flow([
        _group([
            _labeled(_tr("Metric"), dialog.sar_composite_metric_combo, 80),
            _labeled(_tr("Color Ramp"), dialog.sar_composite_ramp_combo, 80),
        ]),
        _group([
            dialog.sar_btn_composite_preview,
            dialog.sar_btn_composite_download,
        ]),
    ], spacing=18))

    lay.addWidget(composite_panel)
    lay.addStretch(1)

    scroll.setWidget(scroll_w)
    dialog.sar_results_splitter.addWidget(scroll)
    # Extra vertical space goes to the plot; the controls pane keeps its size
    # and scrolls if cramped. The plot's minimum height sets the default.
    dialog.sar_results_splitter.setStretchFactor(0, 1)
    dialog.sar_results_splitter.setStretchFactor(1, 0)
    outer.addWidget(dialog.sar_results_splitter)


def setup_radar_page(dialog, page):
    """
    Populate the Radar (SAR) page with a two-tab layout.

    Exposes on dialog:
      sar_layer_combo, sar_date_start, sar_date_end,
      sar_pol_combo, sar_format_combo, sar_index_combo,
      sar_chk_border_noise, sar_chk_terrain, sar_chk_speckle,
      sar_web_view, sar_btn_open_browser, sar_btn_download_csv, sar_btn_filter_dates,
      sar_result_date_combo, sar_btn_preview, sar_btn_download_preview,
      sar_btn_batch_download, sar_render_combo,
      sar_stack, sar_btn_back, sar_btn_next, sar_step_lbl
    """
    page.setObjectName("sarPage")
    page.setStyleSheet("""
        QWidget#sarPage { background-color: #ffffff; }
        QComboBox, QgsMapLayerComboBox {
            combobox-popup: 0;
            background-color: #ffffff;
            color: #212121;
            border: 1px solid #d0d0d0;
            border-radius: 6px;
            padding: 4px 9px;
            font-size: 12px;
        }
        QComboBox:focus, QgsMapLayerComboBox:focus { border: 1.5px solid #1b6b39; }
        QComboBox QAbstractItemView, QgsMapLayerComboBox QAbstractItemView {
            background-color: #ffffff;
            color: #212121;
            border: 1px solid #bdbdbd;
            selection-background-color: #e8f5e9;
            selection-color: #1a1a1a;
            outline: 0;
        }
        QLineEdit {
            background-color: #ffffff;
            color: #212121;
            border: 1px solid #d0d0d0;
            border-radius: 6px;
            padding: 4px 8px;
            font-size: 12px;
        }
        QLineEdit:focus { border: 1.5px solid #1b6b39; }
        QDateEdit {
            background-color: #ffffff;
            color: #212121;
            border: 1px solid #d0d0d0;
            border-radius: 6px;
            padding: 2px 4px 2px 8px;
            font-size: 12px;
        }
        QDateEdit:focus { border: 1.5px solid #1b6b39; }
        QLabel { background: transparent; border: none; }
        QCalendarWidget QWidget {
            background-color: #ffffff;
            color: #212121;
            alternate-background-color: #f5f5f5;
        }
        QCalendarWidget QAbstractItemView {
            background-color: #ffffff;
            color: #212121;
            selection-background-color: #1b6b39;
            selection-color: #ffffff;
        }
        QCalendarWidget QWidget#qt_calendar_navigationbar {
            background-color: #f8f9fa;
            border-bottom: 1px solid #e0e0e0;
        }
        QCalendarWidget QToolButton {
            background-color: transparent;
            color: #212121;
            border: none;
            padding: 2px 6px;
            font-size: 12px;
        }
        QCalendarWidget QToolButton:hover {
            background-color: #e8f5e9;
            border-radius: 4px;
        }
        QCalendarWidget QMenu { background-color: #ffffff; color: #212121; }
        QCalendarWidget QSpinBox {
            background-color: #ffffff;
            color: #212121;
            border: 1px solid #d0d0d0;
            border-radius: 4px;
            padding: 2px 4px;
        }
    """)

    outer = QVBoxLayout(page)
    outer.setContentsMargins(0, 0, 0, 0)
    outer.setSpacing(0)

    # -- Tab bar
    tab_bar = QFrame()
    tab_bar.setObjectName("sarTabBar")
    tab_bar.setFixedHeight(40)
    tab_bar.setStyleSheet("""
        QFrame#sarTabBar {
            background-color: #f8f9fa;
            border-bottom: 1px solid #e0e0e0;
        }
    """)
    tab_bar_lay = QHBoxLayout(tab_bar)
    tab_bar_lay.setContentsMargins(6, 0, 6, 0)
    tab_bar_lay.setSpacing(8)

    btn_tab_intro = QPushButton(_tr("Intro"))
    btn_tab_intro.setFixedHeight(40)
    btn_tab_intro.setCursor(Qt.CursorShape.PointingHandCursor)

    btn_tab_inputs = QPushButton(_tr("Inputs"))
    btn_tab_inputs.setFixedHeight(40)
    btn_tab_inputs.setCursor(Qt.CursorShape.PointingHandCursor)

    btn_tab_results = QPushButton(_tr("Results"))
    btn_tab_results.setFixedHeight(40)
    btn_tab_results.setCursor(Qt.CursorShape.PointingHandCursor)

    tab_bar_lay.addWidget(btn_tab_intro)
    tab_bar_lay.addWidget(btn_tab_inputs)
    tab_bar_lay.addWidget(btn_tab_results)
    tab_bar_lay.addStretch(1)

    outer.addWidget(tab_bar)

    # -- Stacked content
    stack = QStackedWidget()
    stack.setStyleSheet("QStackedWidget { background: transparent; border: none; }")

    intro_page = QWidget()
    _build_intro_tab(dialog, intro_page)
    stack.addWidget(intro_page)

    inputs_page = QWidget()
    _build_inputs_tab(dialog, inputs_page)
    stack.addWidget(inputs_page)

    results_page = QWidget()
    _build_results_tab(dialog, results_page)
    stack.addWidget(results_page)

    outer.addWidget(stack, 1)
    dialog.sar_stack = stack

    # -- Bottom nav bar
    nav_bar = QFrame()
    nav_bar.setObjectName("sarNavBar")
    nav_bar.setFixedHeight(46)
    nav_bar.setStyleSheet("""
        QFrame#sarNavBar {
            background-color: #f8f9fa;
            border-top: 1px solid #e0e0e0;
        }
    """)
    nav_lay = QHBoxLayout(nav_bar)
    nav_lay.setContentsMargins(6, 0, 6, 0)
    nav_lay.setSpacing(8)

    btn_back = QPushButton(_tr("Back"))
    btn_back.setFixedSize(80, 30)
    btn_back.setStyleSheet(STYLE_BTN_SECONDARY)

    nav_lay.addWidget(btn_back)
    nav_lay.addStretch(1)

    step_lbl = QLabel()
    step_lbl.setStyleSheet("color: #bdbdbd; font-size: 11px; background: transparent;")
    nav_lay.addWidget(step_lbl)

    nav_lay.addStretch(1)

    # Forward control on the Intro tab — pure navigation to the Inputs step.
    btn_intro_next = QPushButton(_tr("Next"))
    btn_intro_next.setFixedSize(80, 30)
    btn_intro_next.setStyleSheet(STYLE_BTN_PRIMARY)
    nav_lay.addWidget(btn_intro_next)

    btn_next = QPushButton(_tr("Run"))
    btn_next.setFixedSize(80, 30)
    btn_next.setStyleSheet(STYLE_BTN_PRIMARY)
    nav_lay.addWidget(btn_next)
    outer.addWidget(nav_bar)

    dialog.sar_btn_back = btn_back
    dialog.sar_btn_next = btn_next
    dialog.sar_step_lbl = step_lbl

    # -- Tab switching logic (self-contained, no service dependencies)
    # Three-step flow: 0 = Intro (docs), 1 = Inputs, 2 = Results.
    def _set_tab(index):
        stack.setCurrentIndex(index)
        btn_back.setEnabled(index > 0)
        step_lbl.setText(f"Step {index + 1} of 3")
        btn_intro_next.setVisible(index == 0)  # "Next" advances Intro -> Inputs
        btn_next.setVisible(index == 1)  # "Run" lives on the Inputs tab only
        btn_tab_intro.setStyleSheet(_TAB_ACTIVE if index == 0 else _TAB_INACTIVE)
        btn_tab_inputs.setStyleSheet(_TAB_ACTIVE if index == 1 else _TAB_INACTIVE)
        btn_tab_results.setStyleSheet(_TAB_ACTIVE if index == 2 else _TAB_INACTIVE)

    # Exposed so the controller can advance to Results only on a successful run.
    dialog.sar_set_tab = _set_tab

    btn_tab_intro.clicked.connect(lambda: _set_tab(0))
    btn_tab_inputs.clicked.connect(lambda: _set_tab(1))
    btn_tab_results.clicked.connect(lambda: _set_tab(2))
    btn_intro_next.clicked.connect(lambda: _set_tab(1))
    btn_back.clicked.connect(
        lambda: _set_tab(stack.currentIndex() - 1) if stack.currentIndex() > 0 else None
    )

    _set_tab(0)
