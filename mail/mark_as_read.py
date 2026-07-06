from auth import ensure_authenticated
from graph.client import graph_patch


async def mark_as_read_impl(message_id: str, is_read: bool = True) -> str:
    token = ensure_authenticated()
    await graph_patch(f"me/messages/{message_id}", token, {"isRead": is_read})
    status = "đã đọc" if is_read else "chưa đọc"
    return f"Email {message_id} đã được đánh dấu là '{status}'."
