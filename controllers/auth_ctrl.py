# -*- coding: utf-8 -*-
import re

from qgis.PyQt.QtCore import QCoreApplication
from qgis.PyQt.QtWidgets import QFileDialog

from ..services.auth_worker import AuthWorker, CANCELLED
from ..services.settings_manager import SettingsManager


def _tr(text):
    return QCoreApplication.translate("AGLgis", text)


class AuthCtrl:
    """Handles all user interactions on the authentication page."""

    def __init__(self, dialog, gee_service, dem_ctrl):
        self.dlg = dialog
        self.gee_service = gee_service
        self.dem_ctrl = dem_ctrl
        self._worker = None

    def handle_authentication(self):
        # While a sign-in is in flight, the primary button acts as a Cancel.
        if self._worker is not None and self._worker.isRunning():
            self._worker.cancel()
            self.dlg.set_auth_status(_tr("Cancelling…"))
            return

        project_id = self.dlg.project_id_input.text()
        if not project_id:
            self.dlg.pop_message(_tr("Missing Project ID."), "warning")
            return

        if not re.match(r"^[a-z][a-z0-9-]{4,28}[a-z0-9]$", project_id):
            self.dlg.pop_message(_tr("Invalid Project ID."), "warning")
            return

        self.dlg.set_auth_busy(True)
        self._worker = AuthWorker(self.gee_service, project_id)
        self._worker.browser_opened.connect(self._on_browser_opened)
        self._worker.finished_auth.connect(self._on_auth_finished)
        self._worker.start()

    def _on_browser_opened(self, url):
        self.dlg.set_auth_status(
            _tr("Waiting for sign-in in your browser…"), url
        )

    def _on_auth_finished(self, success, message):
        self.dlg.set_auth_busy(False)
        worker = self._worker
        self._worker = None
        if worker is not None:
            worker.deleteLater()

        if success:
            self.dlg.show_radar_page()
            self.dlg.pop_message(_tr("Authentication successful!"), "info")

            layer = self.dlg.layer_combo.currentLayer()
            if layer:
                self.dem_ctrl.handle_layer_changed(layer)
            else:
                self.dem_ctrl.load_available_datasets()
        elif message == CANCELLED:
            pass  # User aborted; UI is already back to its idle state.
        else:
            self.dlg.pop_message(message, "warning")

    def handle_reset_authentication(self):
        try:
            msg = self.gee_service.reset_authentication()
            if msg:
                self.dlg.pop_message(msg, "info")
        except (FileNotFoundError, RuntimeError, OSError) as e:
            self.dlg.pop_message(str(e), "warning")

    def handle_folder_selection(self):
        current_folder = SettingsManager.load_download_folder()
        folder = QFileDialog.getExistingDirectory(
            self.dlg,
            _tr("Select DEM Download Folder"),
            current_folder,
        )
        if folder:
            self.dlg.folder_input.setText(folder)
            SettingsManager.save_download_folder(folder)

    def handle_clear_folder(self):
        self.dlg.folder_input.clear()
        SettingsManager.clear_download_folder()
