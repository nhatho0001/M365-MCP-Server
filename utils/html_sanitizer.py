import html2text
import re


def html_to_text(html_content: str) -> str:
    """Chuyển HTML email sang plain text, loại bỏ script/style nguy hiểm."""
    converter = html2text.HTML2Text()
    converter.ignore_links = False
    converter.ignore_images = True
    converter.ignore_tables = False
    converter.body_width = 0  # Không wrap dòng
    converter.protect_links = True
    converter.unicode_snob = True

    text = converter.handle(html_content)

    # Loại bỏ nhiều dòng trắng liên tiếp
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def sanitize_body(body: dict) -> str:
    """Lấy nội dung email từ body dict của Graph API."""
    content_type = body.get("contentType", "text").lower()
    content = body.get("content", "")

    if content_type == "html":
        return html_to_text(content)
    return content
