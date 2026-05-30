# -*- coding: utf-8 -*-
import re

from qgis.PyQt.QtCore import QCoreApplication
from qgis.PyQt.QtWidgets import QFileDialog

from ..services.auth_worker import AuthWorker, AuthStatusWorker, CANCELLED
from ..services.settings_manager import SettingsManager


def _tr(text):
    return QCoreApplication.translate("AGLgis", text)


class AuthCtrl:
    """Handles all user interactions on the authentication page."""

    def __init__(self, dialog, gee_service):
        self.dlg = dialog
        self.gee_service = gee_service
        self._worker = None
        self._status_worker = None

    def check_status(self):
        """
        Quickly report the current GEE sign-in status on the auth page,
        without launching the browser.  Runs off the UI thread.
        """
        # Don't interfere with an in-flight sign-in.
        if self._worker is not None and self._worker.isRunning():
            return
        if self._status_worker is not None and self._status_worker.isRunning():
            return

        self.dlg.set_auth_state("checking")
        self._status_worker = AuthStatusWorker(
            self.gee_service, self.dlg.project_id_input.text()
        )
        self._status_worker.status_ready.connect(self._on_status_ready)
        self._status_worker.start()

    def _on_status_ready(self, state):
        self.dlg.set_auth_state(state)
        worker = self._status_worker
        self._status_worker = None
        if worker is not None:
            worker.deleteLater()

    def on_project_id_changed(self, _text):
        """A changed project ID invalidates a prior verified state, so the
        user must validate again before continuing (no stale 'Continue')."""
        if self.gee_service.is_authenticated:
            self.gee_service.is_authenticated = False
            state = "stored" if self.gee_service.has_stored_credentials() else "none"
            self.dlg.set_auth_state(state)

    def handle_authentication(self):
        # While a sign-in is in flight, the primary button acts as a Cancel.
        if self._worker is not None and self._worker.isRunning():
            self._worker.cancel()
            self.dlg.set_auth_status(_tr("Cancelling…"))
            return

        # Already signed in: skip the whole auth flow and just continue.
        if self.gee_service.is_authenticated:
            self.dlg.show_radar_page()
            self.dlg.sar_set_tab(1)
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
            self.dlg.set_auth_state("authenticated")
            self.dlg.show_radar_page()
            self.dlg.sar_set_tab(1)
            self.dlg.pop_message(_tr("Authentication successful!"), "info")
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
        finally:
            self.check_status()

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
