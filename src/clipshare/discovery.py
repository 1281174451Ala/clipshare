"""Device discovery via UDP broadcast."""

import json
import logging
import socket
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from typing import Tuple

from .constants import (
    DEFAULT_BROADCAST_PORT,
    BROADCAST_INTERVAL,
    HEARTBEAT_TIMEOUT,
    DEFAULT_PORT,
)

logger = logging.getLogger(__name__)


@dataclass
class DeviceInfo:
    """Represents a discovered device on the network."""
    device_name: str
    ip_address: str
    tcp_port: int
    public_key: str
    last_seen: float = field(default_factory=time.time)

    @property
    def device_id(self) -> str:
        """Unique identifier for the device based on IP and port."""
        return f"{self.ip_address}:{self.tcp_port}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "device_name": self.device_name,
            "ip_address": self.ip_address,
            "tcp_port": self.tcp_port,
            "public_key": self.public_key,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], last_seen: float = None) -> "DeviceInfo":
        return cls(
            device_name=data["device_name"],
            ip_address=data["ip_address"],
            tcp_port=data.get("tcp_port", DEFAULT_PORT),
            public_key=data["public_key"],
            last_seen=last_seen or time.time(),
        )


class DeviceDiscovery:
    """Manages device discovery via UDP broadcast."""

    def __init__(
        self,
        device_name: str,
        public_key: str,
        broadcast_port: int = DEFAULT_BROADCAST_PORT,
        tcp_port: int = DEFAULT_PORT,
    ) -> None:
        self.device_name = device_name
        self.public_key = public_key
        self.broadcast_port = broadcast_port
        self.tcp_port = tcp_port

        self._devices: Dict[str, DeviceInfo] = {}
        self._lock = threading.Lock()
        self._running = False
        self._broadcast_thread: Optional[threading.Thread] = None
        self._listen_thread: Optional[threading.Thread] = None
        self._cleanup_thread: Optional[threading.Thread] = None

        self._broadcast_socket: Optional[socket.socket] = None
        self._listen_socket: Optional[socket.socket] = None

    def get_devices(self) -> List[DeviceInfo]:
        """Get all discovered devices sorted by last seen time."""
        with self._lock:
            sorted_devices = sorted(
                self._devices.values(),
                key=lambda d: d.last_seen,
                reverse=True,
            )
            return list(sorted_devices)

    def get_device(self, device_id: str) -> Optional[DeviceInfo]:
        """Get a specific device by device_id."""
        with self._lock:
            return self._devices.get(device_id)

    def get_device_by_name(self, name: str) -> Optional[DeviceInfo]:
        """Get a device by name (returns first match)."""
        with self._lock:
            for device in self._devices.values():
                if device.device_name == name:
                    return device
            return None

    def update_device_name(self, new_name: str) -> None:
        """Update local device name."""
        self.device_name = new_name

    def _send_broadcast(self) -> None:
        """Send broadcast announcement."""
        if not self._broadcast_socket:
            return

        message = json.dumps({
            "type": "announce",
            "device_name": self.device_name,
            "tcp_port": self.tcp_port,
            "public_key": self.public_key,
        }).encode("utf-8")

        try:
            self._broadcast_socket.sendto(
                message,
                ("255.255.255.255", self.broadcast_port)
            )
        except Exception as e:
            logger.warning(f"Failed to send broadcast: {e}")

    def _broadcast_loop(self) -> None:
        """Periodic broadcast loop."""
        while self._running:
            self._send_broadcast()
            time.sleep(BROADCAST_INTERVAL)

    def _listen_loop(self) -> None:
        """Listen for incoming announcements from other devices."""
        while self._running:
            try:
                data, (addr, port) = self._listen_socket.recvfrom(4096)
                if addr is None:
                    continue

                try:
                    msg = json.loads(data.decode("utf-8"))
                except json.JSONDecodeError:
                    continue

                if msg.get("type") not in ("announce", "response"):
                    continue

                device_info = DeviceInfo(
                    device_name=msg.get("device_name", "unknown"),
                    ip_address=addr,
                    tcp_port=msg.get("tcp_port", DEFAULT_PORT),
                    public_key=msg.get("public_key", ""),
                    last_seen=time.time(),
                )

                with self._lock:
                    self._devices[device_info.device_id] = device_info

                # If it's an announce, send a response back
                if msg["type"] == "announce":
                    response = json.dumps({
                        "type": "response",
                        "device_name": self.device_name,
                        "tcp_port": self.tcp_port,
                        "public_key": self.public_key,
                    }).encode("utf-8")
                    try:
                        self._broadcast_socket.sendto(response, (addr, self.broadcast_port))
                    except Exception:
                        pass

            except socket.timeout:
                continue
            except Exception as e:
                if self._running:
                    logger.warning(f"Error in listen loop: {e}")
                time.sleep(0.1)

    def _cleanup_loop(self) -> None:
        """Cleanup devices that have been offline for too long."""
        while self._running:
            now = time.time()
            to_remove: List[str] = []

            with self._lock:
                for device_id, device in self._devices.items():
                    if now - device.last_seen > HEARTBEAT_TIMEOUT:
                        to_remove.append(device_id)

                for device_id in to_remove:
                    if device_id in self._devices:
                        logger.info(f"Removing offline device {device_id}")
                        del self._devices[device_id]

            time.sleep(HEARTBEAT_TIMEOUT)

    def start(self) -> None:
        """Start discovery threads."""
        if self._running:
            return

        self._running = True

        # Create broadcast socket
        self._broadcast_socket = socket.socket(
            socket.AF_INET,
            socket.SOCK_DGRAM,
            socket.IPPROTO_UDP
        )
        self._broadcast_socket.setsockopt(
            socket.SOL_SOCKET,
            socket.SO_BROADCAST,
            1
        )
        self._broadcast_socket.settimeout(1.0)

        # Create listen socket
        self._listen_socket = socket.socket(
            socket.AF_INET,
            socket.SOCK_DGRAM,
            socket.IPPROTO_UDP
        )
        self._listen_socket.setsockopt(
            socket.SOL_SOCKET,
            socket.SO_REUSEADDR,
            1
        )
        # Allow multiple processes to bind (macOS/Linux)
        if hasattr(socket, 'SO_REUSEPORT'):
            try:
                self._listen_socket.setsockopt(
                    socket.SOL_SOCKET,
                    socket.SO_REUSEPORT,
                    1
                )
            except OSError:
                pass
        self._listen_socket.bind(
            ("0.0.0.0", self.broadcast_port)
        )
        self._listen_socket.settimeout(1.0)

        # Start threads
        self._broadcast_thread = threading.Thread(
            target=self._broadcast_loop,
            daemon=True,
        )
        self._listen_thread = threading.Thread(
            target=self._listen_loop,
            daemon=True,
        )
        self._cleanup_thread = threading.Thread(
            target=self._cleanup_loop,
            daemon=True,
        )

        self._broadcast_thread.start()
        self._listen_thread.start()
        self._cleanup_thread.start()

        logger.info("Device discovery started")

    def stop(self) -> None:
        """Stop all discovery threads and close sockets."""
        self._running = False

        if self._broadcast_socket:
            try:
                self._broadcast_socket.close()
            except Exception:
                pass
            self._broadcast_socket = None

        if self._listen_socket:
            try:
                self._listen_socket.close()
            except Exception:
                pass
            self._listen_socket = None

        for thread in [self._broadcast_thread, self._listen_thread, self._cleanup_thread]:
            if thread and thread.is_alive():
                thread.join(timeout=2.0)

        logger.info("Device discovery stopped")

    @property
    def is_running(self) -> bool:
        return self._running