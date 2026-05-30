# -*- coding: utf-8 -*-
"""
Background worker for Google Earth Engine authentication.

Runs the (potentially long, browser-driven) auth flow off the UI thread so
the dialog stays responsive, and exposes a ``cancel()`` so an abandoned
sign-in can be aborted instead of freezing the plugin.
"""

from qgis.PyQt.QtCore import QCoreApplication, QThread, pyqtSignal

from .gee_service import AuthCancelled, AuthTimeout

CANCELLED = "__cancelled__"


def _tr(text):
    return QCoreApplication.translate("AGLgis", text)


class AuthWorker(QThread):
    """Runs ``GEEService.authenticate`` on a background thread."""

    # Auth URL, emitted once the browser OAuth flow actually starts.
    browser_opened = pyqtSignal(str)
    # (success, message): message is "" on success, CANCELLED if the user
    # aborted, or an error string to surface otherwise.
    finished_auth = pyqtSignal(bool, str)

    def __init__(self, gee_service, project_id, timeout=180):
        super().__init__()
        self._gee = gee_service
        self._project_id = project_id
        self._timeout = timeout
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        try:
            self._gee.authenticate(
                self._project_id,
                timeout=self._timeout,
                should_cancel=lambda: self._cancelled,
                on_browser_open=self.browser_opened.emit,
            )
            self.finished_auth.emit(True, "")
        except AuthCancelled:
            self.finished_auth.emit(False, CANCELLED)
        except AuthTimeout:
            self.finished_auth.emit(
                False, _tr("Sign-in timed out. Please try again.")
            )
        except Exception as e:  # noqa: BLE001 - surface any failure to the UI
            self.finished_auth.emit(False, str(e))


class AuthStatusWorker(QThread):
    """
    Off-thread, non-interactive check of the current sign-in status.

    Never opens a browser; just reports one of ``"none"`` (no stored
    credentials), ``"stored"`` (credentials present but project not yet
    verified), or ``"authenticated"`` (credentials verified for the project).
    """

    status_ready = pyqtSignal(str)

    def __init__(self, gee_service, project_id):
        super().__init__()
        self._gee = gee_service
        self._project_id = (project_id or "").strip()

    def run(self):
        try:
            if not self._gee.has_stored_credentials():
                self.status_ready.emit("none")
            elif not self._project_id:
                self.status_ready.emit("stored")
            elif self._gee.verify_silent(self._project_id):
                self.status_ready.emit("authenticated")
            else:
                self.status_ready.emit("stored")
        except Exception:  # noqa: BLE001 - never let the check crash the UI
            self.status_ready.emit("stored")
