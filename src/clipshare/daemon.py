"""Daemon process that runs the clipboard sync service."""

import json
import logging
import os
import signal
import socket
import struct
import sys
import threading
import time
from typing import Optional

from .clipboard import get_clipboard_backend
from .config import Config
from .constants import DEFAULT_PORT
from .crypto import generate_dh_keypair
from .discovery import DeviceDiscovery
from .protocol import (
    Message,
    MSG_PAIR_REQUEST,
    MSG_PAIR_RESPONSE,
    MSG_ERROR,
)
from .sync import SyncEngine

logger = logging.getLogger(__name__)

# PID file for daemon management
PID_FILE = os.path.join(os.path.expanduser("~"), ".clipshare", "clipshare.pid")


class Daemon:
    """Main daemon that orchestrates all components."""

    def __init__(self) -> None:
        self.config = Config()
        self._ensure_keys()
        self.discovery = DeviceDiscovery(
            device_name=self.config.get_device_name(),
            public_key=self._get_public_key(),
        )
        self.clipboard = get_clipboard_backend()
        self.sync = SyncEngine(self.config, self.discovery, self.clipboard)
        self._running = False

    def _ensure_keys(self) -> None:
        """Generate DH keypair if not already present or invalid."""
        priv = self.config.get_private_key()
        if not priv or not self._is_valid_key(priv):
            priv, pub = generate_dh_keypair()
            self.config.set_private_key(priv)
            logger.info("Generated new DH keypair")

    def _is_valid_key(self, key: str) -> bool:
        """Check if a stored private key is valid base64."""
        import base64
        try:
            decoded = base64.b64decode(key)
            return len(decoded) == 256  # DH_KEY_SIZE * 8
        except Exception:
            return False

    def _get_public_key(self) -> str:
        """Derive public key from stored private key."""
        import base64
        from .crypto import DH_PRIME, DH_GENERATOR
        priv = self.config.get_private_key()
        if not priv:
            raise RuntimeError("No private key found")
        private_key_bytes = base64.b64decode(priv)
        private_key_int = int.from_bytes(private_key_bytes, "big")
        public_key_int = pow(DH_GENERATOR, private_key_int, DH_PRIME)
        return base64.b64encode(public_key_int.to_bytes(256, "big")).decode("utf-8")

    def start(self) -> None:
        """Start all services."""
        if self._running:
            print("Clipshare is already running.")
            return

        # Check if already running
        if os.path.exists(PID_FILE):
            with open(PID_FILE, "r") as f:
                old_pid = f.read().strip()
            try:
                old_pid_int = int(old_pid)
                os.kill(old_pid_int, 0)
                print(f"Clipshare is already running (PID: {old_pid})")
                return
            except (OSError, ValueError):
                # Stale PID file
                os.remove(PID_FILE)

        self._running = True

        # Write PID file
        os.makedirs(os.path.dirname(PID_FILE), exist_ok=True)
        with open(PID_FILE, "w") as f:
            f.write(str(os.getpid()))

        self.discovery.start()
        self.sync.start()

        print(f"Clipshare started (device: {self.config.get_device_name()})")
        print(f"Listening on port {DEFAULT_PORT}")
        print(f"PID: {os.getpid()}")

        # Keep running
        try:
            while self._running:
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop()

    def stop(self) -> None:
        """Stop all services."""
        if not self._running:
            print("Stopping Clipshare...")

        self._running = False
        self.sync.stop()
        self.discovery.stop()

        # Remove PID file
        if os.path.exists(PID_FILE):
            os.remove(PID_FILE)

        print("Clipshare stopped.")

    def list_devices(self) -> None:
        """List all discovered devices."""
        # Send a quick status request to the daemon if running
        devices = self.discovery.get_devices()

        if not devices:
            print("No devices found on the network.")
            return

        print(f"{'Device Name':<20} {'IP Address':<18} {'Status':<12}")
        print("-" * 50)

        paired = self.config.get_paired_devices()
        for device in devices:
            status = "paired" if device.device_id in paired else "unpaired"
            print(f"{device.device_name:<20} {device.ip_address:<18} {status:<12}")

    def pair(self, device_name: str) -> None:
        """Pair with a device by name."""
        device = self.discovery.get_device_by_name(device_name)
        if not device:
            print(f"Device '{device_name}' not found online.")
            return

        if self.config.is_paired(device.device_id):
            print(f"Already paired with '{device_name}'.")
            return

        print(f"Pairing with '{device_name}' ({device.ip_address})...")

        # Send pairing request via TCP
        import base64
        from .crypto import compute_shared_secret

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10)
            sock.connect((device.ip_address, device.tcp_port))

            # Send pair request with our public key
            msg = Message(MSG_PAIR_REQUEST, {
                "device_name": self.config.get_device_name(),
                "public_key": self._get_public_key(),
            })
            raw = msg.to_json()
            sock.sendall(raw)

            # Wait for response
            length_data = sock.recv(4)
            if len(length_data) < 4:
                print("Failed to receive response.")
                sock.close()
                return

            msg_length = struct.unpack("!I", length_data)[0]
            data = b""
            while len(data) < msg_length:
                chunk = sock.recv(min(msg_length - len(data), 65536))
                if not chunk:
                    break
                data += chunk

            sock.close()
            response = Message.from_json(data)

            if response.msg_type == MSG_PAIR_RESPONSE:
                accepted = response.payload.get("accepted", False)
                if accepted:
                    # Compute shared secret
                    peer_public_key = response.payload.get("public_key", "")
                    our_private_key = self.config.get_private_key()
                    shared_secret = compute_shared_secret(our_private_key, peer_public_key)
                    aes_key_b64 = base64.b64encode(shared_secret).decode("utf-8")

                    self.config.add_paired_device(device.device_id, aes_key_b64)
                    print(f"Successfully paired with '{device_name}'!")
                else:
                    print(f"Pairing rejected by '{device_name}'.")
            elif response.msg_type == MSG_ERROR:
                print(f"Error: {response.payload.get('message', 'Unknown error')}")
            else:
                print(f"Unexpected response from '{device_name}'.")

        except socket.timeout:
            print("Connection timed out.")
        except ConnectionRefusedError:
            print("Connection refused. Make sure the target device is running Clipshare.")
        except Exception as e:
            print(f"Failed to pair: {e}")

    def set_name(self, new_name: str) -> None:
        """Set local device name."""
        self.config.set_device_name(new_name)
        self.discovery.update_device_name(new_name)
        print(f"Device name set to '{new_name}'.")

    def status(self) -> None:
        """Show daemon status."""
        is_running = False
        if os.path.exists(PID_FILE):
            with open(PID_FILE, "r") as f:
                old_pid = f.read().strip()
            try:
                os.kill(int(old_pid), 0)
                is_running = True
            except (OSError, ValueError):
                pass

        print(f"Device Name: {self.config.get_device_name()}")
        print(f"Status: {'Running' if is_running else 'Stopped'}")
        if is_running:
            with open(PID_FILE, "r") as f:
                print(f"PID: {f.read().strip()}")

        paired = self.config.get_paired_devices()
        print(f"Paired Devices: {len(paired)}")
        for device_id in paired:
            print(f"  - {device_id}")

    def stop_daemon(self) -> None:
        """Stop the daemon process by PID file."""
        if not os.path.exists(PID_FILE):
            print("No running Clipshare daemon found.")
            return

        with open(PID_FILE, "r") as f:
            pid = f.read().strip()

        try:
            pid_int = int(pid)
            os.kill(pid_int, signal.SIGTERM)
            print(f"Sent stop signal to Clipshare daemon (PID: {pid})")
        except ProcessLookupError:
            print("Daemon not running. Cleaning up PID file.")
            os.remove(PID_FILE)
        except Exception as e:
            print(f"Failed to stop daemon: {e}")

    def handle_pairing_request(self, sock: socket.socket) -> None:
        """Handle incoming pairing request (called from sync engine)."""
        # This is handled by the sync engine's server
        pass