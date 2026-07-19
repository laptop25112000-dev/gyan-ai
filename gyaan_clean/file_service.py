import base64
import csv
import gzip
import io
import mimetypes
import os
import re
import zipfile
import zlib
from html.parser import HTMLParser


MAX_FILES = 8
MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_TEXT_CHARS = 12000
MAX_ARCHIVE_MEMBERS = 40


class _HTMLTextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        text = data.strip()
        if text:
            self.parts.append(text)

    def text(self):
        return " ".join(self.parts)


def normalize_attachments(raw_attachments):
    attachments = []
    errors = []

    if not raw_attachments:
        return attachments, errors
    if not isinstance(raw_attachments, list):
        return attachments, ["Attachments must be a list."]

    for index, item in enumerate(raw_attachments[:MAX_FILES], start=1):
        if not isinstance(item, dict):
            errors.append(f"Attachment {index} was ignored because it was not an object.")
            continue

        name = _safe_name(item.get("name") or f"attachment-{index}")
        mime_type = (item.get("type") or mimetypes.guess_type(name)[0] or "application/octet-stream").strip()
        data_url = item.get("data") or ""

        try:
            payload = _decode_data_url(data_url)
        except ValueError as exc:
            errors.append(f"{name}: {exc}")
            continue

        if len(payload) > MAX_FILE_BYTES:
            errors.append(f"{name}: file is larger than {MAX_FILE_BYTES // (1024 * 1024)} MB.")
            continue

        attachments.append(_summarize_file(name, mime_type, payload))

    if len(raw_attachments) > MAX_FILES:
        errors.append(f"Only the first {MAX_FILES} files were attached.")

    return attachments, errors


def build_file_context(attachments, errors=None):
    if not attachments and not errors:
        return ""

    lines = ["ATTACHED FILE CONTEXT:"]
    for attachment in attachments:
        lines.extend(
            [
                "",
                f"File: {attachment['name']}",
                f"Type: {attachment['type']}",
                f"Size: {attachment['size']} bytes",
                f"Kind: {attachment['kind']}",
                f"Summary: {attachment['summary']}",
            ]
        )
        if attachment.get("preview"):
            lines.extend(["Preview:", attachment["preview"]])

    if errors:
        lines.extend(["", "Attachment warnings:"])
        lines.extend(f"- {error}" for error in errors)

    return "\n".join(lines)


def public_attachment_summary(attachments, errors=None):
    return {
        "files": [
            {
                "name": attachment["name"],
                "type": attachment["type"],
                "size": attachment["size"],
                "kind": attachment["kind"],
                "summary": attachment["summary"],
            }
            for attachment in attachments
        ],
        "warnings": errors or [],
    }


def _safe_name(name):
    return os.path.basename(str(name)).strip() or "attachment"


def _decode_data_url(data_url):
    if not isinstance(data_url, str) or not data_url:
        raise ValueError("missing file data.")
    if "," in data_url and data_url.split(",", 1)[0].startswith("data:"):
        data_url = data_url.split(",", 1)[1]
    try:
        return base64.b64decode(data_url, validate=True)
    except Exception as exc:
        raise ValueError("file data was not valid base64.") from exc


def _summarize_file(name, mime_type, payload):
    lower_name = name.lower()
    kind = "binary"
    summary = "Binary file attached. The model can use its name, type, and size."
    preview = ""

    if zipfile.is_zipfile(io.BytesIO(payload)):
        kind, summary, preview = _summarize_zip(name, payload)
    elif lower_name.endswith(".gz") or mime_type == "application/gzip":
        kind, summary, preview = _summarize_gzip(payload)
    elif mime_type.startswith("image/"):
        kind = "image"
        summary = "Image attached. Pixel-level vision is not available in this Groq text pipeline, so only metadata is supplied."
    elif mime_type.startswith("audio/"):
        kind = "audio"
        summary = "Audio file attached. Transcription is not available in this text pipeline, so only metadata is supplied."
    elif mime_type.startswith("video/"):
        kind = "video"
        summary = "Video file attached. Frame/audio analysis is not available in this text pipeline, so only metadata is supplied."
    elif mime_type == "application/pdf" or lower_name.endswith(".pdf"):
        kind, summary, preview = _summarize_pdf(payload)
    else:
        text = _decode_text(payload)
        if text is not None:
            kind = "text"
            preview = _prepare_text_preview(name, mime_type, text)
            summary = f"Text content extracted, preview limited to {MAX_TEXT_CHARS} characters."

    return {
        "name": name,
        "type": mime_type,
        "size": len(payload),
        "kind": kind,
        "summary": summary,
        "preview": preview,
    }


