# Outlook Email MCP Server

MCP Server cho Claude Desktop để đọc và quản lý email Microsoft 365 / Outlook qua Microsoft Graph API.

## Tính năng

| Tool | Mô tả |
|------|-------|
| `auth_login` | Bắt đầu đăng nhập — trả về URL và mã xác thực |
| `auth_confirm` | Hoàn tất đăng nhập sau khi xác thực trong browser |
| `auth_status` | Kiểm tra trạng thái đăng nhập hiện tại |
| `auth_logout` | Đăng xuất, xóa token đã lưu |
| `list_emails` | Liệt kê email theo folder |
| `read_email` | Đọc nội dung đầy đủ một email |
| `search_emails` | Tìm kiếm email với nhiều điều kiện |
| `create_draft` | Tạo email nháp mới |
| `list_drafts` | Liệt kê tất cả email nháp |
| `update_draft` | Sửa nội dung email nháp |
| `delete_draft` | Xóa email nháp |
| `send_draft` | Gửi email nháp đã tạo |
| `send_email` | Soạn và gửi email ngay |
| `mark_email_as_read` | Đánh dấu email đã đọc / chưa đọc |

---

## Yêu cầu

- Python 3.11 trở lên
- [Claude Desktop](https://claude.ai/download)
- Tài khoản Microsoft 365 hoặc Outlook.com
- Quyền truy cập [Azure Portal](https://portal.azure.com) (để đăng ký app)

---

## Hướng dẫn cài đặt

### Bước 1: Tải source code

Tải hoặc clone repo này về máy, ví dụ vào thư mục:
```
C:\Projects\mcp-server\
```

> Ghi nhớ đường dẫn này — bạn sẽ dùng ở Bước 4.

---

### Bước 2: Đăng ký Azure App

> Bước này chỉ làm **một lần duy nhất**. Nếu đã có `AZURE_CLIENT_ID`, bỏ qua.

1. Truy cập [portal.azure.com](https://portal.azure.com) và đăng nhập
2. Tìm **"App registrations"** → nhấn **"New registration"**
3. Điền thông tin:
   - **Name**: `M365 MCP Server` (hoặc tên bất kỳ)
   - **Supported account types**: chọn theo nhu cầu:
     - `Accounts in any organizational directory and personal Microsoft accounts` — nếu muốn dùng cả tài khoản cá nhân lẫn tổ chức
     - `Accounts in this organizational directory only` — nếu chỉ dùng trong nội bộ tổ chức
   - **Redirect URI**: để **trống**
4. Nhấn **Register**
5. Sau khi tạo xong, copy **Application (client) ID** — đây là `AZURE_CLIENT_ID`

#### Cấp quyền API

6. Vào tab **"API permissions"** → **"Add a permission"** → **"Microsoft Graph"** → **"Delegated permissions"**
7. Tìm và thêm các quyền sau:
   - `Mail.Read`
   - `Mail.ReadWrite`
   - `Mail.Send`
   - `User.Read`
   - `offline_access`
8. Nhấn **"Grant admin consent for [tên tổ chức]"** nếu bạn là admin *(tùy chọn — xem phần Troubleshooting nếu không có quyền này)*

#### Bật Device Code Flow

9. Vào tab **"Authentication"**
10. Kéo xuống phần **"Advanced settings"**
11. Bật **"Allow public client flows"** → **Yes**
12. Nhấn **Save**

---

### Bước 3: Cài đặt dependencies

Mở terminal, điều hướng vào thư mục project:

```bash
cd "C:\Projects\mcp-server"
```

#### Cách 1: Dùng `uv` (Khuyên dùng — tự quản lý virtual env)

```bash
# Cài uv nếu chưa có
pip install uv

# Cài dependencies
uv sync
```

#### Cách 2: Dùng `pip` thông thường

```bash
pip install "mcp[cli]" msal httpx python-dotenv html2text
```

---

### Bước 4: Tạo file `.env`

Trong thư mục project, copy file mẫu:

```bash
# Windows
copy .env.example .env

# macOS / Linux
cp .env.example .env
```

Mở file `.env` và điền `AZURE_CLIENT_ID` lấy từ Bước 2:

```
AZURE_CLIENT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
AZURE_TENANT_ID=common
```

**Giá trị `AZURE_TENANT_ID`:**

| Giá trị | Dùng khi |
|---------|----------|
| `common` | Tài khoản cá nhân (Outlook.com) hoặc hỗn hợp |
| `organizations` | Chỉ tài khoản tổ chức (work/school) |
| `<tenant-id>` | Giới hạn đúng một tổ chức cụ thể |

---

### Bước 5: Cấu hình Claude Desktop

Mở file cấu hình Claude Desktop:

- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`

Thêm vào trong `mcpServers` (thay đường dẫn bằng đường dẫn thực tế trên máy bạn):

#### Cách 1: Dùng `uv` (Khuyên dùng)

```json
{
  "mcpServers": {
    "outlook-email": {
      "command": "uv",
      "args": [
        "--directory",
        "C:\\Projects\\mcp-server",
        "run",
        "server.py"
      ]
    }
  }
}
```

#### Cách 2: Dùng `python` trực tiếp

```json
{
  "mcpServers": {
    "outlook-email": {
      "command": "python",
      "args": [
        "C:\\Projects\\mcp-server\\server.py"
      ]
    }
  }
}
```

> **Lưu ý Windows**: Dùng `\\` thay vì `\` trong đường dẫn JSON.

**Restart Claude Desktop** sau khi lưu file config.

---

### Bước 6: Đăng nhập lần đầu

Sau khi restart Claude Desktop:

1. Mở cuộc trò chuyện mới
2. Kiểm tra biểu tượng MCP tools xuất hiện (icon công cụ)
3. Yêu cầu Claude gọi tool `auth_login`:
   > "Hãy đăng nhập vào Outlook email cho tôi"

4. Claude sẽ trả về **URL và mã xác thực** ngay trong chat, ví dụ:
   ```
   1. Mở trình duyệt và truy cập: https://login.microsoft.com/device
   2. Nhập mã xác thực: ABCD1234
   3. Đăng nhập bằng tài khoản Microsoft của bạn
   4. Sau khi xác thực xong, gọi auth_confirm
   ```

5. Thực hiện theo hướng dẫn trong chat, sau đó yêu cầu Claude gọi `auth_confirm`:
   > "Tôi đã xác thực xong, hãy xác nhận đăng nhập"

6. Claude thông báo đăng nhập thành công.

> Token được lưu tại `~/.outlook-mcp-tokens.json` và tự động refresh — **có hiệu lực 90 ngày**.

---

## Sử dụng

Sau khi đăng nhập, bạn có thể dùng ngôn ngữ tự nhiên:

```
"Kiểm tra xem tôi đã đăng nhập chưa"
"Liệt kê 10 email mới nhất trong inbox"
"Tìm email từ boss@company.com"
"Tạo email nháp gửi cho colleague@company.com với tiêu đề Meeting tomorrow"
"Gửi email cho client@example.com nội dung cảm ơn hợp tác"
"Đánh dấu email vừa đọc là chưa đọc"
```

---

## Troubleshooting

### "Need admin approval" khi đăng nhập

Tài khoản tổ chức (work/school) yêu cầu admin của tổ chức phải grant consent cho app.

**Nếu bạn là admin:**
1. Azure Portal → **Enterprise Applications** → tìm app → **Permissions** → **Grant admin consent**

**Nếu bạn không phải admin:**
- Nhờ IT admin của tổ chức vào Azure Portal, tìm app theo tên, và grant consent
- Hoặc admin nhấn **"Have an admin account? Sign in with that account"** ngay trên màn hình lỗi

**Giới hạn người dùng (tùy chọn cho admin):**
- Azure Portal → **Enterprise Applications** → tên app → **Properties** → bật **"Assignment required"**
- Sau đó vào **Users and groups** → chỉ add những người được phép dùng

---

### MCP server không xuất hiện trong Claude Desktop

- Kiểm tra đường dẫn trong `claude_desktop_config.json` có đúng không
- Đảm bảo đã restart Claude Desktop hoàn toàn (thoát hẳn, không chỉ đóng cửa sổ)
- Chạy thử `python server.py` trong terminal để kiểm tra lỗi

### Lỗi sau khi gọi `auth_confirm`

- Đảm bảo bạn đã **hoàn thành xác thực trên browser** trước khi gọi `auth_confirm`
- Mã xác thực hết hạn sau ~15 phút — nếu quá thời gian, gọi lại `auth_login` để lấy mã mới

### Token hết hạn

Token tự động refresh. Nếu bị lỗi xác thực sau 90 ngày, gọi lại `auth_login` để đăng nhập mới.

---

## Cấu trúc dự án

```
mcp-server/
├── server.py           # Entry point
├── config.py           # Cấu hình và constants
├── pyproject.toml      # Dependencies
├── .env                # Biến môi trường (KHÔNG commit file này)
├── .env.example        # File mẫu
├── auth/               # Xác thực Microsoft
│   ├── device_flow.py  # MSAL Device Code Flow
│   ├── token_cache.py  # Lưu trữ token
│   ├── tools.py        # MCP tools: login/confirm/status/logout
│   └── __init__.py
├── graph/              # Microsoft Graph API client
│   ├── client.py       # HTTP client, pagination
│   └── __init__.py
├── mail/               # Email operations
│   ├── list_emails.py
│   ├── read_email.py
│   ├── search_emails.py
│   ├── drafts.py       # create/list/update/delete/send draft
│   ├── send_email.py
│   ├── mark_as_read.py
│   ├── folder_utils.py
│   └── __init__.py
└── utils/              # Tiện ích dùng chung
    ├── html_sanitizer.py
    └── formatting.py
```

---

## Mở rộng

Để thêm tính năng mới (ví dụ Calendar):

1. Tạo thư mục `calendar/` với các file tương tự `mail/`
2. Viết `calendar/__init__.py` với hàm `register_calendar_tools(mcp)`
3. Thêm vào `server.py`:
   ```python
   from calendar import register_calendar_tools
   register_calendar_tools(mcp)
   ```

Không cần thay đổi bất kỳ file nào khác.
