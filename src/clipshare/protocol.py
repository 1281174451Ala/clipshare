"""Wire protocol for clipshare messages over TCP."""

import json
import struct
from typing import Any, Dict, List, Optional
from typing import Tuple


# Message types
MSG_PAIR_REQUEST = "pair_request"
MSG_PAIR_RESPONSE = "pair_response"
MSG_CLIPBOARD_SYNC = "clipboard_sync"
MSG_FILE_CHUNK = "file_chunk"
MSG_FILE_DONE = "file_done"
MSG_ERROR = "error"


class Message:
    """Base message with type and payload."""

    def __init__(self, msg_type: str, payload: Dict[str, Any]) -> None:
        self.msg_type = msg_type
        self.payload = payload

    def to_json(self) -> bytes:
        data = json.dumps({
            "type": self.msg_type,
            "payload": self.payload,
        }).encode("utf-8")
        # Prepend 4-byte length
        return struct.pack("!I", len(data)) + data

    @classmethod
    def from_json(cls, data: bytes) -> "Message":
        msg = json.loads(data.decode("utf-8"))
        return cls(msg_type=msg["type"], payload=msg["payload"])


def encode_clipboard_content(content: "ClipboardResult") -> Dict[str, Any]:
    """Encode ClipboardResult to a dict for serialization."""
    from .clipboard import CONTENT_TEXT, CONTENT_RICH_TEXT, CONTENT_IMAGE, CONTENT_FILES
    import base64

    result: Dict[str, Any] = {
        "content_type": content.content_type,
    }

    if content.content_type == CONTENT_TEXT:
        result["text"] = content.text
    elif content.content_type == CONTENT_RICH_TEXT:
        result["text"] = content.text
        result["rich_text"] = content.rich_text
    elif content.content_type == CONTENT_IMAGE:
        if content.image_data:
            result["image_data"] = base64.b64encode(content.image_data).decode("utf-8")
            result["image_format"] = content.image_format
    elif content.content_type == CONTENT_FILES:
        result["file_paths"] = content.file_paths
        result["file_count"] = len(content.file_paths) if content.file_paths else 0

    return result


def decode_clipboard_content(data: Dict[str, Any]) -> "ClipboardResult":
    """Decode dict to ClipboardResult."""
    from .clipboard import ClipboardResult
    import base64

    content_type = data["content_type"]
    result = ClipboardResult(content_type=content_type)

    if content_type == "text":
        result.text = data.get("text")
    elif content_type == "rich_text":
        result.text = data.get("text")
        result.rich_text = data.get("rich_text")
    elif content_type == "image":
        img_b64 = data.get("image_data")
        if img_b64:
            result.image_data = base64.b64decode(img_b64)
            result.image_format = data.get("image_format", "png")
    elif content_type == "files":
        result.file_paths = data.get("file_paths", [])

    return result