def _decode_text(payload):
    if b"\x00" in payload[:4096]:
        return None

    for encoding in ("utf-8", "utf-16", "cp1252", "latin-1"):
        try:
            return payload.decode(encoding)
        except UnicodeDecodeError:
            continue
    return None


def _prepare_text_preview(name, mime_type, text):
    lower_name = name.lower()
    cleaned = text.replace("\r\n", "\n").replace("\r", "\n")

    if mime_type == "text/html" or lower_name.endswith((".html", ".htm")):
        parser = _HTMLTextParser()
        parser.feed(cleaned)
        cleaned = parser.text() or cleaned

    if lower_name.endswith(".csv"):
        cleaned = _csv_preview(cleaned)

    cleaned = "\n".join(line.rstrip() for line in cleaned.splitlines())
    cleaned = cleaned.strip()
    if len(cleaned) > MAX_TEXT_CHARS:
        cleaned = cleaned[:MAX_TEXT_CHARS].rstrip() + "\n...[truncated]"
    return cleaned


def _csv_preview(text):
    sample = io.StringIO(text)
    try:
        rows = list(csv.reader(sample))
    except csv.Error:
        return text

    if not rows:
        return ""

    limited_rows = rows[:30]
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerows(limited_rows)
    preview = output.getvalue().strip()
    if len(rows) > len(limited_rows):
        preview += f"\n...[{len(rows) - len(limited_rows)} more rows]"
    return preview


def _summarize_zip(name, payload):
    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            infos = archive.infolist()[:MAX_ARCHIVE_MEMBERS]
            names = [f"- {info.filename} ({info.file_size} bytes)" for info in infos]
            summary = f"Archive file with {len(archive.infolist())} entries."

            preview_parts = ["Archive contents:", *names]
            if name.lower().endswith(".docx"):
                doc_text = _extract_docx_text(archive)
                if doc_text:
                    preview_parts.extend(["", "Document text:", doc_text[:MAX_TEXT_CHARS]])
                    summary = "Word document text extracted from the .docx archive."

            return "archive", summary, "\n".join(preview_parts)
    except (OSError, zipfile.BadZipFile):
        return "binary", "Archive could not be read.", ""


def _extract_docx_text(archive):
    try:
        xml_text = archive.read("word/document.xml").decode("utf-8", errors="ignore")
    except KeyError:
        return ""

    parser = _HTMLTextParser()
    parser.feed(xml_text.replace("</w:p>", "\n"))
    return parser.text().strip()


def _summarize_gzip(payload):
    try:
        text = gzip.decompress(payload).decode("utf-8", errors="replace")
    except (OSError, EOFError):
        return "binary", "Gzip file attached, but it could not be decompressed.", ""

    preview = text[:MAX_TEXT_CHARS].rstrip()
    if len(text) > MAX_TEXT_CHARS:
        preview += "\n...[truncated]"
    return "text", "Gzip text content extracted.", preview


def _summarize_pdf(payload):
    text = _extract_pdf_text(payload)
    if not text:
        return (
            "document",
            "PDF attached, but no selectable text could be extracted. It may be scanned, image-only, encrypted, or use unsupported PDF encoding.",
            "",
        )

    preview = text[:MAX_TEXT_CHARS].rstrip()
    if len(text) > MAX_TEXT_CHARS:
        preview += "\n...[truncated]"
    return "document", "PDF selectable text extracted.", preview


