"""Cross-platform clipboard access.

macOS: Uses AppKit via pyobjc or falls back to subprocess (pbpaste/pbcopy).
Windows: Uses Win32 API via pywin32 or falls back to PowerShell.
"""

import logging
import os
import platform
import struct
import subprocess
import tempfile
from abc import ABC, abstractmethod
from typing import List, Optional
from typing import Tuple

logger = logging.getLogger(__name__)

# Content types
CONTENT_TEXT = "text"
CONTENT_RICH_TEXT = "rich_text"
CONTENT_IMAGE = "image"
CONTENT_FILES = "files"


class ClipboardResult:
    """Result of reading the clipboard."""

    def __init__(
        self,
        content_type: str,
        text: Optional[str] = None,
        rich_text: Optional[str] = None,
        image_data: Optional[bytes] = None,
        image_format: Optional[str] = None,
        file_paths: Optional[List[str]] = None,
    ) -> None:
        self.content_type = content_type
        self.text = text
        self.rich_text = rich_text
        self.image_data = image_data
        self.image_format = image_format  # "png", "tiff", etc.
        self.file_paths = file_paths or []

    def is_empty(self) -> bool:
        if self.content_type == CONTENT_TEXT:
            return not self.text
        if self.content_type == CONTENT_RICH_TEXT:
            return not self.rich_text
        if self.content_type == CONTENT_IMAGE:
            return self.image_data is None
        if self.content_type == CONTENT_FILES:
            return not self.file_paths
        return True


class ClipboardBackend(ABC):
    """Abstract clipboard backend."""

    @abstractmethod
    def read(self) -> Optional[ClipboardResult]:
        """Read current clipboard content."""
        ...

    @abstractmethod
    def write(self, content: ClipboardResult) -> None:
        """Write content to clipboard."""
        ...

    def detect_content_type(self) -> str:
        """Auto-detect clipboard content type."""
        raise NotImplementedError


