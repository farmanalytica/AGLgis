# -*- coding: utf-8 -*-
"""
Background workers for the SAR page's network-bound operations.

The Earth Engine collection build, image download, and preview operations are
slow network calls, so they run off the UI thread to keep the dialog responsive.
The AOI is extracted from the QGIS layer on the main thread (layers are not
thread-safe) and passed in.
"""

import tempfile
from qgis.PyQt.QtCore import QThread, pyqtSignal, QMutex

from .sar_service import SARService
from .sar_renderer import SARRenderer


class SARWorker(QThread):
    """Runs the GEE collection build and spectral-index time-series fetch."""

    # (collection with index band, data list of dicts, index_name)
    finished_ok = pyqtSignal(object, object, str)
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
            index_name = p.get("index", "VV/VH Ratio")
            meta = SARService.INDEX_REGISTRY[index_name]

            # Add all three spectral indices to the collection for download
            collection = collection.map(SARService.add_vvvh_ratio_band)
            collection = collection.map(SARService.add_rvi_band)
            collection = collection.map(SARService.add_dprvi_band)

            data = SARService.get_index_timeseries(collection, self._aoi, meta["band"])
            self.finished_ok.emit(collection, data, index_name)
        except Exception as e:  # noqa: BLE001 - surface any failure to the UI
            self.failed.emit(str(e))


class SARPreviewWorker(QThread):
    """Downloads a SAR image for preview or export off the UI thread."""

    # (output_path, label)
    finished_ok = pyqtSignal(str, str)
    failed = pyqtSignal(str)

    def __init__(self, collection, aoi, selected_date, output_folder, label, index_band="VVVH_ratio", index_label="VV/VH Ratio"):
        super().__init__()
        self._collection = collection
        self._aoi = aoi
        self._selected_date = selected_date
        self._output_folder = output_folder
        self._label = label
        self._index_band = index_band
        self._index_label = index_label

    def run(self):
        try:
            selected_image = SARService.get_image_for_date(
                self._collection,
                self._aoi,
                self._selected_date,
                index_band=self._index_band,
            )
            output_path = SARService.download_image(
                selected_image,
                self._aoi,
                self._selected_date,
                output_folder=self._output_folder,
                index_band=self._index_band,
                index_label=self._index_label,
            )
            self.finished_ok.emit(output_path, self._label)
        except Exception as e:  # noqa: BLE001 - surface any failure to the UI
            self.failed.emit(str(e))


class SARBatchDownloadWorker(QThread):
    """Downloads multiple SAR images sequentially with progress tracking."""

    progress = pyqtSignal(int, int, str)  # (current, total, current_date)
    finished_ok = pyqtSignal(int, int, list)  # (successful, total, downloaded_paths)
    failed = pyqtSignal(str)
    cancelled = pyqtSignal(int, int, list)  # (successful, total, downloaded_paths)

    def __init__(self, collection, aoi, dates, output_folder, index_band="VVVH_ratio", index_label="VV/VH Ratio"):
        super().__init__()
        self._collection = collection
        self._aoi = aoi
        self._dates = dates
        self._output_folder = output_folder
        self._index_band = index_band
        self._index_label = index_label
        self._cancel_requested = False
        self._mutex = QMutex()

    def request_cancel(self):
        self._mutex.lock()
        self._cancel_requested = True
        self._mutex.unlock()

    def run(self):
        successful = 0
        total = len(self._dates)
        downloaded_paths = []

        for idx, date in enumerate(self._dates, start=1):
            self._mutex.lock()
            if self._cancel_requested:
                self._mutex.unlock()
                self.cancelled.emit(successful, total, downloaded_paths)
                return
            self._mutex.unlock()

            self.progress.emit(idx, total, str(date))

            try:
                selected_image = SARService.get_image_for_date(
                    self._collection,
                    self._aoi,
                    date,
                    index_band=self._index_band,
                )
                output_path = SARService.download_image(
                    selected_image,
                    self._aoi,
                    date,
                    output_folder=self._output_folder,
                    index_band=self._index_band,
                    index_label=self._index_label,
                )
                downloaded_paths.append(output_path)
                successful += 1
            except Exception as e:
                pass

        self.finished_ok.emit(successful, total, downloaded_paths)
