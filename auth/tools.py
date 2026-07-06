import asyncio
from mcp.server.fastmcp import FastMCP
from auth.device_flow import start_device_flow, complete_device_flow
from auth import get_access_token
from config import TOKEN_PATH


def register_auth_tools(mcp: FastMCP) -> None:

    @mcp.tool()
    async def auth_login() -> str:
        """Bắt đầu đăng nhập Microsoft 365 qua Device Code Flow.
        Tool này trả về URL và mã xác thực — mở URL đó trong trình duyệt,
        nhập mã, sau đó gọi auth_confirm để hoàn tất."""
        try:
            info = await asyncio.to_thread(start_device_flow)
            if info.get("already_authenticated"):
                return "Bạn đã đăng nhập rồi. Không cần xác thực lại."
            url = info["verification_uri"]
            code = info["user_code"]
            expires = info["expires_in"]
            return (
                f"Để đăng nhập Microsoft 365, hãy làm theo các bước:\n\n"
                f"1. Mở trình duyệt và truy cập: {url}\n"
                f"2. Nhập mã xác thực: **{code}**\n"
                f"3. Đăng nhập bằng tài khoản Microsoft của bạn\n"
                f"4. Sau khi xác thực xong, quay lại đây và gọi **auth_confirm**\n\n"
                f"(Mã hết hạn sau {expires // 60} phút)"
            )
        except Exception as e:
            return f"Lỗi khởi tạo đăng nhập: {e}"

    @mcp.tool()
    async def auth_confirm() -> str:
        """Hoàn tất đăng nhập sau khi bạn đã nhập mã xác thực trong trình duyệt.
        Gọi tool này sau khi đã hoàn thành bước xác thực trên trang Microsoft."""
        try:
            token = await asyncio.to_thread(complete_device_flow)
            if token:
                return "Đăng nhập thành công! Bạn có thể dùng các email tools ngay bây giờ."
            return "Đăng nhập thất bại. Hãy thử lại từ auth_login."
        except Exception as e:
            return f"Lỗi xác nhận đăng nhập: {e}"

    @mcp.tool()
    def auth_status() -> str:
        """Kiểm tra trạng thái đăng nhập Microsoft 365 hiện tại."""
        token = get_access_token()
        if token:
            return "Đã đăng nhập và sẵn sàng sử dụng."
        return "Chưa đăng nhập. Hãy gọi 'auth_login' để đăng nhập."

    @mcp.tool()
    def auth_logout() -> str:
        """Đăng xuất — xóa token đã lưu, yêu cầu đăng nhập lại lần sau."""
        if TOKEN_PATH.exists():
            TOKEN_PATH.unlink()
            return "Đã đăng xuất. Token đã được xóa."
        return "Không có phiên đăng nhập nào đang hoạt động."
