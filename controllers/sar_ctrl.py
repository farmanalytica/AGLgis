from ..services.aoi_service import AOIService
from ..services.sar_service import SARService
from ..services.sar_renderer import SARRenderer
from ..services.settings_manager import SettingsManager

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QApplication
import pandas as pd
import plotly.express as px

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
            preview_url = SARService.get_ratio_preview_url(selected_image, self.aoi)
            self._render_preview(selected_date, preview_url)
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
            preview_url = SARService.get_ratio_preview_url(selected_image, self.aoi)
            self._render_preview(selected_date, preview_url)

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
                    "AGLgis", f"SAR image '{selected_date}' loaded successfully."
                )
        except Exception as e:
            self.dlg.pop_message(str(e), "warning")
        finally:
            QApplication.restoreOverrideCursor()

    def _render_timeseries(self):
        fig = px.line(
            self.dataframe,
            x="dates",
            y="AOI_average",
            markers=True,
            title="VV/VH Ratio Mean Time Series",
        )
        fig.update_layout(
            xaxis_title="Date",
            yaxis_title="VV/VH Ratio Mean",
            yaxis=dict(
                rangemode="tozero",
                tickformat=".3f",
            ),
            margin=dict(l=80, r=20, t=40, b=40),
        )

        chart_html = fig.to_html(
            include_plotlyjs=True,
            full_html=False,
            config={"displayModeBar": False, "responsive": True},
        )
        table_html = self.dataframe.to_html(index=False, classes="sar-table")
        self.dlg.sar_web_view.setHtml(
            f"""
            <html>
            <head>
                <style>
                    body {{
                        margin: 0;
                        padding: 12px;
                        background: #ffffff;
                        color: #212121;
                        font-family: Arial, sans-serif;
                    }}
                    .sar-table {{
                        width: 100%;
                        border-collapse: collapse;
                        margin-top: 12px;
                        font-size: 12px;
                    }}
                    .sar-table th, .sar-table td {{
                        border: 1px solid #e0e0e0;
                        padding: 6px 8px;
                        text-align: left;
                    }}
                    .sar-table th {{
                        background: #f3f7f4;
                        color: #1b6b39;
                    }}
                </style>
            </head>
            <body>
                {chart_html}
                {table_html}
            </body>
            </html>
            """
        )

    def _render_preview(self, selected_date, preview_url):
        self.dlg.sar_web_view.setHtml(
            f"""
            <html>
            <head>
                <style>
                    body {{
                        margin: 0;
                        padding: 14px;
                        background: #ffffff;
                        color: #212121;
                        font-family: Arial, sans-serif;
                    }}
                    h3 {{
                        margin: 0 0 10px 0;
                        color: #1b6b39;
                        font-size: 15px;
                    }}
                    img {{
                        display: block;
                        width: 100%;
                        height: auto;
                        border: 1px solid #dce6df;
                    }}
                </style>
            </head>
            <body>
                <h3>VV/VH Ratio Preview - {selected_date}</h3>
                <img src="{preview_url}" />
            </body>
            </html>
            """
        )
