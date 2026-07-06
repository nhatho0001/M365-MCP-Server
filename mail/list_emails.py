from auth import ensure_authenticated
from graph.client import graph_paginate
from config import EMAIL_SELECT
from mail.folder_utils import resolve_folder_endpoint
from utils.formatting import format_email_summary


async def list_emails_impl(folder: str = "inbox", limit: int = 10) -> str:
    token = ensure_authenticated()
    limit = max(1, min(limit, 50))
    endpoint = await resolve_folder_endpoint(folder, token)

    params = {
        "$select": EMAIL_SELECT,
        "$orderby": "receivedDateTime desc",
        "$top": str(min(limit, 25)),
    }
    items = await graph_paginate(endpoint, token, params, limit)

    if not items:
        return f"Không có email nào trong folder '{folder}'."

    lines = [format_email_summary(msg, i) for i, msg in enumerate(items, 1)]
    header = f"Tìm thấy {len(items)} email trong '{folder}':\n"
    return header + "\n\n".join(lines)
