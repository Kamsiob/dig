"""The window, and the web view that fills it.

The interface is the prototype's own HTML, CSS, and JS, loaded from disk. This
file gives it a window, a channel back to Python, and a hard guarantee that
nothing it does can reach the network.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QRect, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import (
    QWebEnginePage,
    QWebEngineProfile,
    QWebEngineSettings,
    QWebEngineUrlRequestInfo,
    QWebEngineUrlRequestInterceptor,
)
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QMainWindow, QMenu

from dig import __app_name__, paths

MIN_WIDTH = 1100
MIN_HEIGHT = 720

# The only schemes the interface is allowed to load. Everything else, http and
# https included, is refused before a connection is ever opened.
_ALLOWED_SCHEMES = {"file", "qrc", "data", "blob", "about"}


class LocalOnlyInterceptor(QWebEngineUrlRequestInterceptor):
    """Refuses every request that is not already on this computer."""

    def __init__(self) -> None:
        super().__init__()
        self.blocked: list[str] = []

    def interceptRequest(self, info: QWebEngineUrlRequestInfo) -> None:
        scheme = info.requestUrl().scheme().lower()
        if scheme not in _ALLOWED_SCHEMES:
            self.blocked.append(info.requestUrl().toString())
            info.block(True)


class AppPage(QWebEnginePage):
    """The page. It stays on the one document it was given."""

    def __init__(self, profile: QWebEngineProfile, parent=None) -> None:
        super().__init__(profile, parent)
        self.open_url = None  # set by MainWindow, so links go to the browser

    def acceptNavigationRequest(self, url: QUrl, nav_type, is_main_frame: bool) -> bool:
        if url.scheme() == "file":
            return True
        if self.open_url is not None:
            self.open_url(url.toString())
        return False

    def javaScriptConsoleMessage(self, level, message, line, source) -> None:
        print(f"{__app_name__} ui: {message} ({Path(source).name}:{line})", flush=True)


class WebView(QWebEngineView):
    """The view. Its context menu offers editing and nothing else."""

    def contextMenuEvent(self, event) -> None:
        menu = QMenu(self)
        page = self.page()
        for action_id, label in (
            (QWebEnginePage.WebAction.Cut, "Cut"),
            (QWebEnginePage.WebAction.Copy, "Copy"),
            (QWebEnginePage.WebAction.Paste, "Paste"),
            (QWebEnginePage.WebAction.SelectAll, "Select all"),
        ):
            action = page.action(action_id)
            if action is not None and action.isEnabled():
                action.setText(label)
                menu.addAction(action)
        if menu.actions():
            menu.exec(event.globalPos())
        event.accept()


class MainWindow(QMainWindow):
    """One window, one web view, one channel."""

    def __init__(self, bridge) -> None:
        super().__init__()
        self.setWindowTitle(__app_name__)
        self.setMinimumSize(MIN_WIDTH, MIN_HEIGHT)

        self.profile = QWebEngineProfile("dig", self)
        self.profile.setHttpCacheType(QWebEngineProfile.HttpCacheType.NoCache)
        self.profile.setPersistentCookiesPolicy(
            QWebEngineProfile.PersistentCookiesPolicy.NoPersistentCookies
        )
        self.interceptor = LocalOnlyInterceptor()
        self.profile.setUrlRequestInterceptor(self.interceptor)

        self.page = AppPage(self.profile, self)
        self.page.open_url = bridge.openUrl

        settings = self.page.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, False)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanOpenWindows, False)
        settings.setAttribute(QWebEngineSettings.WebAttribute.ScreenCaptureEnabled, False)
        settings.setAttribute(QWebEngineSettings.WebAttribute.WebGLEnabled, False)
        settings.setAttribute(QWebEngineSettings.WebAttribute.PdfViewerEnabled, False)
        settings.setAttribute(QWebEngineSettings.WebAttribute.ShowScrollBars, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.FocusOnNavigationEnabled, True)

        self.channel = QWebChannel(self)
        self.channel.registerObject("bridge", bridge)
        self.page.setWebChannel(self.channel)

        self.view = WebView(self)
        self.view.setPage(self.page)
        self.setCentralWidget(self.view)

        self.bridge = bridge

    def load_ui(self) -> None:
        index = paths.ui_dir() / "index.html"
        self.view.setUrl(QUrl.fromLocalFile(str(index)))

    # ------------------------------------------------------------- geometry

    def geometry_dict(self) -> dict:
        frame = self.normalGeometry() if not self.isMaximized() else self.geometry()
        return {
            "x": int(frame.x()),
            "y": int(frame.y()),
            "w": int(max(MIN_WIDTH, frame.width())),
            "h": int(max(MIN_HEIGHT, frame.height())),
            "max": bool(self.isMaximized()),
        }

    def apply_geometry(self, saved: dict | None) -> None:
        if not isinstance(saved, dict):
            self.resize(1280, 840)
            return
        try:
            width = max(MIN_WIDTH, int(saved.get("w", 1280)))
            height = max(MIN_HEIGHT, int(saved.get("h", 840)))
        except (TypeError, ValueError):
            width, height = 1280, 840
        self.resize(width, height)
        try:
            x, y = int(saved["x"]), int(saved["y"])
        except (KeyError, TypeError, ValueError):
            pass
        else:
            if _on_a_screen(x, y, width, height):
                self.move(x, y)
        if saved.get("max"):
            self.showMaximized()

    def closeEvent(self, event) -> None:
        self.bridge.flush()
        super().closeEvent(event)


def _on_a_screen(x: int, y: int, width: int, height: int) -> bool:
    """Keep a remembered position from putting the window where nobody can see it."""
    wanted = QRect(x, y, width, height)
    for screen in QGuiApplication.screens():
        if screen.availableGeometry().intersects(wanted):
            return True
    return False