class MacClipboardBackend(ClipboardBackend):
    """macOS clipboard backed by AppKit (pyobjc) with subprocess fallback."""

    def __init__(self) -> None:
        self._use_native = False
        try:
            from AppKit import NSPasteboard, NSPasteboardTypeString, NSPasteboardTypePNG, NSPasteboardTypeTIFF, NSPasteboardTypeHTML, NSPasteboardTypeFileURL
            self._use_native = True
            self._pb = NSPasteboard.generalPasteboard()
        except ImportError:
            logger.info("pyobjc not available; using subprocess for clipboard")

    def read(self) -> Optional[ClipboardResult]:
        if self._use_native:
            return self._read_native()
        return self._read_subprocess()

    def write(self, content: ClipboardResult) -> None:
        if self._use_native:
            self._write_native(content)
        else:
            self._write_subprocess(content)

    def _read_native(self) -> Optional[ClipboardResult]:
        from AppKit import NSPasteboard, NSPasteboardTypeString, NSPasteboardTypePNG, NSPasteboardTypeTIFF, NSPasteboardTypeHTML, NSURL

        pb = NSPasteboard.generalPasteboard()
        types = pb.types()

        # Check for files
        file_paths = []
        for item in pb.pasteboardItems():
            url_str = item.stringForType_("public.file-url")
            if url_str:
                url = NSURL.URLWithString_(url_str)
                if url and url.path():
                    file_paths.append(url.path())

        if file_paths:
            return ClipboardResult(
                content_type=CONTENT_FILES,
                file_paths=file_paths,
            )

        # Check for image
        for img_type in [NSPasteboardTypePNG, NSPasteboardTypeTIFF]:
            img_data = pb.dataForType_(img_type)
            if img_data:
                fmt = "png" if img_type == NSPasteboardTypePNG else "tiff"
                return ClipboardResult(
                    content_type=CONTENT_IMAGE,
                    image_data=bytes(img_data),
                    image_format=fmt,
                )

        # Check for HTML (rich text)
        html_data = pb.stringForType_("public.html") or pb.stringForType_(NSPasteboardTypeHTML)
        if html_data:
            plain_text = pb.stringForType_(NSPasteboardTypeString) or ""
            return ClipboardResult(
                content_type=CONTENT_RICH_TEXT,
                text=plain_text,
                rich_text=html_data,
            )

        # Plain text
        text = pb.stringForType_(NSPasteboardTypeString)
        if text:
            return ClipboardResult(
                content_type=CONTENT_TEXT,
                text=text,
            )

        return ClipboardResult(content_type=CONTENT_TEXT)

    def _write_native(self, content: ClipboardResult) -> None:
        from AppKit import NSPasteboard, NSPasteboardTypeString, NSPasteboardTypePNG
        pb = NSPasteboard.generalPasteboard()
        pb.clearContents()

        if content.content_type == CONTENT_TEXT and content.text:
            pb.setString_forType_(content.text, NSPasteboardTypeString)

        elif content.content_type == CONTENT_RICH_TEXT and content.rich_text:
            pb.setString_forType_(content.rich_text, NSPasteboardTypeString)

        elif content.content_type == CONTENT_IMAGE and content.image_data:
            from Foundation import NSData
            data = NSData.dataWithBytes_length_(content.image_data, len(content.image_data))
            pb.setData_forType_(data, NSPasteboardTypePNG)

        elif content.content_type == CONTENT_FILES and content.file_paths:
            from Foundation import NSURL
            from AppKit import NSPasteboardTypeFileURL
            pb.clearContents()
            urls = [NSURL.fileURLWithPath_(p) for p in content.file_paths]
            pb.writeObjects_(urls)

    def _read_subprocess(self) -> Optional[ClipboardResult]:
        """Read clipboard using pbpaste and osascript."""
        # Try to detect content type using osascript
        try:
            script = '''
            set theClip to the clipboard as record
            try
                set theTypes to (the clipboard as record)
                return "unknown"
            on error
                try
                    set txt to the clipboard as text
                    return "text"
                on error
                    return "empty"
                end try
            end try
            '''
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True, text=True, timeout=3
            )
            clip_type = result.stdout.strip()
        except Exception:
            clip_type = "unknown"

        # Try text first
        try:
            result = subprocess.run(
                ["pbpaste"],
                capture_output=True, text=True, timeout=3
            )
            if result.stdout:
                return ClipboardResult(
                    content_type=CONTENT_TEXT,
                    text=result.stdout,
                )
        except Exception:
            pass

        # Try image (pbpaste -Prefer ascii doesn't work for images, use osascript)
        try:
            script = '''
            use framework "AppKit"
            set pb to current application's NSPasteboard's generalPasteboard()
            set imgData to pb's dataForType:(current application's NSPasteboardTypePNG)
            if imgData is missing value then
                return ""
            end if
            set tempFile to POSIX path of (current application's NSTemporaryDirectory() as string) & "clipshare_temp.png"
            imgData's writeToFile:tempFile atomically:true
            return tempFile
            '''
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True, text=True, timeout=5
            )
            temp_path = result.stdout.strip()
            if temp_path and os.path.exists(temp_path):
                with open(temp_path, "rb") as f:
                    img_data = f.read()
                os.unlink(temp_path)
                if img_data:
                    return ClipboardResult(
                        content_type=CONTENT_IMAGE,
                        image_data=img_data,
                        image_format="png",
                    )
        except Exception:
            pass

        return ClipboardResult(content_type=CONTENT_TEXT)

    def _write_subprocess(self, content: ClipboardResult) -> None:
        """Write clipboard using pbcopy."""
        if content.content_type in (CONTENT_TEXT, CONTENT_RICH_TEXT):
            text = content.rich_text if content.content_type == CONTENT_RICH_TEXT else content.text
            if text:
                subprocess.run(
                    ["pbcopy"],
                    input=text.encode("utf-8"),
                    timeout=3
                )

        elif content.content_type == CONTENT_IMAGE and content.image_data:
            # Write image to temp file and use osascript to set clipboard
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                f.write(content.image_data)
                temp_path = f.name

            script = f'''
            use framework "AppKit"
            set img to (current application's NSImage's alloc()'s initWithContentsOfFile:"{temp_path}")
            set pb to current application's NSPasteboard's generalPasteboard()
            pb's clearContents()
            pb's writeObjects:{{img}}
            '''
            subprocess.run(
                ["osascript", "-e", script],
                capture_output=True, timeout=5
            )
            os.unlink(temp_path)

        elif content.content_type == CONTENT_FILES:
            # On macOS, writing file paths to clipboard
            paths = "\n".join(content.file_paths)
            subprocess.run(
                ["pbcopy"],
                input=paths.encode("utf-8"),
                timeout=3
            )


