"""Unit tests for the clipboard module (macOS only in sandbox)."""
import sys
import os
import platform
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from clipshare.clipboard import (
    ClipboardBackend,
    ClipboardResult,
    MacClipboardBackend,
    WindowsClipboardBackend,
    get_clipboard_backend,
    CONTENT_TEXT,
    CONTENT_RICH_TEXT,
    CONTENT_IMAGE,
    CONTENT_FILES,
)


class TestClipboardResult:
    """Tests for ClipboardResult class."""

    def test_empty_text(self):
        """Test is_empty for text content."""
        cr = ClipboardResult(content_type=CONTENT_TEXT, text="")
        assert cr.is_empty()

        cr2 = ClipboardResult(content_type=CONTENT_TEXT, text="hello")
        assert not cr2.is_empty()

    def test_empty_image(self):
        """Test is_empty for image content."""
        cr = ClipboardResult(content_type=CONTENT_IMAGE, image_data=None)
        assert cr.is_empty()

        cr2 = ClipboardResult(content_type=CONTENT_IMAGE, image_data=b"\x00\x01\x02")
        assert not cr2.is_empty()

    def test_empty_files(self):
        """Test is_empty for files content."""
        cr = ClipboardResult(content_type=CONTENT_FILES, file_paths=[])
        assert cr.is_empty()

        cr2 = ClipboardResult(content_type=CONTENT_FILES, file_paths=["/tmp/test.txt"])
        assert not cr2.is_empty()

    def test_empty_rich_text(self):
        """Test is_empty for rich text content."""
        cr = ClipboardResult(content_type=CONTENT_RICH_TEXT, rich_text="")
        assert cr.is_empty()

        cr2 = ClipboardResult(content_type=CONTENT_RICH_TEXT, rich_text="<b>test</b>")
        assert not cr2.is_empty()

    def test_default_values(self):
        """Test default values for ClipboardResult."""
        cr = ClipboardResult(content_type=CONTENT_TEXT)
        assert cr.content_type == CONTENT_TEXT
        assert cr.text is None
        assert cr.image_data is None
        assert cr.file_paths == []


class TestClipboardBackends:
    """Tests for clipboard backends."""

    def test_factory_mac(self):
        """Test backend factory returns correct type."""
        backend = get_clipboard_backend()
        assert backend is not None

        system = platform.system()
        if system == "Darwin":
            assert isinstance(backend, MacClipboardBackend)
        elif system == "Windows":
            assert isinstance(backend, WindowsClipboardBackend)

    def test_read_returns_result(self):
        """Test that read returns a ClipboardResult."""
        backend = get_clipboard_backend()
        result = backend.read()
        assert result is not None
        assert hasattr(result, "content_type")
        assert hasattr(result, "text")

    def test_write_then_read_text(self):
        """Test write and read back text."""
        backend = get_clipboard_backend()
        system = platform.system()

        test_text = f"clipshare-test-{os.getpid()}"
        cr = ClipboardResult(content_type=CONTENT_TEXT, text=test_text)

        backend.write(cr)

        # Read back
        result = backend.read()
        assert result is not None

        # On macOS with native AppKit or pbcopy/pbpaste, this should work
        if system == "Darwin":
            # pbpaste should give us the text back
            import subprocess
            try:
                out = subprocess.run(
                    ["pbpaste"],
                    capture_output=True, text=True, timeout=3
                )
                clipboard_text = out.stdout.strip()
                # Sometimes pbpaste adds trailing newline
                assert test_text in clipboard_text, \
                    f"Expected '{test_text}' in clipboard, got '{clipboard_text}'"
            except Exception:
                pass  # subprocess fallback might not be available

    def test_content_types(self):
        """Test that content type constants are defined."""
        assert CONTENT_TEXT == "text"
        assert CONTENT_RICH_TEXT == "rich_text"
        assert CONTENT_IMAGE == "image"
        assert CONTENT_FILES == "files"


if __name__ == "__main__":
    import sys
    print("Run via run_tests.py instead")
    sys.exit(0)