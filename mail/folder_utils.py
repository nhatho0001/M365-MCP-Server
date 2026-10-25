import re

from graph.client import graph_get, graph_paginate

# Tên thân thiện → well-known folder name của Graph API
WELL_KNOWN_FOLDERS: dict[str, str] = {
    "inbox":   "inbox",
    "drafts":  "drafts",
    "sent":    "sentItems",
    "deleted": "deletedItems",
    "junk":    "junkemail",
    "archive": "archive",
    "outbox":  "outbox",
}

FOLDER_SELECT = "id,displayName,childFolderCount"
MAX_FOLDERS_SCANNED = 2000


def _odata_quote(value: str) -> str:
    """Escape dấu nháy đơn cho OData string literal."""
    return value.replace("'", "''")


def _split_path(folder: str) -> list[str]:
    """'Test folder/ Test 1' → ['Test folder', 'Test 1']. Hỗ trợ cả '/' và '\\'."""
    return [part.strip() for part in re.split(r"[/\\]", folder) if part.strip()]


async def _find_child(parent_id: str | None, name: str, token: str) -> dict | None:
    """Tìm folder con trực tiếp theo displayName. parent_id=None → các folder cấp gốc."""
    path = f"me/mailFolders/{parent_id}/childFolders" if parent_id else "me/mailFolders"
    resp = await graph_get(
        path,
        token,
        params={
            "$filter": f"displayName eq '{_odata_quote(name)}'",
            "$select": FOLDER_SELECT,
            "$top": "1",
        },
    )
    folders = resp.get("value", [])
    return folders[0] if folders else None


async def _resolve_path(parts: list[str], token: str) -> str | None:
    """Đi từng cấp theo đường dẫn, trả về folder ID hoặc None nếu đứt giữa chừng."""
    first = parts[0].lower()
    if first in WELL_KNOWN_FOLDERS:
        folder_id = WELL_KNOWN_FOLDERS[first]
    else:
        found = await _find_child(None, parts[0], token)
        if not found:
            return None
        folder_id = found["id"]

    for name in parts[1:]:
        found = await _find_child(folder_id, name, token)
        if not found:
            return None
        folder_id = found["id"]
    return folder_id


async def _search_all_levels(name: str, token: str) -> list[tuple[str, str]]:
    """Duyệt BFS toàn bộ cây folder, trả về [(folder_id, full_path)] có displayName khớp name."""
    target = name.lower()
    matches: list[tuple[str, str]] = []
    queue: list[tuple[str | None, str]] = [(None, "")]
    scanned = 0

    while queue and scanned < MAX_FOLDERS_SCANNED:
        parent_id, parent_path = queue.pop(0)
        path = f"me/mailFolders/{parent_id}/childFolders" if parent_id else "me/mailFolders"
        children = await graph_paginate(
            path, token, {"$select": FOLDER_SELECT, "$top": "100"}, MAX_FOLDERS_SCANNED
        )
        for child in children:
            scanned += 1
            full_path = f"{parent_path}/{child['displayName']}" if parent_path else child["displayName"]
            if child["displayName"].lower() == target:
                matches.append((child["id"], full_path))
            if child.get("childFolderCount", 0) > 0:
                queue.append((child["id"], full_path))

    return matches


async def resolve_folder_endpoint(folder: str, token: str) -> str:
    """Chuyển tên/đường dẫn folder thành endpoint messages của Graph API.

    Hỗ trợ:
      - Tên well-known: 'inbox', 'sent', ...
      - Đường dẫn lồng nhau: 'Test folder/Test 1', 'inbox/Project/2024'
      - Chỉ tên folder ở bất kỳ cấp nào: 'Test 1' (tự tìm trong toàn bộ cây folder)
    """
    parts = _split_path(folder)
    if not parts:
        return f"me/mailFolders/{WELL_KNOWN_FOLDERS['inbox']}/messages"

    if len(parts) == 1 and parts[0].lower() in WELL_KNOWN_FOLDERS:
        return f"me/mailFolders/{WELL_KNOWN_FOLDERS[parts[0].lower()]}/messages"

    folder_id = await _resolve_path(parts, token)
    if folder_id:
        return f"me/mailFolders/{folder_id}/messages"

    # Không khớp theo đường dẫn → tìm theo tên folder cuối ở mọi cấp
    matches = await _search_all_levels(parts[-1], token)
    if len(parts) > 1:
        # Ưu tiên kết quả có đường dẫn kết thúc bằng đúng path user đưa vào
        suffix = "/".join(parts).lower()
        matches = [m for m in matches if m[1].lower().endswith(suffix)] or matches

    if len(matches) == 1:
        return f"me/mailFolders/{matches[0][0]}/messages"
    if len(matches) > 1:
        paths = "\n".join(f"  - {p}" for _, p in matches)
        raise ValueError(
            f"Có nhiều folder tên '{parts[-1]}'. Hãy chỉ rõ đường dẫn đầy đủ, ví dụ:\n{paths}"
        )
    raise ValueError(
        f"Không tìm thấy folder '{folder}'. Dùng đường dẫn dạng 'Folder cha/Folder con' cho folder lồng nhau."
    )
