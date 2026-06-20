"""Sync engine: clipboard monitoring + TCP server/client for content sync."""

import logging
import os
import socket
import struct
import threading
import time
from typing import Any, Dict, List, Optional
from typing import Tuple

from .clipboard import (
    ClipboardBackend,
    ClipboardResult,
    CONTENT_TEXT,
    CONTENT_RICH_TEXT,
    CONTENT_IMAGE,
    CONTENT_FILES,
    get_clipboard_backend,
)
from .config import Config
from .constants import (
    DEFAULT_PORT,
    CLIPBOARD_POLL_INTERVAL,
    FILE_CHUNK_SIZE,
    MAX_FILE_SIZE,
)
from .crypto import encrypt_data, decrypt_data
from .discovery import DeviceDiscovery, DeviceInfo
from .protocol import (
    Message,
    MSG_PAIR_REQUEST,
    MSG_PAIR_RESPONSE,
    MSG_CLIPBOARD_SYNC,
    MSG_FILE_CHUNK,
    MSG_FILE_DONE,
    MSG_ERROR,
    encode_clipboard_content,
    decode_clipboard_content,
)

logger = logging.getLogger(__name__)


class SyncEngine:
    """Main engine that watches clipboard and syncs to paired devices."""

    def __init__(
        self,
        config: Config,
        discovery: DeviceDiscovery,
        clipboard: ClipboardBackend,
    ) -> None:
        self.config = config
        self.discovery = discovery
        self.clipboard = clipboard

        self._running = False
        self._server_thread: Optional[threading.Thread] = None
        self._monitor_thread: Optional[threading.Thread] = None
        self._server_socket: Optional[socket.socket] = None
        self._last_hash: Optional[str] = None
        self._sent_by_me: bool = False  # flag to prevent echo-back
        self._lock = threading.Lock()

    def _compute_hash(self, content: ClipboardResult) -> Optional[str]:
        """Compute a simple hash to detect clipboard changes."""
        import hashlib

        if content.content_type == CONTENT_TEXT:
            return hashlib.sha256(content.text.encode("utf-8")).hexdigest()
        elif content.content_type == CONTENT_RICH_TEXT:
            data = (content.rich_text or "").encode("utf-8")
            return hashlib.sha256(data).hexdigest()
        elif content.content_type == CONTENT_IMAGE:
            return hashlib.sha256(content.image_data or b"").hexdigest()
        elif content.content_type == CONTENT_FILES:
            paths = "\n".join(content.file_paths or []).encode("utf-8")
            return hashlib.sha256(paths).hexdigest()
        return None

    def _send_to_device(self, device: DeviceInfo, aes_key_b64: str, message: Message) -> bool:
        """Send an encrypted message to a paired device."""
        try:
            aes_key = self.config.get_aes_key(device.device_id)
            if not aes_key:
                logger.warning(f"No AES key for {device.device_id}")
                return False

            import base64
            key_bytes = base64.b64decode(aes_key)
            plaintext = message.to_json()
            encrypted = encrypt_data(key_bytes, plaintext)

            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10)
            sock.connect((device.ip_address, device.tcp_port))

            # Send 4-byte length + encrypted data
            sock.sendall(struct.pack("!I", len(encrypted)) + encrypted)
            sock.close()
            return True
        except Exception as e:
            logger.warning(f"Failed to send to {device.device_name}: {e}")
            return False

    def _broadcast_clipboard(self, content: ClipboardResult) -> None:
        """Send clipboard content to all paired devices."""
        if content.is_empty():
            return

        paired_devices = self.config.get_paired_devices()
        devices = self.discovery.get_devices()

        content_data = encode_clipboard_content(content)
        msg = Message(MSG_CLIPBOARD_SYNC, {"content": content_data})

        sent_count = 0
        for device in devices:
            if device.device_id in paired_devices:
                success = self._send_to_device(device, "", msg)
                if success:
                    sent_count += 1

        if sent_count > 0:
            logger.info(f"Clipboard sync sent to {sent_count} device(s)")

    def _send_file_to_device(self, device: DeviceInfo, file_path: str) -> bool:
        """Send a file directly to a device."""
        try:
            if not os.path.isfile(file_path):
                return False

            file_size = os.path.getsize(file_path)
            if file_size > MAX_FILE_SIZE:
                logger.warning(f"File too large: {file_path} ({file_size} bytes)")
                return False

            filename = os.path.basename(file_path)
            aes_key = self.config.get_aes_key(device.device_id)
            if not aes_key:
                return False

            import base64
            key_bytes = base64.b64decode(aes_key)

            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(60)
            sock.connect((device.ip_address, device.tcp_port))

            with open(file_path, "rb") as f:
                seq = 0
                while True:
                    chunk = f.read(FILE_CHUNK_SIZE)
                    is_last = len(chunk) < FILE_CHUNK_SIZE

                    msg = Message(MSG_FILE_CHUNK, {
                        "filename": filename,
                        "seq": seq,
                        "data": base64.b64encode(chunk).decode("utf-8"),
                        "is_last": is_last,
                    })

                    encrypted = encrypt_data(key_bytes, msg.to_json())
                    sock.sendall(struct.pack("!I", len(encrypted)) + encrypted)

                    if is_last:
                        break
                    seq += 1

            sock.close()
            logger.info(f"File {filename} sent to {device.device_name}")
            return True
        except Exception as e:
            logger.warning(f"Failed to send file to {device.device_name}: {e}")
            return False

    def _monitor_loop(self) -> None:
        """Poll clipboard for changes and broadcast to paired devices."""
        logger.info("Clipboard monitor started")
        while self._running:
            try:
                content = self.clipboard.read()
                if content is None:
                    time.sleep(CLIPBOARD_POLL_INTERVAL)
                    continue

                current_hash = self._compute_hash(content)
                if current_hash and current_hash != self._last_hash:
                    with self._lock:
                        if self._sent_by_me:
                            self._sent_by_me = False
                            self._last_hash = current_hash
                        else:
                            self._last_hash = current_hash
                            # Broadcast to paired devices
                            if content.content_type == CONTENT_FILES:
                                # Send file list first, then files
                                self._broadcast_clipboard(content)
                                # Then send actual files
                                devices = self.discovery.get_devices()
                                paired = self.config.get_paired_devices()
                                for device in devices:
                                    if device.device_id in paired:
                                        for fp in (content.file_paths or []):
                                            self._send_file_to_device(device, fp)
                            else:
                                self._broadcast_clipboard(content)

                time.sleep(CLIPBOARD_POLL_INTERVAL)
            except Exception as e:
                logger.warning(f"Monitor error: {e}")
                time.sleep(CLIPBOARD_POLL_INTERVAL)

    def _handle_client(self, client_sock: socket.socket, addr: Tuple[str, int]) -> None:
        """Handle incoming TCP connection from another device."""
        try:
            # Read 4-byte length prefix
            length_data = client_sock.recv(4)
            if len(length_data) < 4:
                return
            msg_length = struct.unpack("!I", length_data)[0]

            if msg_length > 10 * 1024 * 1024:  # 10MB sanity check
                logger.warning(f"Message too large from {addr}: {msg_length}")
                return

            # Read the full message
            data = b""
            while len(data) < msg_length:
                chunk = client_sock.recv(min(msg_length - len(data), 65536))
                if not chunk:
                    break
                data += chunk

            if len(data) < msg_length:
                return

            # Try to parse as plaintext first (pairing requests are unencrypted)
            try:
                msg = Message.from_json(data)
                if msg.msg_type == MSG_PAIR_REQUEST:
                    self._handle_pairing_request(client_sock, addr, msg)
                    return
            except Exception:
                pass  # Not plaintext, try encrypted

            # Try to decrypt with paired device keys
            paired = self.config.get_paired_devices()
            device_id = f"{addr[0]}:{DEFAULT_PORT}"
            aes_key_b64 = paired.get(device_id)

            if not aes_key_b64:
                for did, key in paired.items():
                    if did.startswith(f"{addr[0]}:"):
                        device_id = did
                        aes_key_b64 = key
                        break

            if not aes_key_b64:
                logger.warning(f"Received data from unpaired device: {addr}")
                return

            import base64
            key_bytes = base64.b64decode(aes_key_b64)
            plaintext = decrypt_data(key_bytes, data)
            msg = Message.from_json(plaintext)

            self._process_message(msg, device_id)

        except Exception as e:
            logger.warning(f"Error handling client {addr}: {e}")
        finally:
            try:
                client_sock.close()
            except Exception:
                pass

    def _handle_pairing_request(self, client_sock: socket.socket, addr: Tuple[str, int], msg: Message) -> None:
        """Handle an incoming pairing request."""
        peer_name = msg.payload.get("device_name", "unknown")
        peer_public_key = msg.payload.get("public_key", "")

        logger.info(f"Pairing request from {peer_name} ({addr[0]})")

        # Auto-accept pairing (in production, this would prompt the user)
        print(f"\n[Clipshare] Pairing request from '{peer_name}' ({addr[0]}) - auto-accepted")

        import base64
        from .crypto import compute_shared_secret

        # Compute shared secret
        our_private_key = self.config.get_private_key()
        if not our_private_key:
            logger.error("No private key for pairing")
            return

        shared_secret = compute_shared_secret(our_private_key, peer_public_key)
        aes_key_b64 = base64.b64encode(shared_secret).decode("utf-8")

        device_id = f"{addr[0]}:{DEFAULT_PORT}"
        self.config.add_paired_device(device_id, aes_key_b64)

        # Send acceptance response
        our_public_key = self._derive_public_key()
        response = Message(MSG_PAIR_RESPONSE, {
            "accepted": True,
            "device_name": self.config.get_device_name(),
            "public_key": our_public_key,
        })

        try:
            client_sock.sendall(response.to_json())
            logger.info(f"Paired with {peer_name} ({device_id})")
            print(f"[Clipshare] Successfully paired with '{peer_name}'")
        except Exception as e:
            logger.warning(f"Failed to send pair response: {e}")

    def _derive_public_key(self) -> str:
        """Derive public key from stored private key."""
        import base64
        from .crypto import DH_PRIME, DH_GENERATOR
        priv = self.config.get_private_key()
        if not priv:
            return ""
        try:
            private_key_bytes = base64.b64decode(priv)
            private_key_int = int.from_bytes(private_key_bytes, "big")
            public_key_int = pow(DH_GENERATOR, private_key_int, DH_PRIME)
            return base64.b64encode(public_key_int.to_bytes(256, "big")).decode("utf-8")
        except Exception:
            return ""

    def _process_message(self, msg: Message, device_id: str) -> None:
        """Process a received message."""
        payload = msg.payload

        if msg.msg_type == MSG_CLIPBOARD_SYNC:
            content_data = payload.get("content", {})
            content = decode_clipboard_content(content_data)

            with self._lock:
                self._sent_by_me = True
                self.clipboard.write(content)

            logger.info(f"Clipboard updated from {device_id}")

        elif msg.msg_type == MSG_FILE_CHUNK:
            filename = payload.get("filename", "unknown")
            is_last = payload.get("is_last", False)
            data_b64 = payload.get("data", "")

            import base64
            data = base64.b64decode(data_b64)

            # Save to temp dir
            temp_dir = os.path.join(os.path.expanduser("~"), ".clipshare", "files")
            os.makedirs(temp_dir, exist_ok=True)
            file_path = os.path.join(temp_dir, filename)

            mode = "ab" if os.path.exists(file_path) else "wb"
            with open(file_path, mode) as f:
                f.write(data)

            if is_last:
                logger.info(f"File received: {file_path}")
                # Write file path to clipboard
                file_result = ClipboardResult(
                    content_type=CONTENT_FILES,
                    file_paths=[file_path],
                )
                with self._lock:
                    self._sent_by_me = True
                    self.clipboard.write(file_result)

        elif msg.msg_type == MSG_ERROR:
            logger.error(f"Error from {device_id}: {payload.get('message', '')}")

    def _server_loop(self) -> None:
        """TCP server that accepts connections from paired devices."""
        if not self._server_socket:
            logger.error("Server socket not initialized")
            return

        logger.info(f"Sync server listening on port {DEFAULT_PORT}")

        while self._running:
            try:
                client_sock, addr = self._server_socket.accept()
                thread = threading.Thread(
                    target=self._handle_client,
                    args=(client_sock, addr),
                    daemon=True,
                )
                thread.start()
            except socket.timeout:
                continue
            except Exception as e:
                if self._running:
                    logger.warning(f"Server accept error: {e}")

        logger.info("Sync server stopped")

    def start(self) -> None:
        """Start the sync engine."""
        if self._running:
            return

        # Bind TCP socket synchronously so errors propagate immediately
        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_socket.bind(("0.0.0.0", DEFAULT_PORT))
        self._server_socket.listen(10)
        self._server_socket.settimeout(1.0)

        self._running = True

        # Start TCP server accept loop
        self._server_thread = threading.Thread(
            target=self._server_loop,
            daemon=True,
        )
        self._server_thread.start()

        # Start clipboard monitor
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True,
        )
        self._monitor_thread.start()

        logger.info("Sync engine started")

    def stop(self) -> None:
        """Stop the sync engine."""
        self._running = False

        if self._server_socket:
            try:
                self._server_socket.close()
            except Exception:
                pass
            self._server_socket = None

        for thread in [self._server_thread, self._monitor_thread]:
            if thread and thread.is_alive():
                thread.join(timeout=3.0)

        logger.info("Sync engine stopped")

    @property
    def is_running(self) -> bool:
        return self._running