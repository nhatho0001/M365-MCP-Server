from auth.device_flow import acquire_token_silent


def get_access_token() -> str | None:
    """Lấy token từ cache, trả None nếu chưa đăng nhập hoặc token hết hạn."""
    return acquire_token_silent()


def ensure_authenticated() -> str:
    """Lấy token hợp lệ hoặc raise PermissionError nếu chưa đăng nhập."""
    token = get_access_token()
    if not token:
        raise PermissionError(
            "Chưa đăng nhập hoặc token đã hết hạn. "
            "Hãy gọi tool 'auth_login' để đăng nhập lại."
        )
    return token
