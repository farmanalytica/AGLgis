# -*- coding: utf-8 -*-
"""
Background worker for the SAR time-series run.

The Earth Engine collection build + ``getInfo`` fetch is a slow network call, so
it runs off the UI thread to keep the dialog responsive. The AOI is extracted
from the QGIS layer on the main thread (layers are not thread-safe) and passed in.
"""

from qgis.PyQt.QtCore import QThread, pyqtSignal

from .sar_service import SARService


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
