"""Unit tests for the discovery module."""
import sys
import os
import time
import socket
import threading
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from clipshare.discovery import DeviceDiscovery, DeviceInfo
from clipshare.crypto import generate_dh_keypair
from clipshare.constants import DEFAULT_BROADCAST_PORT, DEFAULT_PORT


class TestDeviceInfo:
    """Tests for DeviceInfo dataclass."""

    def test_device_id(self):
        """Test device_id generation."""
        di = DeviceInfo(
            device_name="test-device",
            ip_address="192.168.1.100",
            tcp_port=19205,
            public_key="fake-key",
        )
        assert di.device_id == "192.168.1.100:19205"

    def test_to_dict(self):
        """Test serialization to dict."""
        di = DeviceInfo(
            device_name="test-device",
            ip_address="192.168.1.100",
            tcp_port=19205,
            public_key="fake-key",
        )
        d = di.to_dict()
        assert d["device_name"] == "test-device"
        assert d["ip_address"] == "192.168.1.100"
        assert d["tcp_port"] == 19205
        assert d["public_key"] == "fake-key"

    def test_from_dict(self):
        """Test deserialization from dict."""
        data = {
            "device_name": "test-device",
            "ip_address": "192.168.1.100",
            "tcp_port": 19205,
            "public_key": "fake-key",
        }
        di = DeviceInfo.from_dict(data)
        assert di.device_name == "test-device"
        assert di.ip_address == "192.168.1.100"
        assert di.tcp_port == 19205

    def test_default_tcp_port(self):
        """Test default TCP port in from_dict."""
        data = {
            "device_name": "test",
            "ip_address": "10.0.0.1",
            "public_key": "key",
        }
        di = DeviceInfo.from_dict(data)
        assert di.tcp_port == DEFAULT_PORT


class TestDeviceDiscovery:
    """Tests for DeviceDiscovery class."""

    def test_start_stop(self):
        """Test discovery start and stop."""
        priv, pub = generate_dh_keypair()
        dd = DeviceDiscovery(
            device_name="test-device",
            public_key=pub,
            broadcast_port=DEFAULT_BROADCAST_PORT + 100,  # different port for test
        )

        assert not dd.is_running
        dd.start()
        time.sleep(0.3)
        assert dd.is_running
        dd.stop()
        time.sleep(0.3)
        assert not dd.is_running

    def test_get_devices_empty(self):
        """Test that get_devices returns empty list initially."""
        priv, pub = generate_dh_keypair()
        dd = DeviceDiscovery(
            device_name="test-device",
            public_key=pub,
            broadcast_port=DEFAULT_BROADCAST_PORT + 101,
        )
        dd.start()
        time.sleep(0.3)
        devices = dd.get_devices()
        assert isinstance(devices, list)
        dd.stop()

    def test_update_device_name(self):
        """Test updating device name."""
        priv, pub = generate_dh_keypair()
        dd = DeviceDiscovery(
            device_name="old-name",
            public_key=pub,
            broadcast_port=DEFAULT_BROADCAST_PORT + 102,
        )
        assert dd.device_name == "old-name"
        dd.update_device_name("new-name")
        assert dd.device_name == "new-name"

    def test_get_device(self):
        """Test getting device by ID."""
        priv, pub = generate_dh_keypair()
        dd = DeviceDiscovery(
            device_name="test-device",
            public_key=pub,
            broadcast_port=DEFAULT_BROADCAST_PORT + 103,
        )

        result = dd.get_device("non-existent")
        assert result is None

    def test_get_device_by_name(self):
        """Test getting device by name."""
        priv, pub = generate_dh_keypair()
        dd = DeviceDiscovery(
            device_name="test-device",
            public_key=pub,
            broadcast_port=DEFAULT_BROADCAST_PORT + 104,
        )

        result = dd.get_device_by_name("non-existent")
        assert result is None

    def test_start_already_running(self):
        """Test starting when already running (no double start)."""
        priv, pub = generate_dh_keypair()
        dd = DeviceDiscovery(
            device_name="test-device",
            public_key=pub,
            broadcast_port=DEFAULT_BROADCAST_PORT + 105,
        )

        dd.start()
        time.sleep(0.2)
        dd.start()  # should be no-op
        time.sleep(0.2)
        assert dd.is_running
        dd.stop()

    def test_stop_not_running(self):
        """Test stopping when not running (no error)."""
        priv, pub = generate_dh_keypair()
        dd = DeviceDiscovery(
            device_name="test-device",
            public_key=pub,
            broadcast_port=DEFAULT_BROADCAST_PORT + 106,
        )

        dd.stop()  # should not raise
        assert not dd.is_running

    def test_discovery_between_two_instances(self):
        """Test that two discovery instances can discover each other.

        Note: This test may fail on a single machine due to port conflicts,
        since both instances try to bind the same port. In real usage,
        instances run on different machines so this is not an issue.
        """
        import random
        priv_a, pub_a = generate_dh_keypair()
        priv_b, pub_b = generate_dh_keypair()

        # Use a random high port to minimize conflicts
        port = 40000 + random.randint(0, 5000)

        dd_a = DeviceDiscovery(
            device_name="device-A",
            public_key=pub_a,
            broadcast_port=port,
        )

        try:
            dd_a.start()
        except OSError as e:
            if "Address already in use" in str(e):
                print("  SKIP (port conflict on single machine)")
                return
            raise

        try:
            dd_b = DeviceDiscovery(
                device_name="device-B",
                public_key=pub_b,
                broadcast_port=port,
            )
            dd_b.start()
        except OSError as e:
            dd_a.stop()
            if "Address already in use" in str(e):
                print("  SKIP (port conflict on single machine)")
                return
            raise

        # Wait for broadcasts
        time.sleep(1.5)

        devices_a = dd_a.get_devices()
        devices_b = dd_b.get_devices()

        dd_a.stop()
        dd_b.stop()

        # Each should discover the other
        names_a = [d.device_name for d in devices_a]
        names_b = [d.device_name for d in devices_b]

        assert "device-B" in names_a, f"Device-A should discover Device-B, found: {names_a}"
        assert "device-A" in names_b, f"Device-B should discover Device-A, found: {names_b}"


if __name__ == "__main__":
    import sys
    print("Run via run_tests.py instead")
    sys.exit(0)