"""Cross-platform single-instance application guard using Qt local sockets."""

from __future__ import annotations

import logging

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtNetwork import QLocalServer, QLocalSocket

logger = logging.getLogger("ocr_snip.single_instance")

DEFAULT_SERVER_NAME = "OCRSnippingTool_SingleInstance_v1"


class SingleInstanceGuard(QObject):
    """Ensures only one desktop tray instance runs at a time.

    When a second instance starts (e.g. double-clicking the .exe while already
    running in the system tray), it notifies the primary instance over a local
    socket/named pipe so the primary instance immediately triggers a new snip.
    """

    activate_requested = pyqtSignal(str)  # command payload, e.g. "SNIP"

    def __init__(
        self,
        server_name: str = DEFAULT_SERVER_NAME,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.server_name = server_name
        self._server: QLocalServer | None = None

    def try_notify_existing(self, command: str = "SNIP", timeout_ms: int = 350) -> bool:
        """Return True if an existing instance is running and acknowledged our command."""
        socket = QLocalSocket(self)
        socket.connectToServer(self.server_name)
        if not socket.waitForConnected(timeout_ms):
            socket.abort()
            return False

        try:
            socket.write(command.encode("utf-8"))
            socket.flush()
            socket.waitForBytesWritten(timeout_ms)
        finally:
            socket.disconnectFromServer()
        logger.info("Notified existing instance (%s) with command %r", self.server_name, command)
        return True

    def start_listening(self) -> bool:
        """Bind the local socket server for this primary instance."""
        self.stop()
        # Clean up stale socket left behind if a previous process crashed
        QLocalServer.removeServer(self.server_name)

        server = QLocalServer(self)
        if not server.listen(self.server_name):
            logger.warning(
                "Could not start single-instance server %s: %s",
                self.server_name,
                server.errorString(),
            )
            return False

        server.newConnection.connect(self._handle_new_connection)
        self._server = server
        logger.info("Single-instance guard listening on %s", self.server_name)
        return True

    def stop(self) -> None:
        """Close the local socket server cleanly."""
        if self._server is not None:
            try:
                self._server.close()
            except Exception:
                pass
            self._server = None
            QLocalServer.removeServer(self.server_name)

    def _handle_new_connection(self) -> None:
        if self._server is None:
            return
        while self._server.hasPendingConnections():
            client = self._server.nextPendingConnection()
            if client is None:
                continue
            client.waitForReadyRead(300)
            payload = bytes(client.readAll()).decode("utf-8", errors="ignore").strip() or "SNIP"
            client.disconnectFromServer()
            client.deleteLater()
            logger.info("Received activation command from secondary launch: %r", payload)
            self.activate_requested.emit(payload)
