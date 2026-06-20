"""Quick smoke test for core modules (stdlib only)."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from clipshare.config import Config
from clipshare.constants import DEFAULT_PORT, BROADCAST_INTERVAL, HEARTBEAT_TIMEOUT
from clipshare.protocol import Message, encode_clipboard_content, decode_clipboard_content, MSG_CLIPBOARD_SYNC
from clipshare.crypto import generate_dh_keypair, compute_shared_secret, aes_key_to_base64, aes_key_from_base64

print("All stdlib modules imported OK")

# --- Config ---
c = Config()
print(f"Config path: {c.config_path}")
print(f"Device name: {c.get_device_name()}")

c.set_device_name("test-device")
assert c.get_device_name() == "test-device", "set_device_name failed"
print("Config: set/get device name OK")

c.set_private_key("test-private-key-b64")
assert c.get_private_key() == "test-private-key-b64", "set_private_key failed"
print("Config: set/get private key OK")

c.add_paired_device("192.168.1.100:19205", "test-aes-key")
assert c.is_paired("192.168.1.100:19205"), "add_paired_device failed"
assert c.get_aes_key("192.168.1.100:19205") == "test-aes-key"
print("Config: paired device management OK")

c.remove_paired_device("192.168.1.100:19205")
assert not c.is_paired("192.168.1.100:19205"), "remove_paired_device failed"
print("Config: remove paired device OK")

c.set_device_name("")  # reset
print()

# --- DH Key Exchange ---
priv1, pub1 = generate_dh_keypair()
priv2, pub2 = generate_dh_keypair()

print(f"DH keypair 1: priv={priv1[:20]}..., pub={pub1[:20]}...")
print(f"DH keypair 2: priv={priv2[:20]}..., pub={pub2[:20]}...")

secret1 = compute_shared_secret(priv1, pub2)
secret2 = compute_shared_secret(priv2, pub1)

assert secret1 == secret2, "DH shared secrets don't match!"
print(f"DH key exchange OK, shared secret length: {len(secret1)} bytes")

# Ensure different keypairs produce different secrets
priv3, pub3 = generate_dh_keypair()
secret3 = compute_shared_secret(priv1, pub3)
assert secret3 != secret1, "Different DH keypairs should produce different secrets"
print("DH uniqueness check OK")
print()

# --- Protocol ---
from clipshare.clipboard import ClipboardResult, CONTENT_TEXT, CONTENT_RICH_TEXT, CONTENT_IMAGE, CONTENT_FILES

# Text
cr = ClipboardResult(content_type=CONTENT_TEXT, text="hello world")
encoded = encode_clipboard_content(cr)
decoded = decode_clipboard_content(encoded)
assert decoded.text == "hello world"
assert decoded.content_type == CONTENT_TEXT
print("Protocol: text encode/decode OK")

# Rich text
cr_rt = ClipboardResult(content_type=CONTENT_RICH_TEXT, text="plain", rich_text="<b>bold</b>")
encoded_rt = encode_clipboard_content(cr_rt)
decoded_rt = decode_clipboard_content(encoded_rt)
assert decoded_rt.text == "plain"
assert decoded_rt.rich_text == "<b>bold</b>"
print("Protocol: rich text encode/decode OK")

# Image
import base64
fake_img = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
cr_img = ClipboardResult(content_type=CONTENT_IMAGE, image_data=fake_img, image_format="png")
encoded_img = encode_clipboard_content(cr_img)
decoded_img = decode_clipboard_content(encoded_img)
assert decoded_img.image_data == fake_img
assert decoded_img.image_format == "png"
print("Protocol: image encode/decode OK")

# Files
cr_files = ClipboardResult(content_type=CONTENT_FILES, file_paths=["/tmp/a.txt", "/tmp/b.txt"])
encoded_files = encode_clipboard_content(cr_files)
decoded_files = decode_clipboard_content(encoded_files)
assert decoded_files.file_paths == ["/tmp/a.txt", "/tmp/b.txt"]
print("Protocol: files encode/decode OK")

# Message serialization
msg_data = encode_clipboard_content(cr)
msg = Message(MSG_CLIPBOARD_SYNC, {"content": msg_data})
raw = msg.to_json()
assert len(raw) > 4  # length prefix
parsed = Message.from_json(raw[4:])  # skip length prefix
assert parsed.msg_type == MSG_CLIPBOARD_SYNC
content = decode_clipboard_content(parsed.payload["content"])
assert content.text == "hello world"
print("Protocol: message serialize/deserialize OK")
print()

# --- Discovery ---
import time
from clipshare.discovery import DeviceDiscovery

priv, pub = generate_dh_keypair()
dd = DeviceDiscovery(device_name="test-device", public_key=pub)
assert not dd.is_running
dd.start()
time.sleep(0.5)
assert dd.is_running
devices = dd.get_devices()
print(f"Discovery: started OK, {len(devices)} devices found (expected 0 in isolated env)")
dd.stop()
time.sleep(0.5)
assert not dd.is_running
print("Discovery: start/stop OK")
print()

# --- Clipboard backend factory ---
from clipshare.clipboard import get_clipboard_backend, MacClipboardBackend, WindowsClipboardBackend
import platform
backend = get_clipboard_backend()
system = platform.system()
if system == "Darwin":
    assert isinstance(backend, MacClipboardBackend), "Expected MacClipboardBackend on macOS"
    print(f"Clipboard: correct backend for {system} (MacClipboardBackend)")
elif system == "Windows":
    assert isinstance(backend, WindowsClipboardBackend), "Expected WindowsClipboardBackend on Windows"
    print(f"Clipboard: correct backend for {system} (WindowsClipboardBackend)")
else:
    print(f"Clipboard: platform {system} (no native backend check)")

# Test clipboard read (should return something, even if empty)
result = backend.read()
assert result is not None, "clipboard read should return a result"
print(f"Clipboard: read OK, content_type={result.content_type}")
print()

# --- Constants ---
assert DEFAULT_PORT == 19205
assert BROADCAST_INTERVAL == 5
assert HEARTBEAT_TIMEOUT == 15
print("Constants: all values verified")
print()

print("=" * 50)
print("ALL SMOKE TESTS PASSED")
print("=" * 50)