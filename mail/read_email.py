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

    if mark_as_read and not msg.get("isRead"):
        await graph_patch(f"me/messages/{message_id}", token, {"isRead": True})
        result += "\n\n[Đã đánh dấu là đã đọc]"

    return result