def _extract_pdf_text(payload):
    parts = []
    position = 0

    while True:
        stream_start = payload.find(b"stream", position)
        if stream_start == -1:
            break

        data_start = stream_start + len(b"stream")
        if payload[data_start:data_start + 2] == b"\r\n":
            data_start += 2
        elif payload[data_start:data_start + 1] in {b"\n", b"\r"}:
            data_start += 1

        stream_end = payload.find(b"endstream", data_start)
        if stream_end == -1:
            break

        stream_data = payload[data_start:stream_end].strip(b"\r\n")
        header = payload[max(0, stream_start - 700):stream_start]
        decoded = _decode_pdf_stream(stream_data, header)
        if decoded:
            text = _extract_pdf_text_from_stream(decoded)
            if text:
                parts.append(text)

        position = stream_end + len(b"endstream")

    return _normalize_extracted_text("\n".join(parts))


def _decode_pdf_stream(stream_data, header):
    filters = re.findall(rb"/([A-Za-z0-9]+Decode)\b", header)
    data = stream_data

    for filter_name in filters:
        try:
            if filter_name == b"ASCII85Decode":
                data = base64.a85decode(data, adobe=data.rstrip().endswith(b"~>"))
            elif filter_name == b"ASCIIHexDecode":
                data = _ascii_hex_decode(data)
            elif filter_name == b"FlateDecode":
                data = zlib.decompress(data)
            else:
                return b""
        except (ValueError, zlib.error, EOFError):
            return b""

    return data


def _ascii_hex_decode(data):
    cleaned = re.sub(rb"\s+", b"", data.split(b">", 1)[0])
    if len(cleaned) % 2:
        cleaned += b"0"
    return bytes.fromhex(cleaned.decode("ascii", errors="ignore"))


def _extract_pdf_text_from_stream(stream):
    text_parts = []

    for match in re.finditer(rb"\[(.*?)\]\s*TJ|\((?:\\.|[^\\()])*\)\s*(?:Tj|'|\")", stream, re.S):
        token = match.group(0)
        if token.rstrip().endswith(b"TJ"):
            text_parts.append(_extract_pdf_array_text(match.group(1)))
        else:
            literal = re.search(rb"\((?:\\.|[^\\()])*\)", token, re.S)
            if literal:
                text_parts.append(_decode_pdf_literal(literal.group(0)))

    return "\n".join(part for part in text_parts if part.strip())


def _extract_pdf_array_text(array_payload):
    literals = re.findall(rb"\((?:\\.|[^\\()])*\)", array_payload, re.S)
    return "".join(_decode_pdf_literal(literal) for literal in literals)


def _decode_pdf_literal(literal):
    content = literal[1:-1]
    output = bytearray()
    index = 0

    while index < len(content):
        byte = content[index]
        if byte != 0x5C:
            output.append(byte)
            index += 1
            continue

        index += 1
        if index >= len(content):
            break

        escaped = content[index]
        if escaped in b"nrtbf":
            output.append({
                ord("n"): 10,
                ord("r"): 13,
                ord("t"): 9,
                ord("b"): 8,
                ord("f"): 12,
            }[escaped])
            index += 1
        elif escaped in b"()\\":
            output.append(escaped)
            index += 1
        elif 48 <= escaped <= 55:
            octal = bytes([escaped])
            index += 1
            for _ in range(2):
                if index < len(content) and 48 <= content[index] <= 55:
                    octal += bytes([content[index]])
                    index += 1
                else:
                    break
            output.append(int(octal, 8))
        elif escaped in b"\r\n":
            while index < len(content) and content[index] in b"\r\n":
                index += 1
        else:
            output.append(escaped)
            index += 1

    if output.startswith(b"\xfe\xff"):
        return output[2:].decode("utf-16-be", errors="replace")
    return output.decode("cp1252", errors="replace")


def _normalize_extracted_text(text):
    lines = []
    for line in text.replace("\r\n", "\n").replace("\r", "\n").splitlines():
        cleaned = re.sub(r"\s+", " ", line).strip()
        if cleaned:
            lines.append(cleaned)
    return "\n".join(lines)
