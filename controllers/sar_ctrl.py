from ..services.aoi_service import AOIService
from ..services.sar_service import SARService
from ..services.sar_renderer import SARRenderer
from ..services.sar_worker import SARWorker
from ..services.settings_manager import SettingsManager
from ..view.sar_plot import render_chart_html

from qgis.PyQt.QtCore import Qt, QCoreApplication, QUrl
from qgis.PyQt.QtGui import QDesktopServices
from qgis.PyQt.QtWidgets import QApplication
import os
import tempfile
import pandas as pd

try:
    WAIT_CURSOR = Qt.CursorShape.WaitCursor
except AttributeError:
    WAIT_CURSOR = Qt.WaitCursor


def _tr(text):
    return QCoreApplication.translate("AGLgis", text)


_LOADING_HTML = """<!DOCTYPE html><html><head><meta charset="utf-8"><style>
html,body{height:100%;margin:0;font-family:Arial,sans-serif;background:#fff}
.box{position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);text-align:center;color:#616161}
.spinner{width:34px;height:34px;margin:0 auto 12px;border:3px solid #e0e0e0;
border-top-color:#1b6b39;border-radius:50%;animation:spin 0.9s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
</style></head><body><div class="box"><div class="spinner"></div>
<div>Fetching SAR time series…</div></div></body></html>"""


