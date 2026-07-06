import json
import sys
import msal
from pathlib import Path
from config import AZURE_CLIENT_ID, AZURE_TENANT_ID, SCOPES
from auth.token_cache import load_cache, save_cache

# File tạm lưu flow state giữa auth_login và auth_confirm
_FLOW_STATE_PATH = Path.home() / ".outlook-mcp-pending-flow.json"


def _make_app(cache: msal.SerializableTokenCache) -> msal.PublicClientApplication:
    authority = f"https://login.microsoftonline.com/{AZURE_TENANT_ID}"
    return msal.PublicClientApplication(
        AZURE_CLIENT_ID,
        authority=authority,
        token_cache=cache,
    )


def _try_silent(
    app: msal.PublicClientApplication,
    cache: msal.SerializableTokenCache,
) -> str | None:
    """Thử lấy token từ cache/refresh token. Trả None nếu cần đăng nhập lại."""
    accounts = app.get_accounts()
    if not accounts:
        return None
    result = app.acquire_token_silent(SCOPES, account=accounts[0])
    if result and "access_token" in result:
        save_cache(cache)
        return result["access_token"]
    if result and "error" in result:
        print(
            f"[outlook-mcp] Silent refresh thất bại: {result.get('error_description', result['error'])}",
            file=sys.stderr,
        )
    return None


def acquire_token_silent() -> str | None:
    """Thử lấy token hợp lệ từ cache. Trả None nếu cần đăng nhập lại."""
    if not AZURE_CLIENT_ID:
        return None
    cache = load_cache()
    app = _make_app(cache)
    return _try_silent(app, cache)


def start_device_flow() -> dict:
    """
    Bước 1: Khởi tạo Device Code Flow, lưu state vào file, trả về thông tin
    để hiển thị cho user (URL + code). Không blocking.
    """
    if not AZURE_CLIENT_ID:
        raise RuntimeError(
            "AZURE_CLIENT_ID chưa được cấu hình. "
            "Tạo file .env với AZURE_CLIENT_ID=<your-client-id>."
        )

    cache = load_cache()
    app = _make_app(cache)

    # Thử silent refresh trước
    token = _try_silent(app, cache)
    if token:
        return {"already_authenticated": True, "token": token}

    flow = app.initiate_device_flow(scopes=SCOPES)
    if "user_code" not in flow:
        raise RuntimeError(
            f"Không thể khởi tạo Device Code Flow: {flow.get('error_description', 'unknown error')}"
        )

    # Lưu flow state ra file để auth_confirm có thể đọc lại
    _FLOW_STATE_PATH.write_text(json.dumps(flow), encoding="utf-8")

    return {
        "already_authenticated": False,
        "user_code": flow["user_code"],
        "verification_uri": flow["verification_uri"],
        "message": flow["message"],
        "expires_in": flow.get("expires_in", 900),
    }


def complete_device_flow() -> str:
    """
    Bước 2: Đọc flow state đã lưu và poll để lấy token (blocking ngắn).
    Phải gọi sau khi user đã xác thực trong browser.
    """
    if not _FLOW_STATE_PATH.exists():
        raise RuntimeError(
            "Không tìm thấy phiên xác thực đang chờ. "
            "Hãy gọi auth_login trước."
        )

    flow = json.loads(_FLOW_STATE_PATH.read_text(encoding="utf-8"))
    cache = load_cache()
    app = _make_app(cache)

    result = app.acquire_token_by_device_flow(flow)

    # Dọn file tạm dù thành công hay thất bại
    _FLOW_STATE_PATH.unlink(missing_ok=True)

    if "access_token" not in result:
        error = result.get("error_description", result.get("error", "unknown error"))
        raise RuntimeError(f"Xác thực thất bại: {error}")

    save_cache(cache)
    return result["access_token"]


def acquire_token_device_flow() -> str:
    """Legacy blocking flow — kept for compatibility."""
    info = start_device_flow()
    if info.get("already_authenticated"):
        return info["token"]
    print(info["message"], file=sys.stderr, flush=True)
    return complete_device_flow()
