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

1. Tạo thư mục `calendar_tools/` với file `__init__.py` chứa hàm `register_calendar_tools(mcp: FastMCP)`
   (không đặt tên `calendar/` — trùng tên module chuẩn của Python, sẽ gây lỗi import)
2. Logic impl nằm trong các file riêng, ví dụ `calendar_tools/list_events.py`
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
| `sharepoint/` | Đọc file Excel từ SharePoint Online (xem bên dưới) |
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
| `read_attachment` | `attachments.py` | Đọc nội dung đính kèm trực tiếp (text/xlsx/pdf/docx/ảnh) |

`search_emails_impl` có hai nhánh loại trừ lẫn nhau: nếu `query` khác rỗng, tool dùng `$search` (KQL) và **bỏ qua mọi filter khác** (`from_address`, `subject`, `unread_only`, `has_attachments`, `from_date`, `to_date`); nếu `query` rỗng, tool build `$filter` từ các điều kiện đó (kết hợp bằng `and`). Khi thêm filter mới, phải thêm vào nhánh `$filter`, không phải nhánh `$search`.

`read_attachment` hỗ trợ: text thuần (UTF-8), Excel (`openpyxl`), PDF (`pypdf`), Word (`python-docx`), ảnh PNG/JPEG/GIF/WEBP (trả về qua `mcp.server.fastmcp.Image` — Claude xem trực tiếp, không phải OCR). Định dạng ảnh khác (bmp, tiff, svg, ...) và định dạng chưa hỗ trợ khác trả thông báo không hỗ trợ. Excel đính kèm trả về **markdown table** — khác với `read_sharepoint_excel` (trả JSON, xem mục `sharepoint/` bên dưới).

### sharepoint/ — tools

| Tool | File impl | Chức năng |
|------|-----------|-----------|
| `read_sharepoint_excel` | `read_excel.py` | Đọc nội dung file Excel (.xlsx/.xlsm/.xlam) từ SharePoint Online |
| `filter_sharepoint_excel` | `filter_excel.py` | Đọc file Excel từ SharePoint, chỉ trả về các dòng khớp filter theo giá trị cột |

Logic resolve/download URL (sharing link + direct URL) và các helper JSON (`build_field_names`, `normalize_cell_value`, `rows_to_records`) nằm chung trong `sharepoint/excel_common.py` — dùng chung cho cả `read_excel.py` và `filter_excel.py`. `fetch_excel_bytes(url, token)` xử lý 2 dạng URL:
- **Sharing link** (`/:x:/s/...`) — encode thành `shareId` (`u!<base64url>`) và gọi `GET /shares/{shareId}/driveItem`, ưu tiên download qua `@microsoft.graph.downloadUrl` (pre-authenticated, dùng `graph_download_url`), fallback sang `graph_download` với `driveId`/`itemId`.
- **Direct URL** (`https://tenant.sharepoint.com/sites/.../file.xlsx`) — parse hostname/site path/file path, resolve site ID qua `sites/{hostname}:{site_path}`, rồi lấy driveItem và download qua `graph_download`.

Cả 2 hàm impl đều trả về **JSON** (không phải markdown table).

`read_excel_impl` → object gồm metadata (`site`, `file_name`, `file_path`, `file_size_bytes`, `sheet_names`, `sheet`, `total_rows`, `rows_returned`, `truncated`, `columns`) và mảng `rows` — mỗi phần tử là 1 dòng dữ liệu dạng `{tên_cột: giá_trị}` lấy từ header row của sheet.

`filter_excel_impl` nhận thêm tham số `filters: dict[str, list[str]]` — object dạng `{tên_cột: [giá_trị_1, giá_trị_2, ...]}`. Một dòng khớp khi: với **mọi** cột có trong `filters`, giá trị dòng đó nằm trong danh sách giá trị cho phép của cột (AND giữa các cột, OR giữa các giá trị trong cùng 1 cột). So sánh dạng chuỗi (`str(cell_value)`), không phân biệt kiểu số/text gốc. Nếu 1 tên cột trong `filters` không tồn tại trong header row, trả lỗi kèm danh sách cột hợp lệ — kiểm tra này chạy ngay sau khi đọc header, trước khi quét toàn bộ data rows. Output thêm field `filters`, `total_rows_scanned`, `total_matched` so với `read_excel_impl`; `max_rows` áp dụng trên **số dòng khớp filter**, không phải tổng số dòng trong sheet.

### mail/folder_utils.py

`resolve_folder_endpoint(folder, token)` chuyển tên folder thành Graph API path. Các tên well-known: `inbox`, `drafts`, `sent`, `deleted`, `junk`, `archive`, `outbox`. Tên tùy chỉnh được tra cứu qua `$filter=displayName eq '...'`.

### Authentication

Dùng **MSAL Device Code Flow** (2 bước): `auth_login` → user xác thực trên browser → `auth_confirm`. Token được cache tại `~/.outlook-mcp-tokens.json`, tự refresh, hiệu lực 90 ngày.

Scopes hiện tại trong `config.py`: `Mail.Read`, `Mail.ReadWrite`, `Mail.Send`, `User.Read`, `Sites.Read.All`, `Files.Read.All`.

> Khi thêm scope mới, user phải re-authenticate: `auth_logout()` → `auth_login()` → `auth_confirm()`.

### graph/client.py — các hàm quan trọng

- `graph_get/post/patch/delete` — JSON requests, tự xử lý lỗi 401/403/404/429
- `graph_download(path, token) -> bytes` — download file nhị phân qua Graph API (binary stream, timeout 60s, cần Authorization header)
- `graph_download_url(url) -> bytes` — download trực tiếp từ pre-authenticated URL (vd. `@microsoft.graph.downloadUrl`), không cần token
- `graph_paginate(path, token, params, max_items)` — follow `@odata.nextLink` tự động

Dùng `graph_get` khi API trả JSON (kể cả khi JSON chứa `contentBytes` base64 như attachment). Dùng `graph_download`/`graph_download_url` khi endpoint trả về binary stream trực tiếp (như SharePoint file `/content`).

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