class SARCtrl:
    def __init__(self, dialog, interface=None, gee_service=None):
        self.dlg = dialog
        self.interface = interface
        self.gee_service = gee_service
        self.collection = None
        self.aoi = None
        self.dataframe = None
        self._worker = None

    def _show_auth_required_message(self):
        self.dlg.pop_message(
            _tr(
                "Authentication is required to download SAR data. "
                "Please go to the Auth page and validate your Google Cloud project ID."
            ),
            "warning",
        )

    def handle_sar_run(self):
        if self._worker is not None and self._worker.isRunning():
            return  # a run is already in flight

        if self.gee_service and not self.gee_service.is_authenticated:
            self._show_auth_required_message()
            return

        layer = self.dlg.sar_layer_combo.currentLayer()
        if not layer:
            self.dlg.pop_message("Select an AOI layer.", "warning")
            return

        start_qdate = self.dlg.sar_date_start.date()
        end_qdate = self.dlg.sar_date_end.date()
        if start_qdate >= end_qdate:
            self.dlg.pop_message("End date must be after start date.", "warning")
            return

        # Extract the AOI on the UI thread — QGIS layers are not thread-safe.
        try:
            aoi, _bbox = AOIService.get_aoi_from_layer(
                layer, use_selected_features=False
            )
        except Exception as e:
            self.dlg.pop_message(str(e), "warning")
            return

        self.aoi = aoi
        params = {
            "start_date": start_qdate.toString("yyyy-MM-dd"),
            "end_date": end_qdate.toString("yyyy-MM-dd"),
            "polarization": self.dlg.sar_pol_combo.currentText(),
            "output_format": self.dlg.sar_format_combo.currentText(),
            "border_noise": self.dlg.sar_chk_border_noise.isChecked(),
            "terrain": self.dlg.sar_chk_terrain.isChecked(),
            "speckle": self.dlg.sar_chk_speckle.isChecked(),
        }

        # Show progress without blocking: spinner in the Results tab + busy button.
        self._set_running(True)
        self.dlg.sar_web_view.setHtml(_LOADING_HTML)
        self.dlg.sar_set_tab(2)

        self._worker = SARWorker(aoi, params)
        self._worker.finished_ok.connect(self._on_sar_done)
        self._worker.failed.connect(self._on_sar_failed)
        self._worker.start()

    def _set_running(self, running):
        self.dlg.sar_btn_next.setEnabled(not running)
        self.dlg.sar_btn_next.setText(_tr("Running…") if running else _tr("Run"))

    def _clear_worker(self):
        worker = self._worker
        self._worker = None
        if worker is not None:
            worker.deleteLater()

    def _on_sar_done(self, collection, data):
        self._set_running(False)
        self._clear_worker()

        if not data:
            self.dlg.sar_web_view.setHtml("")
            self.dlg.sar_set_tab(1)
            self.dlg.pop_message(
                "No SAR images found for this date range.", "warning"
            )
            return

        self.collection = collection
        self.dataframe = pd.DataFrame(data)

        self.dlg.sar_result_date_combo.clear()
        self.dlg.sar_result_date_combo.addItems(self.dataframe["dates"].tolist())
        self._render_timeseries()
        self.dlg.sar_set_tab(2)

    def _on_sar_failed(self, message):
        self._set_running(False)
        self._clear_worker()
        self.dlg.sar_web_view.setHtml("")
        self.dlg.sar_set_tab(1)
        self.dlg.pop_message(message, "warning")

    def handle_preview_image(self):
        if self.collection is None or self.aoi is None:
            self.dlg.pop_message("Run SAR processing first.", "warning")
            return

        QApplication.setOverrideCursor(WAIT_CURSOR)
        QApplication.processEvents()

        try:
            selected_date = self.dlg.sar_result_date_combo.currentText()
            selected_image = SARService.get_image_for_date(
                self.collection,
                self.aoi,
                selected_date,
            )
            output_path = SARService.download_image(
                selected_image,
                self.aoi,
                selected_date,
                output_folder=tempfile.gettempdir(),
            )
            SARRenderer.load_sar_to_qgis(output_path, f"Preview_{selected_date}")
            if self.interface:
                self.interface.messageBar().pushMessage(
                    "AGLgis", f"SAR preview '{selected_date}' loaded into QGIS."
                )
        except Exception as e:
            self.dlg.pop_message(str(e), "warning")
        finally:
            QApplication.restoreOverrideCursor()

    def handle_download_preview(self):
        if self.collection is None or self.aoi is None:
            self.dlg.pop_message("Run SAR processing first.", "warning")
            return

        QApplication.setOverrideCursor(WAIT_CURSOR)
        QApplication.processEvents()

        try:
            selected_date = self.dlg.sar_result_date_combo.currentText()
            selected_image = SARService.get_image_for_date(
                self.collection,
                self.aoi,
                selected_date,
            )
            output_folder = SettingsManager.load_download_folder()
            output_path = SARService.download_image(
                selected_image,
                self.aoi,
                selected_date,
                output_folder=output_folder,
            )
            SARRenderer.load_sar_to_qgis(output_path, f"Sentinel1_{selected_date}")
            if self.interface:
                self.interface.messageBar().pushMessage(
                    "AGLgis",
                    f"SAR image '{selected_date}' downloaded and loaded successfully.",
                )
        except Exception as e:
            self.dlg.pop_message(str(e), "warning")
        finally:
            QApplication.restoreOverrideCursor()

    def handle_open_browser(self):
        if self.dataframe is None:
            self.dlg.pop_message("Run SAR processing first.", "warning")
            return
        html = render_chart_html(self.dataframe)
        with tempfile.NamedTemporaryFile(
            suffix=".html", delete=False, mode="w", encoding="utf-8"
        ) as f:
            f.write(html)
            path = f.name
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def _render_timeseries(self):
        html = render_chart_html(self.dataframe)
        # Write to a fresh temp file and load it: QtWebKit renders large embedded
        # Plotly content reliably from a file:// URL, unlike setContent/setHtml.
        fd, path = tempfile.mkstemp(suffix=".html", prefix="aglgis_sar_")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(html)
        self.dlg.sar_web_view.load(QUrl.fromLocalFile(path))

        # Drop the previous render's file (the view has moved off it by now).
        prev = getattr(self, "_plot_path", None)
        if prev and os.path.exists(prev):
            try:
                os.remove(prev)
            except OSError:
                pass
        self._plot_path = path
