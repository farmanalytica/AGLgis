# -*- coding: utf-8 -*-
"""
Radar (SAR) data page for the AGLgis dialog.

Two-tab layout: Inputs (parameters) → Results (output).
Signal connections will be wired externally by ``aglgis.py`` once the
service layer is in place.
"""

from qgis.core import QgsMapLayerProxyModel
from qgis.gui import QgsMapLayerComboBox
from qgis.PyQt.QtCore import Qt, QCoreApplication
from qgis.PyQt.QtWebKitWidgets import QWebView
from qgis.PyQt.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
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


def _field_label(text):
    lbl = QLabel(text)
    lbl.setStyleSheet(
        "color: #9e9e9e; font-size: 10px; font-weight: bold; letter-spacing: 1px;"
        " background: transparent; border: none;"
    )
    return lbl


def _build_inputs_tab(dialog, parent):
    lay = QVBoxLayout(parent)
    lay.setContentsMargins(20, 14, 20, 10)
    lay.setSpacing(10)

    # AOI layer
    lay.addWidget(_field_label(_tr("AOI LAYER")))
    dialog.sar_layer_combo = QgsMapLayerComboBox()
    dialog.sar_layer_combo.setFilters(QgsMapLayerProxyModel.VectorLayer)
    dialog.sar_layer_combo.setFixedHeight(28)
    dialog.sar_layer_combo.setAllowEmptyLayer(True)
    lay.addWidget(dialog.sar_layer_combo)

    # Date row
    date_row = QHBoxLayout()
    date_row.setSpacing(12)
    date_row.setContentsMargins(0, 0, 0, 0)

    start_col = QVBoxLayout()
    start_col.setSpacing(4)
    start_col.addWidget(_field_label(_tr("START DATE")))
    dialog.sar_date_start = QLineEdit()
    dialog.sar_date_start.setPlaceholderText("YYYY-MM-DD")
    dialog.sar_date_start.setFixedHeight(28)
    start_col.addWidget(dialog.sar_date_start)
    date_row.addLayout(start_col)

    end_col = QVBoxLayout()
    end_col.setSpacing(4)
    end_col.addWidget(_field_label(_tr("END DATE")))
    dialog.sar_date_end = QLineEdit()
    dialog.sar_date_end.setPlaceholderText("YYYY-MM-DD")
    dialog.sar_date_end.setFixedHeight(28)
    end_col.addWidget(dialog.sar_date_end)
    date_row.addLayout(end_col)

    lay.addLayout(date_row)

    # Polarization + Output format row
    pol_fmt_row = QHBoxLayout()
    pol_fmt_row.setSpacing(12)
    pol_fmt_row.setContentsMargins(0, 0, 0, 0)

    pol_col = QVBoxLayout()
    pol_col.setSpacing(4)
    pol_col.addWidget(_field_label(_tr("POLARIZATION")))
    dialog.sar_pol_combo = QComboBox()
    dialog.sar_pol_combo.addItems(["VV", "VH", "VVVH"])
    dialog.sar_pol_combo.setCurrentText("VVVH")
    dialog.sar_pol_combo.setFixedHeight(28)
    pol_col.addWidget(dialog.sar_pol_combo)
    pol_fmt_row.addLayout(pol_col)

    fmt_col = QVBoxLayout()
    fmt_col.setSpacing(4)
    fmt_col.addWidget(_field_label(_tr("OUTPUT FORMAT")))
    dialog.sar_format_combo = QComboBox()
    dialog.sar_format_combo.addItems(["DB", "LINEAR"])
    dialog.sar_format_combo.setFixedHeight(28)
    fmt_col.addWidget(dialog.sar_format_combo)
    pol_fmt_row.addLayout(fmt_col)

    lay.addLayout(pol_fmt_row)

    # Processing options
    lay.addWidget(_field_label(_tr("PROCESSING OPTIONS")))
    dialog.sar_chk_border_noise = QCheckBox(_tr("Border noise correction"))
    dialog.sar_chk_border_noise.setChecked(True)
    dialog.sar_chk_terrain = QCheckBox(_tr("Terrain flattening"))
    dialog.sar_chk_terrain.setChecked(True)
    dialog.sar_chk_speckle = QCheckBox(_tr("Speckle filtering"))
    dialog.sar_chk_speckle.setChecked(True)
    for chk in (dialog.sar_chk_border_noise, dialog.sar_chk_terrain, dialog.sar_chk_speckle):
        chk.setStyleSheet("color: #212121; font-size: 12px; background: transparent;")
        lay.addWidget(chk)

    lay.addStretch(1)


