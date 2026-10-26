from auth import ensure_authenticated
from graph.client import graph_get, graph_paginate
from config import EMAIL_SELECT, MAX_RESULT_COUNT
from mail.folder_utils import resolve_folder_endpoint
from utils.formatting import format_email_summary


def _to_iso_datetime(date_str: str, end_of_day: bool = False) -> str:
    """Chuẩn hóa 'YYYY-MM-DD' thành ISO 8601 datetime UTC. Giữ nguyên nếu đã là ISO datetime."""
    if len(date_str) == 10:
        return f"{date_str}T{'23:59:59' if end_of_day else '00:00:00'}Z"
    return date_str


async def search_emails_impl(
    query: str = "",
    folder: str = "inbox",
    from_address: str = "",
    subject: str = "",
    unread_only: bool = False,
    has_attachments: bool = False,
    from_date: str = "",
    to_date: str = "",
    limit: int = 10,
) -> str:
    token = ensure_authenticated()
    limit = max(1, min(limit, MAX_RESULT_COUNT))
    endpoint = await resolve_folder_endpoint(folder, token)

    # Ưu tiên $search (KQL) nếu có query text
    if query:
        params = {
            "$search": f'"{query}"',
            "$select": EMAIL_SELECT,
            "$top": str(min(limit, 25)),
        }
        items = await graph_paginate(endpoint, token, params, limit)
    else:
        # Dùng $filter khi chỉ có điều kiện cụ thể
        filters = []
        if from_address:
            filters.append(f"from/emailAddress/address eq '{from_address}'")
        if subject:
            filters.append(f"contains(subject,'{subject}')")
        if unread_only:
            filters.append("isRead eq false")
        if has_attachments:
            filters.append("hasAttachments eq true")
        if from_date:
            filters.append(f"receivedDateTime ge {_to_iso_datetime(from_date)}")
        if to_date:
            filters.append(f"receivedDateTime le {_to_iso_datetime(to_date, end_of_day=True)}")

        params: dict = {
            "$select": EMAIL_SELECT,
            "$orderby": "receivedDateTime desc",
            "$top": str(min(limit, 25)),
        }
        if filters:
            params["$filter"] = " and ".join(filters)

        items = await graph_paginate(endpoint, token, params, limit)

    if not items:
        return "Không tìm thấy email nào khớp với điều kiện tìm kiếm."

    lines = [format_email_summary(msg, i) for i, msg in enumerate(items, 1)]
    header = f"Tìm thấy {len(items)} email:\n"
    return header + "\n\n".join(lines)
