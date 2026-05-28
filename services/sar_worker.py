# -*- coding: utf-8 -*-
"""
Background workers for the SAR page's network-bound operations.

The Earth Engine collection build, image download, and preview operations are
slow network calls, so they run off the UI thread to keep the dialog responsive.
The AOI is extracted from the QGIS layer on the main thread (layers are not
thread-safe) and passed in.
"""

import tempfile
from qgis.PyQt.QtCore import QThread, pyqtSignal

from .sar_service import SARService
from .sar_renderer import SARRenderer


class SARWorker(QThread):
    """Runs the GEE collection build and VV/VH-ratio time-series fetch."""

    # (collection with ratio band, data list of dicts)
    finished_ok = pyqtSignal(object, object)
    failed = pyqtSignal(str)

    def __init__(self, aoi, params):
        super().__init__()
        self._aoi = aoi
        self._params = params

    def run(self):
        try:
            p = self._params
            collection = SARService.get_collection(
                aoi=self._aoi,
                start_date=p["start_date"],
                end_date=p["end_date"],
                polarization=p["polarization"],
                output_format=p["output_format"],
                apply_border_noise_correction=p["border_noise"],
                apply_terrain_flattening=p["terrain"],
                apply_speckle_filtering=p["speckle"],
                ascending=False,
            )
            collection = collection.map(SARService.add_vvvh_ratio_band)
            data = SARService.get_vvvh_ratio_timeseries(collection, self._aoi)
            self.finished_ok.emit(collection, data)
        except Exception as e:  # noqa: BLE001 - surface any failure to the UI
            self.failed.emit(str(e))


class SARPreviewWorker(QThread):
    """Downloads a SAR image for preview or export off the UI thread."""

    # (output_path, label)
    finished_ok = pyqtSignal(str, str)
    failed = pyqtSignal(str)

    def __init__(self, collection, aoi, selected_date, output_folder, label):
        super().__init__()
        self._collection = collection
        self._aoi = aoi
        self._selected_date = selected_date
        self._output_folder = output_folder
        self._label = label

    def run(self):
        try:
            selected_image = SARService.get_image_for_date(
                self._collection,
                self._aoi,
                self._selected_date,
            )
            output_path = SARService.download_image(
                selected_image,
                self._aoi,
                self._selected_date,
                output_folder=self._output_folder,
            )
            self.finished_ok.emit(output_path, self._label)
        except Exception as e:  # noqa: BLE001 - surface any failure to the UI
            self.failed.emit(str(e))
