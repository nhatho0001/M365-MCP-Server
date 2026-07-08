# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Cài dependencies
uv sync

# Chạy server ở chế độ dev (MCP Inspector)
uv run mcp dev server.py

# Chạy server trực tiếp
uv run server.py

# Thêm dependency mới
uv add <package>

# Kiểm tra import không lỗi
uv run python -c "import server; print('OK')"
```

Không có test suite. Verification thủ công qua `mcp dev server.py` hoặc Claude Desktop.

## Architecture

MCP Server cho Microsoft 365 dùng [FastMCP](https://github.com/jlowin/fastmcp). Mọi chức năng được expose dưới dạng **MCP tools** để Claude gọi.

### Luồng dữ liệu

```
Claude Desktop → FastMCP (server.py)
                    ↓
            register_*_tools()   ← mỗi package có 1 hàm này
                    ↓
          auth.ensure_authenticated()  ← lấy token từ cache
                    ↓
          graph/client.py              ← gọi Microsoft Graph API
                    ↓
          utils/formatting.py          ← format kết quả thành text
```

### Cách thêm nhóm tool mới (ví dụ Calendar)

1. Tạo thư mục `calendar/` với file `__init__.py` chứa hàm `register_calendar_tools(mcp: FastMCP)`
2. Logic impl nằm trong các file riêng, ví dụ `calendar/list_events.py`
3. Thêm 2 dòng vào `server.py`:
   ```python
   from calendar_tools import register_calendar_tools
   register_calendar_tools(mcp)
   ```
4. Thêm package vào `pyproject.toml` → `[tool.hatch.build.targets.wheel] packages`

Không cần thay đổi file nào khác.

### Cách thêm tool mới vào package có sẵn (ví dụ thêm vào mail/)

1. Tạo file impl: `mail/my_feature.py` với hàm `async def my_feature_impl(...) -> str`
2. Import và đăng ký trong `mail/__init__.py`:
   ```python
   from mail.my_feature import my_feature_impl

   # trong register_mail_tools():
   @mcp.tool()
   async def my_feature(...) -> str:
       """Docstring mô tả tool — hiển thị cho Claude."""
       return await my_feature_impl(...)
   ```

### Các package hiện có

| Package | Chức năng |
|---------|-----------|
| `auth/` | MSAL Device Code Flow; tools: `auth_login`, `auth_confirm`, `auth_status`, `auth_logout` |
| `graph/` | HTTP wrappers cho Graph API: `graph_get/post/patch/delete/download`, `graph_paginate` |
| `mail/` | Email CRUD + đọc đính kèm (xem bên dưới) |
| `sharepoint/` | Đọc file Excel từ SharePoint Online |
| `utils/` | HTML → text (`html_sanitizer`), format email display (`formatting`) |

### mail/ — các tools

| Tool | File impl | Chức năng |
|------|-----------|-----------|
| `list_emails` | `list_emails.py` | Liệt kê email theo folder |
| `read_email` | `read_email.py` | Đọc nội dung đầy đủ một email |
| `search_emails` | `search_emails.py` | Tìm kiếm với KQL / OData filter |
| `create_draft`, `list_drafts`, `update_draft`, `delete_draft`, `send_draft` | `drafts.py` | Quản lý email nháp |
| `send_email` | `send_email.py` | Soạn và gửi ngay |
| `mark_email_as_read` | `mark_as_read.py` | Đánh dấu đọc/chưa đọc |
| `list_attachments` | `attachments.py` | Liệt kê file đính kèm (tên, MIME, kích thước, ID) |
| `read_attachment` | `attachments.py` | Đọc nội dung đính kèm trực tiếp (text/xlsx/pdf/docx) |

`read_attachment` hỗ trợ: text thuần (UTF-8), Excel (`openpyxl`), PDF (`pypdf`), Word (`python-docx`). Ảnh và định dạng khác trả thông báo không hỗ trợ.

### mail/folder_utils.py

`resolve_folder_endpoint(folder, token)` chuyển tên folder thành Graph API path. Các tên well-known: `inbox`, `drafts`, `sent`, `deleted`, `junk`, `archive`, `outbox`. Tên tùy chỉnh được tra cứu qua `$filter=displayName eq '...'`.

### Authentication

Dùng **MSAL Device Code Flow** (2 bước): `auth_login` → user xác thực trên browser → `auth_confirm`. Token được cache tại `~/.outlook-mcp-tokens.json`, tự refresh, hiệu lực 90 ngày.

Scopes hiện tại trong `config.py`: `Mail.Read`, `Mail.ReadWrite`, `Mail.Send`, `User.Read`, `Sites.Read.All`, `Files.Read.All`.

> Khi thêm scope mới, user phải re-authenticate: `auth_logout()` → `auth_login()` → `auth_confirm()`.

### graph/client.py — các hàm quan trọng

- `graph_get/post/patch/delete` — JSON requests, tự xử lý lỗi 401/403/404/429
- `graph_download(path, token) -> bytes` — download file nhị phân (binary stream, timeout 60s)
- `graph_paginate(path, token, params, max_items)` — follow `@odata.nextLink` tự động

Dùng `graph_get` khi API trả JSON (kể cả khi JSON chứa `contentBytes` base64 như attachment). Dùng `graph_download` khi endpoint trả về binary stream trực tiếp (như SharePoint file `/content`).

### config.py — các constants

```python
EMAIL_SELECT           # fields dùng cho list view (không có body)
EMAIL_DETAIL_SELECT    # fields dùng cho detail view (có body)
ATTACHMENT_LIST_SELECT # fields dùng khi list attachments (không có contentBytes)
```

Luôn dùng `$select` khi gọi Graph API để tránh fetch dữ liệu không cần thiết. Đặc biệt quan trọng với attachments — bỏ `contentBytes` khỏi select khi chỉ cần metadata.

### Cấu hình

File `.env` cần có:
```
AZURE_CLIENT_ID=<app-registration-id>
AZURE_TENANT_ID=common   # hoặc tenant-id cụ thể
```

Azure App phải bật **"Allow public client flows"** (Device Code Flow) và được grant các permissions tương ứng với SCOPES.
