import json
import os
import socket
from pathlib import Path
from typing import Optional

from .constants import CONFIG_DIR_NAME, CONFIG_FILE_NAME


class Config:
    """Manages local configuration: device name, paired devices, keys."""

    def __init__(self, config_dir: Optional[str] = None) -> None:
        if config_dir:
            self._config_dir = Path(config_dir)
        else:
            self._config_dir = Path.home() / CONFIG_DIR_NAME
        self._config_path = self._config_dir / CONFIG_FILE_NAME
        self._data: dict = {}
        self._load()

    def _load(self) -> None:
        try:
            self._config_dir.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            self._fallback_config()

        # Verify the directory is writable
        if not os.access(self._config_dir, os.W_OK):
            self._fallback_config()

        if self._config_path.exists():
            with open(self._config_path, "r", encoding="utf-8") as f:
                self._data = json.load(f)
        else:
            self._data = {}

    def _fallback_config(self) -> None:
        """Fallback to current working directory if home dir is not writable."""
        fallback = Path.cwd() / CONFIG_DIR_NAME
        fallback.mkdir(parents=True, exist_ok=True)
        self._config_dir = fallback
        self._config_path = fallback / CONFIG_FILE_NAME

    def _save(self) -> None:
        try:
            self._config_dir.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            pass
        with open(self._config_path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2, ensure_ascii=False)

    def get_device_name(self) -> str:
        return self._data.get("device_name", socket.gethostname())

    def set_device_name(self, name: str) -> None:
        self._data["device_name"] = name
        self._save()

    def get_private_key(self) -> Optional[str]:
        return self._data.get("private_key")

    def set_private_key(self, key: str) -> None:
        self._data["private_key"] = key
        self._save()

    def get_paired_devices(self) -> dict:
        return self._data.get("paired_devices", {})

    def add_paired_device(self, device_id: str, aes_key: str) -> None:
        paired = self._data.get("paired_devices", {})
        paired[device_id] = aes_key
        self._data["paired_devices"] = paired
        self._save()

    def remove_paired_device(self, device_id: str) -> None:
        paired = self._data.get("paired_devices", {})
        if device_id in paired:
            del paired[device_id]
            self._data["paired_devices"] = paired
            self._save()

    def is_paired(self, device_id: str) -> bool:
        return device_id in self.get_paired_devices()

    def get_aes_key(self, device_id: str) -> Optional[str]:
        return self.get_paired_devices().get(device_id)

    @property
    def config_path(self) -> Path:
        return self._config_path