import httpx
from config import GRAPH_BASE


async def graph_request(
    method: str,
    path: str,
    token: str,
    *,
    params: dict | None = None,
    json: dict | None = None,
) -> dict:
    url = f"{GRAPH_BASE}/{path.lstrip('/')}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.request(
            method, url, headers=headers, params=params, json=json
        )

    if response.status_code == 401:
        raise PermissionError(
            "Token hết hạn hoặc không hợp lệ. Hãy gọi 'auth_login' để đăng nhập lại."
        )
    if response.status_code == 403:
        raise PermissionError(
            f"Graph API từ chối quyền truy cập (403). "
            f"Kiểm tra lại API permissions trong Azure Portal."
        )
    if response.status_code == 404:
        raise ValueError(f"Không tìm thấy resource: {path}")
    if response.status_code == 429:
        raise RuntimeError("Graph API rate limit. Hãy thử lại sau vài giây.")

    response.raise_for_status()

    if response.content:
        return response.json()
    return {}


async def graph_paginate(
    path: str,
    token: str,
    params: dict,
    max_items: int,
) -> list[dict]:
    """Fetch nhiều trang kết quả, follow @odata.nextLink tự động."""
    items: list[dict] = []
    url = f"{GRAPH_BASE}/{path.lstrip('/')}"
    headers = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient(timeout=30.0) as client:
        while url and len(items) < max_items:
            response = await client.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()
            items.extend(data.get("value", []))
            url = data.get("@odata.nextLink")
            params = {}  # nextLink đã có sẵn tất cả params

    return items[:max_items]


async def graph_get(path: str, token: str, params: dict | None = None) -> dict:
    return await graph_request("GET", path, token, params=params)


async def graph_post(path: str, token: str, body: dict) -> dict:
    return await graph_request("POST", path, token, json=body)


async def graph_patch(path: str, token: str, body: dict) -> dict:
    return await graph_request("PATCH", path, token, json=body)


async def graph_delete(path: str, token: str) -> dict:
    return await graph_request("DELETE", path, token)
