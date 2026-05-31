# -*- coding: utf-8 -*-
"""
DEM controller for AGLgis QGIS plugin.

Orchestrates DEM operations, AOI management, and coordinates between
services for dataset loading and layer rendering.
"""

from qgis.core import (
    QgsProject,
    QgsCoordinateTransform,
)

from qgis.PyQt.QtWidgets import QFileDialog
from qgis.PyQt.QtCore import QTimer, QCoreApplication

from ..services.map_utils import hybrid_function
from ..services.aoi_draw_tool import start_draw_aoi
from ..services.aoi_service import AOIService
from ..services.dem_renderer import DEMRenderer
from ..services.dataset_manager import DatasetManager
from ..services.settings_manager import SettingsManager
from ..services.dem_registry import DEMRegistry
from ..services.dem_worker import DatasetAvailabilityWorker, DemDownloadWorker


def _tr(text):
    return QCoreApplication.translate("AGLgis", text)


class DEMCtrl:
    """
    Orchestrates DEM operations and coordinates between services.

    Manages AOI-based dataset loading, DEM service calls, and layer
    management across the plugin.
    """

    def __init__(self, dialog, gee_service, interface):
        self.dlg = dialog
        self.gee_service = gee_service
        self.interface = interface
        self.current_aoi = None
        self.current_aoi_bbox = None
        self._pending_layer = None
        self._debounce_timer = QTimer()
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.timeout.connect(self._load_aoi_for_pending_layer)
        # Strong refs to running QThreads (so they aren't GC'd mid-run) and a
        # generation token to ignore stale dataset-availability results.
        self._workers = set()
        self._ds_gen = 0
        self._dem_running = False
        self._dem_btn_text = None

    def _track(self, worker):
        self._workers.add(worker)
        worker.finished.connect(lambda w=worker: self._untrack(w))

    def _untrack(self, worker):
        self._workers.discard(worker)
        worker.deleteLater()

    def _is_passive_ee_init_error(self, error):
        """Return True for EE initialization errors caused by passive UI refresh."""
        return (
            not self.gee_service.is_authenticated
            and "Earth Engine client library not initialized" in str(error)
        )

    def handle_get_aoi(self):
        """Load the AOI from the selected layer and store it for downstream use."""
        try:
            layer = self.dlg.layer_combo.currentLayer()

            if not layer:
                self.dlg.pop_message(_tr("Select a layer."), "warning")
                return

            if not self.gee_service.is_authenticated:
                self.current_aoi = None
                self.current_aoi_bbox = None
                self.load_available_datasets()
                return

            self.current_aoi, self.current_aoi_bbox = AOIService.get_aoi_from_layer(
                layer
            )

            self.load_available_datasets()

        except Exception as e:
            if self._is_passive_ee_init_error(e):
                return
            self.dlg.pop_message(str(e), "warning")

    def handle_dem_service(self, interface):
        """
        Download the selected DEM and load it into QGIS.

        The file is saved to the folder chosen by the user via the Browse
        button. When no folder is selected, it falls back to the system's
        temporary directory.

        Args:
            interface: The QGIS interface instance for message bar.
        """

        if not self.gee_service.is_authenticated:
            self.dlg.pop_message(
                _tr(
                    "Authentication is required to download DEM data. "
                    "Please go to the Auth page and validate your Google Cloud project ID."
                ),
                "warning",
            )
            return

        if not self.current_aoi:
            self.dlg.pop_message(
                _tr("No AOI selected. Please select a layer first."), "warning"
            )
            return

        dataset_name = self.dlg.dem_combo.currentData()
        if not dataset_name:
            self.dlg.pop_message(_tr("No dataset selected."), "warning")
            return

        if self._dem_running:
            return  # a download is already in flight

        output_folder = self.dlg.folder_input.text().strip() or None
        buffer_m = self.dlg.buffer_slider.value()
        aoi = self._apply_buffer(self.current_aoi, buffer_m)

        # Run the download off the UI thread; load into QGIS on completion.
        self._set_dem_running(True)
        worker = DemDownloadWorker(aoi, dataset_name, output_folder)
        worker.finished_ok.connect(self._on_dem_downloaded)
        worker.failed.connect(self._on_dem_failed)
        self._track(worker)
        worker.start()

    def _set_dem_running(self, running):
        self._dem_running = running
        btn = self.dlg.btn_download_dem
        if running and self._dem_btn_text is None:
            self._dem_btn_text = btn.text()
        btn.setEnabled(not running)
        btn.setText(_tr("Downloading…") if running else (self._dem_btn_text or btn.text()))

    def _on_dem_downloaded(self, dem_path, dataset_name):
        self._set_dem_running(False)
        try:
            DEMRenderer.load_dem_to_qgis(dem_path, dataset_name)
            self.interface.messageBar().pushMessage(
                "AGLgis", _tr("DEM '%s' loaded successfully.") % dataset_name
            )
        except Exception as e:
            self.dlg.pop_message(str(e), "warning")

    def _on_dem_failed(self, message):
        self._set_dem_running(False)
        self.dlg.pop_message(message, "warning")

    def handle_layer_changed(self, layer):
        """
        Handle layer selection changes.

        Zooms the map canvas to the selected layer, then updates the current
        AOI and loads the available datasets for that region.

        Args:
            layer: The newly selected layer.
        """
        if not layer or not layer.isValid():
            self._debounce_timer.stop()
            self.current_aoi = None
            self.current_aoi_bbox = None
            self.dlg.dem_combo.clear()
            return

        if not self.gee_service.is_authenticated:
            self._debounce_timer.stop()
            self.current_aoi = None
            self.current_aoi_bbox = None
            return

        canvas = self.interface.mapCanvas()
        transform = QgsCoordinateTransform(
            layer.crs(),
            canvas.mapSettings().destinationCrs(),
            QgsProject.instance(),
        )
        extent = transform.transformBoundingBox(layer.extent())
        extent.scale(1.8)
        canvas.setExtent(extent)
        canvas.refresh()

        self._pending_layer = layer
        self._debounce_timer.start(300)

    def handle_layer_activated(self, *args):
        """Handle AOI layer choices explicitly made from the plugin combo box."""
        self.handle_layer_changed(self.dlg.layer_combo.currentLayer())

    def _load_aoi_for_pending_layer(self):
        """Load AOI and available datasets for the debounced pending layer."""
        layer = self._pending_layer
        if not layer or not layer.isValid():
            self.current_aoi = None
            self.current_aoi_bbox = None
            self.dlg.dem_combo.clear()
            return
        if not self.gee_service.is_authenticated:
            self.current_aoi = None
            self.current_aoi_bbox = None
            return
        try:
            self.current_aoi, self.current_aoi_bbox = AOIService.get_aoi_from_layer(
                layer
            )
            self.load_available_datasets()
        except Exception as e:
            if self._is_passive_ee_init_error(e):
                return
            self.dlg.pop_message(str(e), "warning")

    def load_available_datasets(self):
        """Load available datasets in the combobox based on current AOI.

        When the user is not authenticated, all datasets from the catalog are
        listed without any GEE availability check.  When authenticated, only
        datasets that intersect the current AOI are shown.
        """
        combo = self.dlg.dem_combo
        combo.clear()

        if not self.gee_service.is_authenticated:
            for dataset in DEMRegistry().list_datasets():
                combo.addItem(dataset.name, dataset.name)
            return

        if not self.current_aoi:
            return

        # The availability check hits GEE per dataset; run it off the UI thread.
        # A generation token discards results from superseded AOI selections.
        self._ds_gen += 1
        gen = self._ds_gen

        combo.blockSignals(True)
        combo.clear()
        combo.addItem(_tr("Checking available datasets…"))
        combo.setEnabled(False)
        combo.blockSignals(False)

        worker = DatasetAvailabilityWorker(self.current_aoi, self.current_aoi_bbox)
        worker.finished_ok.connect(
            lambda names, g=gen: self._on_datasets_ready(names, g)
        )
        worker.failed.connect(lambda msg, g=gen: self._on_datasets_failed(msg, g))
        self._track(worker)
        worker.start()

    def _on_datasets_ready(self, names, gen):
        if gen != self._ds_gen:
            return  # a newer AOI selection superseded this request
        combo = self.dlg.dem_combo
        combo.blockSignals(True)
        combo.clear()
        for name in names:
            combo.addItem(name, name)
        combo.setEnabled(True)
        combo.blockSignals(False)
        self.on_dataset_changed()

    def _on_datasets_failed(self, message, gen):
        if gen != self._ds_gen:
            return
        combo = self.dlg.dem_combo
        combo.blockSignals(True)
        combo.clear()
        combo.setEnabled(True)
        combo.blockSignals(False)
        if not self._is_passive_ee_init_error(message):
            self.dlg.pop_message(message, "warning")

    def handle_folder_selection(self):
        """Open a folder picker, persist the choice, and update the UI."""
        current_folder = SettingsManager.load_download_folder()

        folder = QFileDialog.getExistingDirectory(
            self.dlg,
            _tr("Select DEM Download Folder"),
            current_folder,
        )

        if folder:
            self.dlg.folder_input.setText(folder)
            SettingsManager.save_download_folder(folder)

    def on_dataset_changed(self):
        """Update the dataset info panel when the selected dataset changes."""
        DatasetManager.update_dataset_info(self.dlg.dem_combo, self.dlg.dem_info)

    def handle_hybrid_layer(self):
        """Load the Google hybrid basemap layer."""
        hybrid_function()
        self.interface.messageBar().pushMessage(
            "AGLgis", _tr("Google Hybrid Layer loaded successfully")
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
            self.interface, self.dlg.layer_combo, self.dlg.btn_draw_aoi
        )

    def _apply_buffer(self, aoi, buffer_distance: int):
        """
        Return a buffered copy of the AOI without mutating the original.

        Args:
            aoi: ee.FeatureCollection representing the current AOI.
            buffer_distance: Buffer in metres.  Zero returns the original
                object unchanged.

        Returns:
            ee.FeatureCollection — buffered when distance != 0, original otherwise.
        """
        if buffer_distance == 0:
            return aoi
        return aoi.map(lambda feature: feature.buffer(buffer_distance))
