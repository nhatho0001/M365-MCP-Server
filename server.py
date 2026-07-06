from mcp.server.fastmcp import FastMCP
from auth.tools import register_auth_tools
from mail import register_mail_tools

# Tạo FastMCP instance — tên này hiển thị trong Claude Desktop
mcp = FastMCP("outlook-email")

# Đăng ký các nhóm tool
# Để thêm tính năng mới (Calendar, Contacts, ...):
#   1. Tạo package mới, ví dụ: calendar/
#   2. Viết register_calendar_tools(mcp) trong calendar/__init__.py
#   3. Thêm 2 dòng bên dưới:
#      from calendar_tools import register_calendar_tools
#      register_calendar_tools(mcp)
register_auth_tools(mcp)
register_mail_tools(mcp)

if __name__ == "__main__":
    mcp.run()
