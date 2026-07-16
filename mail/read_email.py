import re

from auth import ensure_authenticated
from graph.client import graph_get, graph_patch
from config import EMAIL_DETAIL_SELECT
from utils.html_sanitizer import sanitize_body
from utils.formatting import format_email_detail


async def read_email_impl(message_id: str, mark_as_read: bool = False) -> str:
    token = ensure_authenticated()

    msg = await graph_get(
        f"me/messages/{message_id}",
        token,
        params={"$select": EMAIL_DETAIL_SELECT},
    )

    body_text = sanitize_body(msg.get("body", {}))
    result = format_email_detail(msg, body_text)

    # Kiểm tra ảnh inline: khi body chứa placeholder cid: hoặc email có attachment
    has_inline = bool(re.search(r"cid:", body_text)) or msg.get("hasAttachments")
    if has_inline:
        inline_section = await _get_inline_images_section(message_id, token)
        if inline_section:
            result += "\n\n" + inline_section

    if mark_as_read and not msg.get("isRead"):
        await graph_patch(f"me/messages/{message_id}", token, {"isRead": True})
        result += "\n\n[Đã đánh dấu là đã đọc]"

    return result


async def _get_inline_images_section(message_id: str, token: str) -> str:
    """Trả về section liệt kê ảnh inline, hoặc chuỗi rỗng nếu không có."""
    try:
        # Không dùng $select để lấy đủ field, kể cả contentId
        # (contentId không hợp lệ trong $select ở collection endpoint → 400)
        data = await graph_get(
            f"me/messages/{message_id}/attachments",
            token,
        )
    except Exception:
        return ""

    attachments = data.get("value", [])
    inline_images = [
        att for att in attachments
        if att.get("isInline") and att.get("contentType", "").startswith("image/")
    ]

    if not inline_images:
        return ""

    lines = [f"📷 Ảnh đính kèm trong thân email ({len(inline_images)} ảnh):"]
    for att in inline_images:
        cid = att.get("contentId", "").strip("<>")
        lines.append(
            f"  • {att.get('name', '(không tên)')} "
            f"[{att.get('contentType', '')}] "
            f"— ID: {att.get('id', '')} "
            + (f"| cid: {cid}" if cid else "")
        )
    lines.append("→ Dùng read_attachment(message_id, attachment_id) để xem từng ảnh.")
    return "\n".join(lines)