def _build_results_tab(dialog, parent):
    lay = QVBoxLayout(parent)
    lay.setContentsMargins(20, 14, 20, 10)
    lay.setSpacing(8)

    # Plot
    dialog.sar_web_view = QWebView()
    dialog.sar_web_view.setStyleSheet(
        "border: 1px solid #e0e0e0; border-radius: 6px; background: #f8f9fa;"
    )
    lay.addWidget(dialog.sar_web_view, 1)

    # Plot action buttons
    plot_row = QHBoxLayout()
    plot_row.setSpacing(8)
    plot_row.setContentsMargins(0, 0, 0, 0)
    dialog.sar_btn_open_browser = QPushButton(_tr("Open in Browser"))
    dialog.sar_btn_open_browser.setFixedHeight(28)
    dialog.sar_btn_open_browser.setStyleSheet(STYLE_BTN_SECONDARY)
    dialog.sar_btn_download_csv = QPushButton(_tr("Download as CSV"))
    dialog.sar_btn_download_csv.setFixedHeight(28)
    dialog.sar_btn_download_csv.setStyleSheet(STYLE_BTN_SECONDARY)
    plot_row.addWidget(dialog.sar_btn_open_browser)
    plot_row.addWidget(dialog.sar_btn_download_csv)
    plot_row.addStretch(1)
    lay.addLayout(plot_row)

    # Date selection row
    date_row = QHBoxLayout()
    date_row.setSpacing(8)
    date_row.setContentsMargins(0, 0, 0, 0)
    date_lbl = QLabel(_tr("Date"))
    date_lbl.setStyleSheet("color: #616161; font-size: 12px; background: transparent; border: none;")
    date_row.addWidget(date_lbl)
    dialog.sar_result_date_combo = QComboBox()
    dialog.sar_result_date_combo.setFixedHeight(28)
    dialog.sar_result_date_combo.setMinimumWidth(130)
    date_row.addWidget(dialog.sar_result_date_combo)
    date_row.addStretch(1)
    dialog.sar_btn_preview = QPushButton(_tr("Preview"))
    dialog.sar_btn_preview.setFixedHeight(28)
    dialog.sar_btn_preview.setStyleSheet(STYLE_BTN_PRIMARY)
    dialog.sar_btn_download_preview = QPushButton(_tr("Download & Preview"))
    dialog.sar_btn_download_preview.setFixedHeight(28)
    dialog.sar_btn_download_preview.setStyleSheet(STYLE_BTN_SECONDARY)
    date_row.addWidget(dialog.sar_btn_preview)
    date_row.addWidget(dialog.sar_btn_download_preview)
    lay.addLayout(date_row)

    # Batch download
    dialog.sar_btn_batch_download = QPushButton(_tr("Batch Download (All Dates)"))
    dialog.sar_btn_batch_download.setFixedHeight(28)
    dialog.sar_btn_batch_download.setStyleSheet(STYLE_BTN_SECONDARY)
    lay.addWidget(dialog.sar_btn_batch_download)


