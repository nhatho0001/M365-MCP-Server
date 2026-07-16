import html2text
import re


def html_to_text(html_content: str) -> str:
    """Chuyển HTML email sang plain text, loại bỏ script/style nguy hiểm."""
    converter = html2text.HTML2Text()
    converter.ignore_links = False
    converter.ignore_images = False  # Giữ lại <img> để xử lý cid: bên dưới
    converter.ignore_tables = False
    converter.body_width = 0  # Không wrap dòng
    converter.protect_links = True
    converter.unicode_snob = True

    text = converter.handle(html_content)

    # Chuyển ảnh inline (cid:) thành placeholder dễ đọc
    # html2text render thành: ![alt](cid:xxx) hoặc ![](cid:xxx)
    text = re.sub(r"!\[([^\]]*)\]\(cid:([^)]+)\)", _replace_cid_image, text)

    # Loại bỏ ảnh remote (http/https) và data URI — chỉ giữ cid: placeholder
    text = re.sub(r"!\[[^\]]*\]\(https?://[^)]+\)", "", text)
    text = re.sub(r"!\[[^\]]*\]\(data:[^)]+\)", "", text)

    # Loại bỏ nhiều dòng trắng liên tiếp
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _replace_cid_image(m: re.Match) -> str:
    alt = m.group(1).strip()
    cid = m.group(2).strip()
    label = alt if alt else "ảnh"
    return f"[{label} — cid:{cid}]"


def sanitize_body(body: dict) -> str:
    """Lấy nội dung email từ body dict của Graph API."""
    content_type = body.get("contentType", "text").lower()
    content = body.get("content", "")

    if content_type == "html":
        return html_to_text(content)
    return content
