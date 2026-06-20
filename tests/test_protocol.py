"""Unit tests for the protocol module."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from clipshare.protocol import (
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
from clipshare.clipboard import (
    ClipboardResult,
    CONTENT_TEXT,
    CONTENT_RICH_TEXT,
    CONTENT_IMAGE,
    CONTENT_FILES,
)


class TestMessage:
    """Tests for Message serialization."""

    def test_message_roundtrip(self):
        """Test message serialize/deserialize."""
        msg = Message(MSG_CLIPBOARD_SYNC, {"text": "hello"})
        raw = msg.to_json()

        # First 4 bytes should be length prefix
        assert len(raw) >= 4

        # Parse back
        parsed = Message.from_json(raw[4:])
        assert parsed.msg_type == MSG_CLIPBOARD_SYNC
        assert parsed.payload["text"] == "hello"

    def test_all_message_types(self):
        """Test all message types can be serialized."""
        types = [MSG_PAIR_REQUEST, MSG_PAIR_RESPONSE, MSG_CLIPBOARD_SYNC,
                 MSG_FILE_CHUNK, MSG_FILE_DONE, MSG_ERROR]

        for msg_type in types:
            msg = Message(msg_type, {"test": "data"})
            raw = msg.to_json()
            parsed = Message.from_json(raw[4:])
            assert parsed.msg_type == msg_type

    def test_empty_payload(self):
        """Test message with empty payload."""
        msg = Message(MSG_ERROR, {})
        raw = msg.to_json()
        parsed = Message.from_json(raw[4:])
        assert parsed.msg_type == MSG_ERROR
        assert parsed.payload == {}

    def test_complex_payload(self):
        """Test message with nested payload."""
        payload = {
            "nested": {
                "key1": "value1",
                "key2": [1, 2, 3],
                "key3": {"deep": True},
            },
            "list": ["a", "b", "c"],
        }
        msg = Message(MSG_CLIPBOARD_SYNC, payload)
        raw = msg.to_json()
        parsed = Message.from_json(raw[4:])
        assert parsed.payload == payload


class TestClipboardEncoding:
    """Tests for clipboard content encoding/decoding."""

    def test_text_encode_decode(self):
        """Test plain text encoding."""
        cr = ClipboardResult(content_type=CONTENT_TEXT, text="Hello World")
        encoded = encode_clipboard_content(cr)
        decoded = decode_clipboard_content(encoded)
        assert decoded.content_type == CONTENT_TEXT
        assert decoded.text == "Hello World"

    def test_empty_text(self):
        """Test empty text."""
        cr = ClipboardResult(content_type=CONTENT_TEXT, text="")
        encoded = encode_clipboard_content(cr)
        decoded = decode_clipboard_content(encoded)
        assert decoded.text == ""

    def test_unicode_text(self):
        """Test unicode text."""
        cr = ClipboardResult(content_type=CONTENT_TEXT, text="你好世界 🎉")
        encoded = encode_clipboard_content(cr)
        decoded = decode_clipboard_content(encoded)
        assert decoded.text == "你好世界 🎉"

    def test_rich_text_encode_decode(self):
        """Test rich text encoding."""
        cr = ClipboardResult(
            content_type=CONTENT_RICH_TEXT,
            text="plain text",
            rich_text="<html><b>bold</b></html>"
        )
        encoded = encode_clipboard_content(cr)
        decoded = decode_clipboard_content(encoded)
        assert decoded.content_type == CONTENT_RICH_TEXT
        assert decoded.text == "plain text"
        assert decoded.rich_text == "<html><b>bold</b></html>"

    def test_image_encode_decode(self):
        """Test image encoding."""
        import base64
        fake_png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 200
        cr = ClipboardResult(
            content_type=CONTENT_IMAGE,
            image_data=fake_png,
            image_format="png"
        )
        encoded = encode_clipboard_content(cr)
        decoded = decode_clipboard_content(encoded)
        assert decoded.content_type == CONTENT_IMAGE
        assert decoded.image_data == fake_png
        assert decoded.image_format == "png"

    def test_files_encode_decode(self):
        """Test files encoding."""
        files = ["/Users/test/file1.txt", "/Users/test/file2.jpg"]
        cr = ClipboardResult(
            content_type=CONTENT_FILES,
            file_paths=files
        )
        encoded = encode_clipboard_content(cr)
        decoded = decode_clipboard_content(encoded)
        assert decoded.content_type == CONTENT_FILES
        assert decoded.file_paths == files

    def test_empty_files(self):
        """Test empty file list."""
        cr = ClipboardResult(content_type=CONTENT_FILES, file_paths=[])
        encoded = encode_clipboard_content(cr)
        decoded = decode_clipboard_content(encoded)
        assert decoded.file_paths == []


if __name__ == "__main__":
    import sys
    print("Run via run_tests.py instead")
    sys.exit(0)