def setup_radar_page(dialog, page):
    """
    Populate the Radar (SAR) page with a two-tab layout.

    Exposes on dialog:
      sar_layer_combo, sar_date_start, sar_date_end,
      sar_pol_combo, sar_format_combo,
      sar_chk_border_noise, sar_chk_terrain, sar_chk_speckle,
      sar_web_view, sar_btn_open_browser, sar_btn_download_csv,
      sar_result_date_combo, sar_btn_preview, sar_btn_download_preview,
      sar_btn_batch_download,
      sar_stack, sar_btn_back, sar_btn_next, sar_step_lbl
    """
    page.setStyleSheet("background-color: #f5f5f5;")

    outer = QVBoxLayout(page)
    outer.setContentsMargins(24, 14, 24, 14)
    outer.setSpacing(0)

    # Main card
    card = QFrame()
    card.setObjectName("sarCard")
    card.setStyleSheet("""
        QFrame#sarCard {
            background-color: #ffffff;
            border: 1px solid #e0e0e0;
            border-radius: 12px;
        }
        QComboBox, QgsMapLayerComboBox {
            combobox-popup: 0;
            background-color: #ffffff;
            color: #212121;
            border: 1px solid #d0d0d0;
            border-radius: 6px;
            padding: 4px 8px;
            font-size: 12px;
        }
        QComboBox:focus, QgsMapLayerComboBox:focus {
            border: 1.5px solid #1b6b39;
        }
        QComboBox QAbstractItemView {
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
        QLabel { background: transparent; border: none; }
    """)
    card_lay = QVBoxLayout(card)
    card_lay.setContentsMargins(0, 0, 0, 0)
    card_lay.setSpacing(0)

    # -- Tab bar
    tab_bar = QFrame()
    tab_bar.setObjectName("sarTabBar")
    tab_bar.setFixedHeight(40)
    tab_bar.setStyleSheet("""
        QFrame#sarTabBar {
            background-color: #f8f9fa;
            border-bottom: 1px solid #e0e0e0;
            border-top-left-radius: 12px;
            border-top-right-radius: 12px;
        }
    """)
    tab_bar_lay = QHBoxLayout(tab_bar)
    tab_bar_lay.setContentsMargins(16, 0, 16, 0)
    tab_bar_lay.setSpacing(4)

    btn_tab_inputs = QPushButton(_tr("Inputs"))
    btn_tab_inputs.setFixedHeight(40)
    btn_tab_inputs.setCursor(Qt.CursorShape.PointingHandCursor)

    btn_tab_results = QPushButton(_tr("Results"))
    btn_tab_results.setFixedHeight(40)
    btn_tab_results.setCursor(Qt.CursorShape.PointingHandCursor)

    tab_bar_lay.addWidget(btn_tab_inputs)
    tab_bar_lay.addWidget(btn_tab_results)
    tab_bar_lay.addStretch(1)

    card_lay.addWidget(tab_bar)

    # -- Stacked content
    stack = QStackedWidget()
    stack.setStyleSheet("QStackedWidget { background: transparent; border: none; }")

    inputs_page = QWidget()
    _build_inputs_tab(dialog, inputs_page)
    stack.addWidget(inputs_page)

    results_page = QWidget()
    _build_results_tab(dialog, results_page)
    stack.addWidget(results_page)

    card_lay.addWidget(stack, 1)
    dialog.sar_stack = stack

    # -- Bottom nav bar
    nav_bar = QFrame()
    nav_bar.setObjectName("sarNavBar")
    nav_bar.setFixedHeight(46)
    nav_bar.setStyleSheet("""
        QFrame#sarNavBar {
            background-color: #f8f9fa;
            border-top: 1px solid #e0e0e0;
            border-bottom-left-radius: 12px;
            border-bottom-right-radius: 12px;
        }
    """)
    nav_lay = QHBoxLayout(nav_bar)
    nav_lay.setContentsMargins(16, 0, 16, 0)
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

    btn_next = QPushButton(_tr("Run"))
    btn_next.setFixedSize(80, 30)
    btn_next.setStyleSheet(STYLE_BTN_PRIMARY)

    nav_lay.addWidget(btn_next)
    card_lay.addWidget(nav_bar)

    dialog.sar_btn_back = btn_back
    dialog.sar_btn_next = btn_next
    dialog.sar_step_lbl = step_lbl

    outer.addWidget(card)

    # -- Tab switching logic (self-contained, no service dependencies)
    def _set_tab(index):
        stack.setCurrentIndex(index)
        btn_back.setEnabled(index > 0)
        step_lbl.setText(f"Step {index + 1} of 2")
        btn_next.setVisible(index == 0)
        btn_tab_inputs.setStyleSheet(_TAB_ACTIVE if index == 0 else _TAB_INACTIVE)
        btn_tab_results.setStyleSheet(_TAB_ACTIVE if index == 1 else _TAB_INACTIVE)

    btn_tab_inputs.clicked.connect(lambda: _set_tab(0))
    btn_tab_results.clicked.connect(lambda: _set_tab(1))
    btn_next.clicked.connect(lambda: _set_tab(stack.currentIndex() + 1)
                             if stack.currentIndex() < stack.count() - 1 else None)
    btn_back.clicked.connect(lambda: _set_tab(stack.currentIndex() - 1)
                             if stack.currentIndex() > 0 else None)

    _set_tab(0)
