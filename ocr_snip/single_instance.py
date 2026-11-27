"""Cross-platform single-instance application guard using user-scoped Qt local sockets."""

from __future__ import annotations

import getpass
import hashlib
import logging

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtNetwork import QLocalServer, QLocalSocket

logger = logging.getLogger("ocr_snip.single_instance")

ALLOWED_COMMANDS: frozenset[str] = frozenset({"SNIP"})
MAX_IPC_PAYLOAD_BYTES = 64


def default_server_name() -> str:
    """Return a per-user local socket name to prevent cross-user collisions/squatting."""
    try:
        user = getpass.getuser()
    except Exception:
        user = "default"
    digest = hashlib.sha256(user.encode("utf-8")).hexdigest()[:12]
    return f"OCRSnippingTool_v1_{digest}"


class SingleInstanceGuard(QObject):
    """Ensures only one desktop tray instance runs per user at a time.

    Enforces OS-level current-user-only socket permissions (`UserAccessOption`),
    bounded IPC payload size, and strict command allowlisting.
    """

    activate_requested = pyqtSignal(str)  # validated command payload, e.g. "SNIP"

    def __init__(
        self,
        server_name: str | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.server_name = server_name or default_server_name()
        self._server: QLocalServer | None = None

    def try_notify_existing(self, command: str = "SNIP", timeout_ms: int = 350) -> bool:
        """Return True if an existing instance is running and acknowledged our command."""
        cmd = command if command in ALLOWED_COMMANDS else "SNIP"
        socket = QLocalSocket(self)
        socket.connectToServer(self.server_name)
        if not socket.waitForConnected(timeout_ms):
            socket.abort()
            return False

        try:
            socket.write(cmd.encode("utf-8"))
            socket.flush()
            socket.waitForBytesWritten(timeout_ms)
        finally:
            socket.disconnectFromServer()
        logger.info("Notified existing instance (%s) with command %r", self.server_name, cmd)
        return True

    def start_listening(self) -> bool:
        """Bind a user-only local socket server for this primary instance."""
        self.stop()
        QLocalServer.removeServer(self.server_name)

        server = QLocalServer(self)
        # Restrict access to the current OS user only (Unix permissions / Windows DACL)
        server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
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
            try:
                client.waitForReadyRead(300)
                raw = bytes(client.read(MAX_IPC_PAYLOAD_BYTES))
                payload = raw.decode("utf-8", errors="ignore").strip()
            finally:
                client.disconnectFromServer()
                client.deleteLater()

            if payload not in ALLOWED_COMMANDS:
                logger.warning("Ignored unrecognized IPC payload: %r", payload[:32])
                continue

            logger.info("Received activation command from secondary launch: %r", payload)
            self.activate_requested.emit(payload)
