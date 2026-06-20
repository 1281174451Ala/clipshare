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


def _get_pid_file() -> str:
    """Get PID file path, using config directory with fallback."""
    home_pid = os.path.join(os.path.expanduser("~"), ".clipshare", "clipshare.pid")
    try:
        os.makedirs(os.path.dirname(home_pid), exist_ok=True)
        # Test if writable
        test_file = os.path.join(os.path.dirname(home_pid), ".test_write")
        with open(test_file, "w") as f:
            f.write("test")
        os.remove(test_file)
        return home_pid
    except OSError:
        return os.path.join(os.getcwd(), "clipshare.pid")


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
        """Start all services in background."""
        pid_file = _get_pid_file()
        # Check if already running
        if os.path.exists(pid_file):
            with open(pid_file, "r") as f:
                old_pid = f.read().strip()
            try:
                old_pid_int = int(old_pid)
                os.kill(old_pid_int, 0)
                print(f"Clipshare is already running (PID: {old_pid})")
                return
            except (OSError, ValueError):
                try:
                    os.remove(pid_file)
                except OSError:
                    pass

        # Start as background subprocess
        import subprocess

        # Build command for daemon mode
        if getattr(sys, 'frozen', False):
            # PyInstaller binary
            cmd = [sys.executable, "--daemon"]
        else:
            # Running from source
            cmd = [sys.executable, "-m", "clipshare", "--daemon"]

        # Start the daemon process
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
        )

        # Wait briefly and check if it's still running
        time.sleep(1)

        if proc.poll() is not None:
            # Process exited immediately - read error
            stderr = proc.stderr.read().decode("utf-8", errors="replace").strip()
            if stderr:
                print(f"Failed to start: {stderr}")
            else:
                print("Failed to start daemon process.")
            return

        # Write PID file
        pid_file = _get_pid_file()
        try:
            os.makedirs(os.path.dirname(pid_file), exist_ok=True)
            with open(pid_file, "w") as f:
                f.write(str(proc.pid))
        except OSError:
            pass

        print(f"Clipshare started in background (device: {self.config.get_device_name()})")
        print(f"Listening on port {DEFAULT_PORT}")
        print(f"PID: {proc.pid}")

    def run_daemon(self) -> None:
        """Run the daemon in foreground (called when --daemon flag is passed)."""
        self._running = True

        # Write PID file
        pid_file = _get_pid_file()
        try:
            os.makedirs(os.path.dirname(pid_file), exist_ok=True)
            with open(pid_file, "w") as f:
                f.write(str(os.getpid()))
        except OSError:
            pass

        try:
            self.discovery.start()
            self.sync.start()
        except OSError as e:
            print(f"Failed to start: {e}", file=sys.stderr)
            try:
                os.remove(pid_file)
            except OSError:
                pass
            sys.exit(1)

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
        pid_file = _get_pid_file()
        if os.path.exists(pid_file):
            try:
                os.remove(pid_file)
            except OSError:
                pass

        print("Clipshare stopped.")

    def list_devices(self) -> None:
        """List all discovered devices."""
        # Start a quick discovery scan
        print("Scanning for devices...")
        try:
            self.discovery.start()
            time.sleep(3)  # Wait for broadcasts
        except OSError:
            # Port already in use - daemon may be running
            pass
        devices = self.discovery.get_devices()
        try:
            self.discovery.stop()
        except Exception:
            pass

        if not devices:
            print("No devices found on the network.")
            print("\nTroubleshooting:")
            print("  1. Ensure clipshare is running on the other device")
            print("  2. Check both devices are on the same WiFi/network")
            print("  3. Check firewall allows UDP port 19206 and TCP port 19205")
            print("  4. Some routers block broadcast - try disabling AP isolation")
            return

        print(f"\n{'Device Name':<20} {'IP Address':<18} {'Status':<12}")
        print("-" * 50)

        paired = self.config.get_paired_devices()
        for device in devices:
            status = "paired" if device.device_id in paired else "unpaired"
            print(f"{device.device_name:<20} {device.ip_address:<18} {status:<12}")

    def pair(self, device_name: str) -> None:
        """Pair with a device by name."""
        # Quick scan first
        print("Scanning for devices...")
        try:
            self.discovery.start()
            time.sleep(3)
        except OSError:
            pass
        device = self.discovery.get_device_by_name(device_name)
        try:
            self.discovery.stop()
        except Exception:
            pass

        if not device:
            print(f"Device '{device_name}' not found online.")
            print("Run 'clipshare list' to see available devices.")
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
        pid_file = _get_pid_file()
        is_running = False
        pid = ""
        if os.path.exists(pid_file):
            with open(pid_file, "r") as f:
                pid = f.read().strip()
            try:
                os.kill(int(pid), 0)
                is_running = True
            except (OSError, ValueError):
                pass

        print(f"Device Name: {self.config.get_device_name()}")
        print(f"Status: {'Running' if is_running else 'Stopped'}")
        if is_running:
            print(f"PID: {pid}")

        paired = self.config.get_paired_devices()
        print(f"Paired Devices: {len(paired)}")
        for device_id in paired:
            print(f"  - {device_id}")

    def stop_daemon(self) -> None:
        """Stop the daemon process by PID file."""
        pid_file = _get_pid_file()
        if not os.path.exists(pid_file):
            print("No running Clipshare daemon found.")
            return

        with open(pid_file, "r") as f:
            pid = f.read().strip()

        try:
            pid_int = int(pid)
            os.kill(pid_int, signal.SIGTERM)
            print(f"Sent stop signal to Clipshare daemon (PID: {pid})")
        except ProcessLookupError:
            print("Daemon not running. Cleaning up PID file.")
        except Exception as e:
            print(f"Failed to stop daemon: {e}")

        # Clean up PID file
        try:
            os.remove(pid_file)
        except OSError:
            pass

    def handle_pairing_request(self, sock: socket.socket) -> None:
        """Handle incoming pairing request (called from sync engine)."""
        # This is handled by the sync engine's server
        pass