# -*- coding: utf-8 -*-
import re

from qgis.PyQt.QtCore import QCoreApplication
from qgis.PyQt.QtWidgets import QFileDialog

from ..services.settings_manager import SettingsManager


def _tr(text):
    return QCoreApplication.translate("AGLgis", text)


class AuthCtrl:
    """Handles all user interactions on the authentication page."""

    def __init__(self, dialog, gee_service, dem_ctrl):
        self.dlg = dialog
        self.gee_service = gee_service
        self.dem_ctrl = dem_ctrl

    def handle_authentication(self):
        project_id = self.dlg.project_id_input.text()
        if not project_id:
            self.dlg.pop_message(_tr("Missing Project ID."), "warning")
            return

        if not re.match(r"^[a-z][a-z0-9-]{4,28}[a-z0-9]$", project_id):
            self.dlg.pop_message(_tr("Invalid Project ID."), "warning")
            return

        try:
            self.gee_service.authenticate(project_id)
            self.dlg.show_aoi_page()
            self.dlg.pop_message(_tr("Authentication successful!"), "info")

            layer = self.dlg.layer_combo.currentLayer()
            if layer:
                self.dem_ctrl.handle_layer_changed(layer)
            else:
                self.dem_ctrl.load_available_datasets()

        except Exception as e:
            self.dlg.pop_message(str(e), "warning")

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
