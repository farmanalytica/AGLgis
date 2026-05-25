from ..services.aoi_service import AOIService
from ..services.sar_service import SARService
from ..services.sar_renderer import SARRenderer
from ..services.settings_manager import SettingsManager
from ..view.sar_plot import render_plugin_html, render_browser_html

from qgis.PyQt.QtCore import Qt, QUrl
from qgis.PyQt.QtGui import QDesktopServices
from qgis.PyQt.QtWidgets import QApplication
import tempfile
import pandas as pd

try:
    WAIT_CURSOR = Qt.CursorShape.WaitCursor
except AttributeError:
    WAIT_CURSOR = Qt.WaitCursor


class SARCtrl:
    def __init__(self, dialog, interface=None):
        self.dlg = dialog
        self.interface = interface
        self.collection = None
        self.aoi = None
        self.dataframe = None

    def handle_sar_run(self):
        layer = self.dlg.sar_layer_combo.currentLayer()
        if not layer:
            self.dlg.pop_message("Select an AOI layer.", "warning")
            return

        start_qdate = self.dlg.sar_date_start.date()
        end_qdate = self.dlg.sar_date_end.date()
        if start_qdate >= end_qdate:
            self.dlg.pop_message("End date must be after start date.", "warning")
            return

        QApplication.setOverrideCursor(WAIT_CURSOR)
        QApplication.processEvents()

        try:
            aoi, bbox = AOIService.get_aoi_from_layer(
                layer, use_selected_features=False
            )

            collection = SARService.get_collection(
                aoi=aoi,
                start_date=start_qdate.toString("yyyy-MM-dd"),
                end_date=end_qdate.toString("yyyy-MM-dd"),
                polarization=self.dlg.sar_pol_combo.currentText(),
                output_format=self.dlg.sar_format_combo.currentText(),
                apply_border_noise_correction=self.dlg.sar_chk_border_noise.isChecked(),
                apply_terrain_flattening=self.dlg.sar_chk_terrain.isChecked(),
                apply_speckle_filtering=self.dlg.sar_chk_speckle.isChecked(),
                ascending=False,
            )

            self.collection = collection.map(SARService.add_vvvh_ratio_band)
            self.aoi = aoi
            data = SARService.get_vvvh_ratio_timeseries(self.collection, self.aoi)
            if not data:
                self.dlg.pop_message(
                    "No SAR images found for this date range.", "warning"
                )
                return

            self.dataframe = pd.DataFrame(data)

            self.dlg.sar_result_date_combo.clear()
            self.dlg.sar_result_date_combo.addItems(self.dataframe["dates"].tolist())
            self._render_timeseries()
        except Exception as e:
            self.dlg.pop_message(str(e), "warning")
        finally:
            QApplication.restoreOverrideCursor()

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
                    "AGLgis", f"SAR image '{selected_date}' downloaded and loaded successfully."
                )
        except Exception as e:
            self.dlg.pop_message(str(e), "warning")
        finally:
            QApplication.restoreOverrideCursor()

    def handle_open_browser(self):
        if self.dataframe is None:
            self.dlg.pop_message("Run SAR processing first.", "warning")
            return
        html = render_browser_html(self.dataframe)
        with tempfile.NamedTemporaryFile(
            suffix=".html", delete=False, mode="w", encoding="utf-8"
        ) as f:
            f.write(html)
            path = f.name
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def _render_timeseries(self):
        self.dlg.sar_web_view.setHtml(render_plugin_html(self.dataframe))

