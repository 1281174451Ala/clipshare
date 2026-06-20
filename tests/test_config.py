"""Unit tests for the config module."""
import sys
import os
import json
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from clipshare.config import Config


class TestConfig:
    """Tests for Config class."""

    def test_default_device_name(self):
        """Test default device name - uses hostname when no config."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            c = Config()
            c._config_dir = tmp
            c._config_path = tmp / "config.json"
            c._data = {}
            name = c.get_device_name()
            assert isinstance(name, str) and len(name) > 0

    def test_set_and_get_device_name(self):
        """Test setting and getting device name."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            c = Config()
            c._config_dir = tmp
            c._config_path = tmp / "config.json"
            c._data = {}
            
            c.set_device_name("my-macbook")
            assert c.get_device_name() == "my-macbook"

    def test_paired_devices_crud(self):
        """Test paired device CRUD operations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            c = Config()
            c._config_dir = tmp
            c._config_path = tmp / "config.json"
            c._data = {}

            c.add_paired_device("device-1", "aes-key-1")
            assert c.is_paired("device-1")
            assert c.get_aes_key("device-1") == "aes-key-1"

            c.add_paired_device("device-2", "aes-key-2")
            assert len(c.get_paired_devices()) == 2

            c.remove_paired_device("device-1")
            assert not c.is_paired("device-1")
            assert c.is_paired("device-2")

            c.remove_paired_device("non-existent")

    def test_private_key(self):
        """Test private key storage."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            c = Config()
            c._config_dir = tmp
            c._config_path = tmp / "config.json"
            c._data = {}

            assert c.get_private_key() is None

            c.set_private_key("dh-private-key-b64")
            assert c.get_private_key() == "dh-private-key-b64"

    def test_persistence(self):
        """Test config persistence across instances."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            config_path = tmp / "config.json"
            
            c1 = Config()
            c1._config_dir = tmp
            c1._config_path = config_path
            c1._data = {}
            c1.set_device_name("persistent-device")
            c1.add_paired_device("dev-a", "key-a")
            c1.set_private_key("priv-key")
            c1._save()

            c2 = Config()
            c2._config_dir = tmp
            c2._config_path = config_path
            c2._data = {}
            c2._load()
            
            assert c2.get_device_name() == "persistent-device"
            assert c2.is_paired("dev-a")
            assert c2.get_aes_key("dev-a") == "key-a"
            assert c2.get_private_key() == "priv-key"