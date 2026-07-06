from graph.client import graph_get

WELL_KNOWN_FOLDERS: dict[str, str] = {
    "inbox":   "me/mailFolders/inbox/messages",
    "drafts":  "me/mailFolders/drafts/messages",
    "sent":    "me/mailFolders/sentItems/messages",
    "deleted": "me/mailFolders/deletedItems/messages",
    "junk":    "me/mailFolders/junkemail/messages",
    "archive": "me/mailFolders/archive/messages",
    "outbox":  "me/mailFolders/outbox/messages",
}


async def resolve_folder_endpoint(folder: str, token: str) -> str:
    key = folder.lower().strip()
    if key in WELL_KNOWN_FOLDERS:
        return WELL_KNOWN_FOLDERS[key]

    # Tìm folder theo display name qua Graph API
    resp = await graph_get(
        "me/mailFolders",
        token,
        params={"$filter": f"displayName eq '{folder}'", "$top": "1"},
    )
    folders = resp.get("value", [])
    if folders:
        return f"me/mailFolders/{folders[0]['id']}/messages"

    # Fallback về inbox nếu không tìm thấy
    return WELL_KNOWN_FOLDERS["inbox"]
