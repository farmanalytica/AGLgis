from ..services.aoi_service import AOIService
from ..services.sar_service import SARService
from ..services.sar_renderer import SARRenderer
from ..services.sar_worker import (
    SARWorker,
    SARPreviewWorker,
    SARBatchDownloadWorker,
    SARCompositeWorker,
)
from ..services.settings_manager import SettingsManager
from ..services.aoi_draw_tool import start_draw_aoi
from ..view.sar_plot import render_chart_html

from qgis.PyQt.QtCore import Qt, QCoreApplication, QUrl
from qgis.PyQt.QtGui import QDesktopServices
from qgis.PyQt.QtWidgets import (
    QApplication,
    QFileDialog,
    QProgressDialog,
)
from qgis.core import QgsProject, QgsCoordinateTransform
import os
import tempfile
import pandas as pd
from datetime import datetime

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
        self._preview_worker = None
        self._active_dates = None
        self._filter_dialog = None
        self._batch_worker = None
        self._batch_dialog = None
        self._zoom_enabled = True
        self._current_index = "VV/VH Ratio"
        self._composite_worker = None

    def _show_auth_required_message(self):
        self.dlg.pop_message(
            _tr(
                "Authentication is required to download SAR data. "
                "Please go to the Auth page and validate your Google Cloud project ID."
            ),
            "warning",
        )

    def handle_draw_aoi(self):
        """Toggle rectangular AOI drawing on the canvas.

        Clicking the button while draw mode is already armed turns it off
        (restoring the previous map tool) instead of re-arming it.
        """
        canvas = self.interface.mapCanvas()
        tool = getattr(self, "_draw_tool", None)
        if tool is not None and canvas.mapTool() is tool:
            canvas.unsetMapTool(tool)
            self._draw_tool = None
            return
        self._draw_tool = start_draw_aoi(
            self.interface, self.dlg.sar_layer_combo, self.dlg.sar_btn_draw_aoi
        )

    def handle_layer_changed(self):
        """Zoom to the selected AOI layer."""
        if not self._zoom_enabled:
            return

        layer = self.dlg.sar_layer_combo.currentLayer()
        if not layer or not layer.isValid():
            return

        if not self.interface:
            return

        try:
            canvas = self.interface.mapCanvas()
            transform = QgsCoordinateTransform(
                layer.crs(),
                canvas.mapSettings().destinationCrs(),
                QgsProject.instance(),
            )
            extent = transform.transformBoundingBox(layer.extent())
            extent.scale(1.5)
            canvas.setExtent(extent)
            canvas.refresh()
        except Exception:
            pass

    def handle_sar_run(self):
        if self._worker is not None and self._worker.isRunning():
            return  # a run is already in flight

        if self.gee_service and not self.gee_service.is_authenticated:
            self._show_auth_required_message()
            return

        layer = self.dlg.sar_layer_combo.currentLayer()
        if not layer:
            self.dlg.pop_message(_tr("Select an AOI layer."), "warning")
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
            "index": self.dlg.sar_index_combo.currentText(),
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

    def _set_preview_running(self, running):
        self.dlg.sar_btn_preview.setEnabled(not running)
        self.dlg.sar_btn_download_preview.setEnabled(not running)
        if running:
            self._preview_btn_text = (
                self.dlg.sar_btn_preview.text(),
                self.dlg.sar_btn_download_preview.text(),
            )
            self.dlg.sar_btn_preview.setText(_tr("Loading…"))
            self.dlg.sar_btn_download_preview.setText(_tr("Loading…"))
        else:
            if hasattr(self, "_preview_btn_text"):
                self.dlg.sar_btn_preview.setText(self._preview_btn_text[0])
                self.dlg.sar_btn_download_preview.setText(self._preview_btn_text[1])

    def _clear_worker(self):
        worker = self._worker
        self._worker = None
        if worker is not None:
            worker.deleteLater()

    def _on_sar_done(self, collection, data, index):
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
        self._active_dates = None
        self._current_index = index

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

    def _clear_preview_worker(self):
        worker = self._preview_worker
        self._preview_worker = None
        if worker is not None:
            worker.deleteLater()

    def _on_preview_done(self, output_path, label):
        self._set_preview_running(False)
        self._clear_preview_worker()
        render_mode = self.dlg.sar_render_combo.currentText()
        SARRenderer.load_sar_to_qgis(output_path, label, render_mode=render_mode)
        if self.interface:
            self.interface.messageBar().pushMessage(
                "AGLgis", f"SAR preview '{output_path.split('/')[-1]}' loaded into QGIS."
            )

    def _on_download_preview_done(self, output_path, label):
        self._set_preview_running(False)
        self._clear_preview_worker()
        render_mode = self.dlg.sar_render_combo.currentText()
        SARRenderer.load_sar_to_qgis(output_path, label, render_mode=render_mode)
        if self.interface:
            self.interface.messageBar().pushMessage(
                "AGLgis",
                f"SAR image '{output_path.split('/')[-1]}' downloaded and loaded successfully.",
            )

    def _on_preview_failed(self, message):
        self._set_preview_running(False)
        self._clear_preview_worker()
        self.dlg.pop_message(message, "warning")

    def handle_preview_image(self):
        if self._preview_worker is not None and self._preview_worker.isRunning():
            return  # a preview operation is already in flight

        if self.collection is None or self.aoi is None:
            self.dlg.pop_message(_tr("Run SAR processing first."), "warning")
            return

        selected_date = self.dlg.sar_result_date_combo.currentText()
        self._set_preview_running(True)
        meta = SARService.INDEX_REGISTRY[self._current_index]
        self._preview_worker = SARPreviewWorker(
            self.collection,
            self.aoi,
            selected_date,
            tempfile.gettempdir(),
            f"SAR_Preview_{selected_date}",
            index_band=meta["band"],
            index_label=meta["band_label"],
        )
        self._preview_worker.finished_ok.connect(self._on_preview_done)
        self._preview_worker.failed.connect(self._on_preview_failed)
        self._preview_worker.start()

    def handle_download_preview(self):
        if self._preview_worker is not None and self._preview_worker.isRunning():
            return  # a preview operation is already in flight

        if self.collection is None or self.aoi is None:
            self.dlg.pop_message(_tr("Run SAR processing first."), "warning")
            return

        selected_date = self.dlg.sar_result_date_combo.currentText()
        output_folder = SettingsManager.load_download_folder()
        self._set_preview_running(True)
        meta = SARService.INDEX_REGISTRY[self._current_index]
        self._preview_worker = SARPreviewWorker(
            self.collection,
            self.aoi,
            selected_date,
            output_folder,
            f"SAR_{selected_date}",
            index_band=meta["band"],
            index_label=meta["band_label"],
        )
        self._preview_worker.finished_ok.connect(
            lambda path, label: self._on_download_preview_done(path, label)
        )
        self._preview_worker.failed.connect(self._on_preview_failed)
        self._preview_worker.start()

    # ------------------------------------------------------------------
    # Synthetic image (composite of the selected index over selected dates)
    # ------------------------------------------------------------------
    def _selected_composite_dates(self):
        dates = self.dataframe["dates"].tolist()
        if self._active_dates is not None:
            dates = [d for d in dates if d in self._active_dates]
        return dates

    def handle_composite_preview(self):
        self._run_composite(to_folder=False)

    def handle_composite_download(self):
        self._run_composite(to_folder=True)

    def _run_composite(self, to_folder):
        if self._composite_worker is not None and self._composite_worker.isRunning():
            return  # a composite operation is already in flight

        if self.collection is None or self.aoi is None or self.dataframe is None:
            self.dlg.pop_message(_tr("Run SAR processing first."), "warning")
            return

        dates = self._selected_composite_dates()
        if not dates:
            self.dlg.pop_message(_tr("No dates selected for the composite."), "warning")
            return

        metric = self.dlg.sar_composite_metric_combo.currentText()
        meta = SARService.INDEX_REGISTRY[self._current_index]
        start_date = min(dates)  # AUC needs a reference start date
        output_folder = (
            SettingsManager.load_download_folder()
            if to_folder
            else tempfile.gettempdir()
        )
        label = f"{meta['band_label']} {metric}"

        self._set_composite_running(True)
        self._composite_worker = SARCompositeWorker(
            self.collection,
            self.aoi,
            meta["band"],
            meta["band_label"],
            metric,
            dates,
            start_date,
            output_folder,
            label,
        )
        self._composite_worker.finished_ok.connect(
            lambda path, lbl, tf=to_folder: self._on_composite_done(path, lbl, tf)
        )
        self._composite_worker.failed.connect(self._on_composite_failed)
        self._composite_worker.start()

    def _set_composite_running(self, running):
        self.dlg.sar_btn_composite_preview.setEnabled(not running)
        self.dlg.sar_btn_composite_download.setEnabled(not running)
        if running:
            self._composite_btn_text = (
                self.dlg.sar_btn_composite_preview.text(),
                self.dlg.sar_btn_composite_download.text(),
            )
            self.dlg.sar_btn_composite_preview.setText(_tr("Working…"))
            self.dlg.sar_btn_composite_download.setText(_tr("Working…"))
        elif hasattr(self, "_composite_btn_text"):
            self.dlg.sar_btn_composite_preview.setText(self._composite_btn_text[0])
            self.dlg.sar_btn_composite_download.setText(self._composite_btn_text[1])

    def _clear_composite_worker(self):
        worker = self._composite_worker
        self._composite_worker = None
        if worker is not None:
            worker.deleteLater()

    def _on_composite_done(self, output_path, label, to_folder):
        self._set_composite_running(False)
        self._clear_composite_worker()
        ramp = self.dlg.sar_composite_ramp_combo.currentText()
        SARRenderer.load_composite_to_qgis(output_path, label, color_ramp_name=ramp)
        if self.interface:
            verb = _tr("downloaded and loaded") if to_folder else _tr("loaded")
            self.interface.messageBar().pushMessage(
                "AGLgis",
                f"Composite '{os.path.basename(output_path)}' {verb} into QGIS.",
            )

    def _on_composite_failed(self, message):
        self._set_composite_running(False)
        self._clear_composite_worker()
        self.dlg.pop_message(message, "warning")

    def handle_batch_download(self):
        if self.collection is None or self.aoi is None:
            self.dlg.pop_message(_tr("Run SAR processing first."), "warning")
            return

        dates = self.dataframe["dates"].tolist()
        if self._active_dates is not None:
            dates = [d for d in dates if d in self._active_dates]

        if not dates:
            self.dlg.pop_message(_tr("No dates selected to download."), "warning")
            return

        output_folder = SettingsManager.load_download_folder()

        self._batch_dialog = QProgressDialog(
            _tr("Preparing batch download..."),
            _tr("Cancel"),
            0,
            len(dates),
            self.dlg,
        )
        self._batch_dialog.setWindowTitle(_tr("Batch Download Progress"))
        self._batch_dialog.setModal(True)
        self._batch_dialog.show()

        meta = SARService.INDEX_REGISTRY[self._current_index]
        self._batch_worker = SARBatchDownloadWorker(
            self.collection, self.aoi, dates, output_folder,
            index_band=meta["band"],
            index_label=meta["band_label"],
        )
        self._batch_worker.progress.connect(self._on_batch_progress)
        self._batch_worker.finished_ok.connect(self._on_batch_done)
        self._batch_worker.failed.connect(self._on_batch_failed)
        self._batch_worker.cancelled.connect(
            lambda success, total, paths: self._on_batch_cancelled(success, total, paths)
        )
        self._batch_dialog.canceled.connect(self._batch_worker.request_cancel)
        self._batch_worker.start()

    def _on_batch_progress(self, current, total, date_str):
        self._batch_dialog.setMaximum(total)
        self._batch_dialog.setValue(current)
        self._batch_dialog.setLabelText(
            _tr(f"Downloading {current} of {total}: {date_str}")
        )

    def _on_batch_done(self, successful, total, downloaded_paths):
        self._batch_dialog.close()
        self._load_downloaded_images(downloaded_paths)

        failed = total - successful
        msg = _tr(f"Batch download complete: {successful}/{total} successful")
        if failed > 0:
            msg += _tr(f" ({failed} failed)")
        msg_type = "warning" if failed > 0 else "info"
        self.dlg.pop_message(msg, msg_type)

    def _on_batch_failed(self, message):
        if self._batch_dialog:
            self._batch_dialog.close()
        self.dlg.pop_message(_tr(f"Batch download failed: {message}"), "warning")

    def _on_batch_cancelled(self, successful, total, downloaded_paths):
        self._batch_dialog.close()
        self._load_downloaded_images(downloaded_paths)

        if successful > 0:
            msg = _tr(
                f"Batch download cancelled. {successful}/{total} images downloaded and loaded."
            )
            self.dlg.pop_message(msg, "info")
        else:
            self.dlg.pop_message(_tr("Batch download cancelled by user."), "info")

    def _load_downloaded_images(self, paths):
        render_mode = self.dlg.sar_render_combo.currentText()
        for path in paths:
            try:
                filename = os.path.basename(path)
                date_str = filename.replace("Sentinel1_", "").replace(".tiff", "")
                label = f"SAR_{date_str}"
                SARRenderer.load_sar_to_qgis(path, label, render_mode=render_mode)
            except Exception:
                continue

    def handle_filter_dates(self):
        if self.dataframe is None:
            self.dlg.pop_message(_tr("Run SAR processing first."), "warning")
            return
        from ..view.sar_date_filter_dialog import SARDateFilterDialog

        if self._filter_dialog is not None:
            self._filter_dialog.raise_()
            self._filter_dialog.activateWindow()
            return

        dates = self.dataframe["dates"].tolist()
        self._filter_dialog = SARDateFilterDialog(
            dates, self._active_dates, parent=self.dlg
        )
        self._filter_dialog.filter_changed.connect(self._on_filter_changed)
        self._filter_dialog.finished.connect(self._on_filter_dialog_closed)
        self._filter_dialog.show()

    def _on_filter_changed(self, selected_dates):
        all_dates = self.dataframe["dates"].tolist()
        self._active_dates = (
            None if set(selected_dates) == set(all_dates) else selected_dates
        )
        self._render_timeseries()

    def _on_filter_dialog_closed(self):
        self._filter_dialog = None

    def handle_open_browser(self):
        if self.dataframe is None:
            self.dlg.pop_message(_tr("Run SAR processing first."), "warning")
            return
        df = self.dataframe
        if self._active_dates is not None:
            df = df[df["dates"].isin(self._active_dates)]
        meta = SARService.INDEX_REGISTRY[self._current_index]
        html = render_chart_html(df, hide_toolbar=False, title=meta["title"], ylabel=meta["ylabel"])
        with tempfile.NamedTemporaryFile(
            suffix=".html", delete=False, mode="w", encoding="utf-8"
        ) as f:
            f.write(html)
            path = f.name
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def handle_export_csv(self):
        if self.dataframe is None:
            self.dlg.pop_message(_tr("Run SAR processing first."), "warning")
            return

        date_str = datetime.now().strftime("%Y%m%d")
        default_filename = f"SAR_timeseries_{date_str}.csv"

        file_path, _ = QFileDialog.getSaveFileName(
            self.dlg,
            _tr("Export SAR Time Series as CSV"),
            default_filename,
            _tr("CSV Files (*.csv);;All Files (*)"),
        )

        if not file_path:
            return

        df = self.dataframe
        if self._active_dates is not None:
            df = df[df["dates"].isin(self._active_dates)]

        try:
            df.to_csv(file_path, index=False)
            self.dlg.pop_message(
                _tr(f"CSV exported successfully to {file_path}"), "info"
            )
        except Exception as e:
            self.dlg.pop_message(_tr(f"Failed to export CSV: {str(e)}"), "warning")

    def _render_timeseries(self):
        df = self.dataframe
        if self._active_dates is not None:
            df = df[df["dates"].isin(self._active_dates)]
        meta = SARService.INDEX_REGISTRY[self._current_index]
        html = render_chart_html(df, title=meta["title"], ylabel=meta["ylabel"])
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