class WindowsClipboardBackend(ClipboardBackend):
    """Windows clipboard backed by pywin32 with PowerShell fallback."""

    def __init__(self) -> None:
        self._use_native = False
        try:
            import win32clipboard
            self._use_native = True
        except ImportError:
            logger.info("pywin32 not available; using PowerShell for clipboard")

    def read(self) -> Optional[ClipboardResult]:
        if self._use_native:
            return self._read_native()
        return self._read_powershell()

    def write(self, content: ClipboardResult) -> None:
        if self._use_native:
            self._write_native(content)
        else:
            self._write_powershell(content)

    def _read_native(self) -> Optional[ClipboardResult]:
        import win32clipboard
        from win32clipboard import CF_TEXT, CF_UNICODETEXT, CF_HDROP, CF_DIB

        try:
            win32clipboard.OpenClipboard()

            # Check for files
            try:
                if win32clipboard.IsClipboardFormatAvailable(CF_HDROP):
                    file_paths = win32clipboard.GetClipboardData(CF_HDROP)
                    win32clipboard.CloseClipboard()
                    return ClipboardResult(
                        content_type=CONTENT_FILES,
                        file_paths=list(file_paths),
                    )
            except Exception:
                pass

            # Check for image
            try:
                if win32clipboard.IsClipboardFormatAvailable(CF_DIB):
                    data = win32clipboard.GetClipboardData(CF_DIB)
                    win32clipboard.CloseClipboard()
                    return ClipboardResult(
                        content_type=CONTENT_IMAGE,
                        image_data=data,
                        image_format="dib",
                    )
            except Exception:
                pass

            # Text
            try:
                if win32clipboard.IsClipboardFormatAvailable(CF_UNICODETEXT):
                    text = win32clipboard.GetClipboardData(CF_UNICODETEXT)
                    win32clipboard.CloseClipboard()
                    return ClipboardResult(
                        content_type=CONTENT_TEXT,
                        text=text,
                    )
            except Exception:
                pass

            try:
                if win32clipboard.IsClipboardFormatAvailable(CF_TEXT):
                    text = win32clipboard.GetClipboardData(CF_TEXT)
                    win32clipboard.CloseClipboard()
                    return ClipboardResult(
                        content_type=CONTENT_TEXT,
                        text=text.decode("ascii", errors="replace"),
                    )
            except Exception:
                pass

            win32clipboard.CloseClipboard()
            return ClipboardResult(content_type=CONTENT_TEXT)

        except Exception:
            try:
                win32clipboard.CloseClipboard()
            except Exception:
                pass
            return ClipboardResult(content_type=CONTENT_TEXT)

    def _write_native(self, content: ClipboardResult) -> None:
        import win32clipboard
        from win32clipboard import CF_UNICODETEXT, CF_DIB

        try:
            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()

            if content.content_type in (CONTENT_TEXT, CONTENT_RICH_TEXT):
                text = content.rich_text if content.content_type == CONTENT_RICH_TEXT else content.text
                if text:
                    win32clipboard.SetClipboardText(text, CF_UNICODETEXT)

            elif content.content_type == CONTENT_IMAGE and content.image_data:
                win32clipboard.SetClipboardData(CF_DIB, content.image_data)

            elif content.content_type == CONTENT_FILES:
                from win32clipboard import CF_HDROP
                win32clipboard.SetClipboardData(
                    CF_HDROP,
                    tuple(content.file_paths)
                )

            win32clipboard.CloseClipboard()
        except Exception:
            try:
                win32clipboard.CloseClipboard()
            except Exception:
                pass

    def _read_powershell(self) -> Optional[ClipboardResult]:
        """Fallback: use PowerShell to read clipboard."""
        # Check for files first
        try:
            ps_script = """
            Add-Type -AssemblyName System.Windows.Forms
            $data = [System.Windows.Forms.Clipboard]::GetDataObject()
            if ($data.GetDataPresent([System.Windows.Forms.DataFormats]::FileDrop)) {
                $files = $data.GetData([System.Windows.Forms.DataFormats]::FileDrop)
                $files -join "|"
            } else {
                ""
            }
            """
            result = subprocess.run(
                ["powershell", "-Command", ps_script],
                capture_output=True, text=True, timeout=5
            )
            output = result.stdout.strip()
            if output:
                file_paths = [p for p in output.split("|") if p]
                if file_paths:
                    return ClipboardResult(
                        content_type=CONTENT_FILES,
                        file_paths=file_paths,
                    )
        except Exception:
            pass

        # Try text
        try:
            result = subprocess.run(
                ["powershell", "-Command", "Get-Clipboard"],
                capture_output=True, text=True, timeout=5
            )
            if result.stdout:
                return ClipboardResult(
                    content_type=CONTENT_TEXT,
                    text=result.stdout,
                )
        except Exception:
            pass

        return ClipboardResult(content_type=CONTENT_TEXT)

    def _write_powershell(self, content: ClipboardResult) -> None:
        """Fallback: use PowerShell to write clipboard."""
        if content.content_type in (CONTENT_TEXT, CONTENT_RICH_TEXT):
            text = content.rich_text if content.content_type == CONTENT_RICH_TEXT else content.text
            if text:
                # Escape for PowerShell
                escaped = text.replace("`", "``").replace('"', '`"')
                script = f'Set-Clipboard -Value "{escaped}"'
                subprocess.run(
                    ["powershell", "-Command", script],
                    capture_output=True, timeout=5
                )

        elif content.content_type == CONTENT_IMAGE and content.image_data:
            # Save to temp file and use PowerShell to set clipboard
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                f.write(content.image_data)
                temp_path = f.name

            script = f"""
            Add-Type -AssemblyName System.Windows.Forms
            Add-Type -AssemblyName System.Drawing
            $img = [System.Drawing.Image]::FromFile('{temp_path}')
            [System.Windows.Forms.Clipboard]::SetImage($img)
            $img.Dispose()
            """
            subprocess.run(
                ["powershell", "-Command", script],
                capture_output=True, timeout=5
            )
            os.unlink(temp_path)


def get_clipboard_backend() -> ClipboardBackend:
    """Factory: return the appropriate clipboard backend for the current OS."""
    system = platform.system()
    if system == "Darwin":
        return MacClipboardBackend()
    elif system == "Windows":
        return WindowsClipboardBackend()
    else:
        raise RuntimeError(f"Unsupported platform: {system}")