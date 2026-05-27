# -*- coding: utf-8 -*-
"""
GEE (Google Earth Engine) service layer.

All Earth Engine business logic lives here, keeping the UI layer free
of SDK-specific details.
"""

import os
import time

import ee
from qgis.PyQt.QtCore import QCoreApplication, QSettings


def _tr(text):
    return QCoreApplication.translate("AGLgis", text)


class AuthCancelled(Exception):
    """Raised when the user aborts the OAuth flow before it completes."""


class AuthTimeout(Exception):
    """Raised when the browser sign-in is not completed within the deadline."""


class GEEService:
    """
    Service layer for Google Earth Engine operations.

    Handles authentication, initialization, and credential management
    for the Google Earth Engine API.
    """

    SETTINGS_PROJECT_ID_KEY = "MyPlugin/projectID"

    def __init__(self):
        self.is_authenticated = False

    def get_saved_project_id(self) -> str:
        """
        Retrieve the saved GEE project ID from settings.

        Returns:
            Project ID string, or empty string if not found.
        """

        return QSettings().value(self.SETTINGS_PROJECT_ID_KEY, "", type=str)

    def save_project_id(self, project_id) -> None:
        """
        Save a GEE project ID to settings.

        Args:
            project_id: Project ID string to save.
        """
        QSettings().setValue(self.SETTINGS_PROJECT_ID_KEY, project_id)

    def authenticate(
        self,
        project_id: str,
        timeout: float = 180,
        should_cancel=None,
        on_browser_open=None,
    ):
        """
        Authenticate with Google Earth Engine.

        Attempts to initialize EE with the given project ID, running the
        browser OAuth flow only if needed. The OAuth wait is bounded by
        ``timeout`` and can be aborted via ``should_cancel`` so the caller
        is never stuck if the user abandons the browser sign-in.

        Args:
            project_id: Google Cloud project ID.
            timeout: Seconds to wait for the browser sign-in before giving up.
            should_cancel: Optional callable returning True to abort the wait.
            on_browser_open: Optional callable invoked with the auth URL once
                the browser flow starts (so the UI can offer to reopen it).

        Raises:
            AuthCancelled: If ``should_cancel`` returns True during the wait.
            AuthTimeout: If the sign-in is not completed within ``timeout``.
            Exception: If authentication fails or the project is invalid.
        """
        should_cancel = should_cancel or (lambda: False)
        try:
            try:
                ee.Initialize(project=project_id)

            except ee.EEException:
                self._run_localhost_oauth(timeout, should_cancel, on_browser_open)
                ee.Initialize(project=project_id)

            default_project_path = f"projects/{project_id}/assets/"

            ee.data.listAssets({"parent": default_project_path})
            self.is_authenticated = True

        except (AuthCancelled, AuthTimeout):
            raise

        except ee.EEException as e:
            error_msg = str(e)

            if "Earth Engine client library not initialized" in error_msg:
                raise Exception("Authentication failed. Please authenticate again.")
            else:
                raise Exception(
                    f"An error occurred during authentication or initialization: {error_msg}"
                )

        except Exception as e:
            raise Exception(f"An unexpected error occurred: {e}")

    def _run_localhost_oauth(self, timeout, should_cancel, on_browser_open):
        """
        Run the GEE localhost OAuth flow with a bounded, cancellable wait.

        Mirrors ``ee.oauth``'s localhost flow but polls the callback server in
        short slices so the caller can cancel, and enforces a deadline so an
        abandoned browser sign-in never blocks forever.
        """
        from ee import oauth

        flow = oauth.Flow("localhost", oauth.SCOPES)
        httpd = flow.server.server
        try:
            oauth._open_new_browser(flow.auth_url)
            if on_browser_open:
                on_browser_open(flow.auth_url)

            httpd.timeout = 1.0  # poll slice so cancel/timeout stay responsive
            handler_cls = httpd.RequestHandlerClass
            deadline = time.monotonic() + timeout
            code = None
            while not code:
                if should_cancel():
                    raise AuthCancelled()
                if time.monotonic() > deadline:
                    raise AuthTimeout()
                httpd.handle_request()  # returns within ~1s if no callback
                code = getattr(handler_cls, "code", None)
        finally:
            try:
                httpd.server_close()
            except Exception:
                pass

        oauth._obtain_and_write_token(
            code, flow.code_verifier, flow.scopes, flow.server.url
        )

    def reset_authentication(self):
        """
        Clear saved Google Earth Engine credentials.

        Args:
            silent: If True, don't raise error if no credentials found.

        Returns:
            Success message string, or None if silent and no credentials.

        Raises:
            FileNotFoundError: If credentials not found.
        """
        credentials_path = ee.oauth.get_credentials_path()

        if not os.path.exists(credentials_path):
            raise FileNotFoundError(_tr("No Earth Engine configuration found to clear."))

        os.remove(credentials_path)

        try:
            import importlib

            importlib.reload(ee.oauth)
            ee.Reset()
        except Exception:
            pass

        self.is_authenticated = False
        return _tr("Earth Engine configuration cleared successfully.")
