from auth import ensure_authenticated
from graph.client import graph_get, graph_post, graph_patch, graph_delete, graph_paginate
from config import EMAIL_SELECT
from utils.formatting import format_draft_summary


def _build_recipients(csv_addresses: str) -> list[dict]:
    if not csv_addresses or not csv_addresses.strip():
        return []
    return [
        {"emailAddress": {"address": addr.strip()}}
        for addr in csv_addresses.split(",")
        if addr.strip()
    ]


def _detect_content_type(body: str) -> str:
    stripped = body.strip().lower()
    if stripped.startswith("<html") or stripped.startswith("<!doctype"):
        return "html"
    return "text"


async def create_draft_impl(
    to: str = "",
    cc: str = "",
    bcc: str = "",
    subject: str = "",
    body: str = "",
    importance: str = "normal",
) -> str:
    token = ensure_authenticated()
    payload: dict = {
        "subject": subject,
        "importance": importance,
        "body": {
            "contentType": _detect_content_type(body),
            "content": body,
        },
        "toRecipients": _build_recipients(to),
        "ccRecipients": _build_recipients(cc),
        "bccRecipients": _build_recipients(bcc),
    }
    draft = await graph_post("me/messages", token, payload)
    return (
        f"Đã tạo email nháp thành công.\n"
        f"Tiêu đề: {draft.get('subject') or '(không có tiêu đề)'}\n"
        f"ID: {draft['id']}\n"
        f"Đến: {to or '(chưa điền)'}"
    )


async def list_drafts_impl(limit: int = 10) -> str:
    token = ensure_authenticated()
    limit = max(1, min(limit, 50))
    params = {
        "$select": EMAIL_SELECT,
        "$orderby": "lastModifiedDateTime desc",
        "$top": str(min(limit, 25)),
    }
    items = await graph_paginate("me/mailFolders/drafts/messages", token, params, limit)

    if not items:
        return "Không có email nháp nào."

    lines = [format_draft_summary(msg, i) for i, msg in enumerate(items, 1)]
    return f"Tìm thấy {len(items)} email nháp:\n\n" + "\n\n".join(lines)


async def update_draft_impl(
    message_id: str,
    subject: str | None = None,
    body: str | None = None,
    to: str | None = None,
    cc: str | None = None,
    bcc: str | None = None,
) -> str:
    token = ensure_authenticated()
    payload: dict = {}

    if subject is not None:
        payload["subject"] = subject
    if body is not None:
        payload["body"] = {
            "contentType": _detect_content_type(body),
            "content": body,
        }
    if to is not None:
        payload["toRecipients"] = _build_recipients(to)
    if cc is not None:
        payload["ccRecipients"] = _build_recipients(cc)
    if bcc is not None:
        payload["bccRecipients"] = _build_recipients(bcc)

    if not payload:
        return "Không có thay đổi nào được cung cấp."

    await graph_patch(f"me/messages/{message_id}", token, payload)
    fields = ", ".join(payload.keys())
    return f"Đã cập nhật nháp {message_id}. Các trường đã sửa: {fields}."


async def delete_draft_impl(message_id: str) -> str:
    token = ensure_authenticated()
    await graph_delete(f"me/messages/{message_id}", token)
    return f"Đã xóa email nháp {message_id}."


async def send_draft_impl(message_id: str) -> str:
    token = ensure_authenticated()
    await graph_post(f"me/messages/{message_id}/send", token, {})
    return f"Đã gửi email nháp {message_id} thành công."
