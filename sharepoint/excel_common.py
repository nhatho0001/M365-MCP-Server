import base64
import datetime
from io import BytesIO
from urllib.parse import unquote, urlparse

import openpyxl
from openpyxl.worksheet.worksheet import Worksheet
from openpyxl.workbook import Workbook

from graph.client import graph_download, graph_download_url, graph_get

# ---------------------------------------------------------------------------
# Helpers — URL detection & encoding
# ---------------------------------------------------------------------------


def is_sharing_link(url: str) -> bool:
    """Kiểm tra URL có phải dạng SharePoint sharing link không.

    Sharing links có dạng: https://tenant.sharepoint.com/:x:/s/Site/FileID
    Ký tự đặc biệt '/:' ở đầu path là dấu hiệu nhận biết.
    """
    return urlparse(url).path.startswith("/:")


def _encode_sharing_url(url: str) -> str:
    """Encode sharing URL sang shareId cho Graph API /shares endpoint.

    Theo tài liệu Microsoft:
      1. Base64url-encode toàn bộ URL
      2. Bỏ ký tự padding '='
      3. Thêm prefix 'u!'
    """
    encoded = base64.urlsafe_b64encode(url.encode()).decode().rstrip("=")
    return f"u!{encoded}"


# ---------------------------------------------------------------------------
# Helpers — URL parsing (direct link)
# ---------------------------------------------------------------------------


def _parse_sharepoint_url(url: str) -> tuple[str, str, str]:
    """Tách URL SharePoint thành (hostname, site_path, file_path).

    Ví dụ:
      https://contoso.sharepoint.com/sites/MySite/Shared Documents/folder/file.xlsx
      → ('contoso.sharepoint.com', '/sites/MySite', 'Shared Documents/folder/file.xlsx')
    """
    parsed = urlparse(url)
    hostname = parsed.netloc
    path = unquote(parsed.path)

    for prefix in ("/sites/", "/teams/"):
        if prefix in path:
            idx = path.index(prefix)
            after_prefix = path[idx + len(prefix):]
            parts = after_prefix.split("/", 1)
            site_path = prefix + parts[0]
            file_path = parts[1] if len(parts) > 1 else ""
            return hostname, site_path, file_path

    # Root site — toàn bộ path là đường dẫn file
    return hostname, "", path.lstrip("/")


# ---------------------------------------------------------------------------
# Helpers — Sharing link resolution
# ---------------------------------------------------------------------------


async def _resolve_sharing_link(url: str, token: str) -> tuple[str, str, int, bytes]:
    """Resolve SharePoint sharing link → (file_name, file_path, file_size, file_bytes).

    Sử dụng Graph API endpoint: GET /shares/{shareId}/driveItem
    """
    share_id = _encode_sharing_url(url)

    # 1. Lấy thông tin driveItem từ sharing link
    item_data = await graph_get(
        f"shares/{share_id}/driveItem",
        token,
        params={
            "$select": "id,name,size,parentReference,@microsoft.graph.downloadUrl"
        },
    )

    file_name = item_data.get("name", "unknown")
    file_size = item_data.get("size", 0)

    # 2. Tạo đường dẫn hiển thị từ parentReference
    parent_ref = item_data.get("parentReference", {})
    parent_path = parent_ref.get("path", "")
    file_path = file_name
    if "root:/" in parent_path:
        rel = parent_path.split("root:/", 1)[1]
        file_path = f"{rel}/{file_name}" if rel else file_name

    # 3. Download file
    # Ưu tiên dùng pre-authenticated downloadUrl (không cần Authorization header)
    download_url = item_data.get("@microsoft.graph.downloadUrl")
    if download_url:
        file_bytes = await graph_download_url(download_url)
    else:
        # Fallback: download qua Graph API với token
        drive_id = parent_ref.get("driveId", "")
        item_id = item_data.get("id", "")
        if not drive_id or not item_id:
            raise ValueError(
                "Không lấy được driveId hoặc itemId từ sharing link. "
                "Kiểm tra quyền truy cập file."
            )
        file_bytes = await graph_download(
            f"drives/{drive_id}/items/{item_id}/content", token
        )

    return file_name, file_path, file_size, file_bytes


# ---------------------------------------------------------------------------
# Helpers — Fetch file bytes (dùng chung cho mọi tool đọc Excel từ SharePoint)
# ---------------------------------------------------------------------------


async def fetch_excel_bytes(
    sharepoint_url: str, token: str
) -> tuple[str, str, int, bytes, str] | str:
    """Resolve + download file Excel từ SharePoint URL (sharing link hoặc direct URL).

    Trả về tuple (file_name, file_path, file_size, file_bytes, site_display) khi
    thành công, hoặc str thông báo lỗi (tiếng Việt, có thể trả thẳng cho user) khi
    thất bại — caller phân biệt 2 trường hợp bằng isinstance(result, str).
    """
    if is_sharing_link(sharepoint_url):
        try:
            file_name, file_path, file_size, file_bytes = await _resolve_sharing_link(
                sharepoint_url, token
            )
        except PermissionError as exc:
            return f"Lỗi quyền truy cập: {exc}"
        except ValueError as exc:
            return f"Lỗi khi resolve sharing link: {exc}"
        except Exception as exc:
            return f"Lỗi không xác định: {exc}"

        if not file_name.lower().endswith((".xlsx", ".xlsm", ".xlam")):
            return (
                f"Lỗi: Chỉ hỗ trợ file Excel định dạng .xlsx / .xlsm / .xlam. "
                f"File được resolve: {file_name}"
            )

        return file_name, file_path, file_size, file_bytes, sharepoint_url

    # Direct URL
    if not sharepoint_url.lower().endswith((".xlsx", ".xlsm", ".xlam")):
        return (
            "Lỗi: Chỉ hỗ trợ file Excel định dạng .xlsx / .xlsm / .xlam. "
            f"File được cung cấp: {sharepoint_url}"
        )

    hostname, site_path, file_path = _parse_sharepoint_url(sharepoint_url)
    if not hostname:
        return f"Lỗi: Không thể phân tích URL SharePoint: {sharepoint_url}"

    site_api_path = (
        f"sites/{hostname}:{site_path}" if site_path else f"sites/{hostname}"
    )
    try:
        site_data = await graph_get(site_api_path, token)
    except ValueError:
        return (
            f"Lỗi: Không tìm thấy SharePoint site tại '{hostname}{site_path}'. "
            "Kiểm tra lại URL hoặc quyền truy cập."
        )

    site_id = site_data.get("id", "")
    site_display = site_data.get("webUrl", sharepoint_url)

    file_api_path = f"sites/{site_id}/drive/root:/{file_path}"
    try:
        item_data = await graph_get(file_api_path, token)
    except ValueError:
        return (
            f"Lỗi: Không tìm thấy file '{file_path}' trong site. "
            "Kiểm tra lại đường dẫn file trong URL."
        )

    item_id = item_data.get("id", "")
    file_name = item_data.get("name", file_path.split("/")[-1])
    file_size = item_data.get("size", 0)

    download_path = f"sites/{site_id}/drive/items/{item_id}/content"
    try:
        file_bytes = await graph_download(download_path, token)
    except Exception as exc:
        return f"Lỗi khi tải file: {exc}"

    return file_name, file_path, file_size, file_bytes, site_display


# ---------------------------------------------------------------------------
# Helpers — Resolve driveItem (không download; dùng cho tool ghi qua Workbook API)
# ---------------------------------------------------------------------------


async def resolve_drive_item(sharepoint_url: str, token: str) -> dict | str:
    """Resolve SharePoint URL (sharing link hoặc direct URL) → thông tin driveItem.

    Thành công: dict gồm drive_id, item_id, file_name, file_path, site.
    Thất bại: str thông báo lỗi (tiếng Việt) — caller phân biệt bằng isinstance(str).
    """
    if is_sharing_link(sharepoint_url):
        try:
            item = await graph_get(
                f"shares/{_encode_sharing_url(sharepoint_url)}/driveItem",
                token,
                params={"$select": "id,name,parentReference"},
            )
        except PermissionError as exc:
            return f"Lỗi quyền truy cập: {exc}"
        except ValueError as exc:
            return f"Lỗi khi resolve sharing link: {exc}"
        except Exception as exc:
            return f"Lỗi không xác định: {exc}"

        file_name = item.get("name", "unknown")
        parent_ref = item.get("parentReference", {})
        parent_path = parent_ref.get("path", "")
        file_path = file_name
        if "root:/" in parent_path:
            rel = parent_path.split("root:/", 1)[1]
            file_path = f"{rel}/{file_name}" if rel else file_name
        site = sharepoint_url
    else:
        hostname, site_path, file_path = _parse_sharepoint_url(sharepoint_url)
        if not hostname:
            return f"Lỗi: Không thể phân tích URL SharePoint: {sharepoint_url}"

        site_api_path = (
            f"sites/{hostname}:{site_path}" if site_path else f"sites/{hostname}"
        )
        try:
            site_data = await graph_get(site_api_path, token)
        except ValueError:
            return (
                f"Lỗi: Không tìm thấy SharePoint site tại '{hostname}{site_path}'. "
                "Kiểm tra lại URL hoặc quyền truy cập."
            )
        except PermissionError as exc:
            return f"Lỗi quyền truy cập: {exc}"

        site = site_data.get("webUrl", sharepoint_url)
        try:
            item = await graph_get(
                f"sites/{site_data.get('id', '')}/drive/root:/{file_path}",
                token,
                params={"$select": "id,name,parentReference"},
            )
        except ValueError:
            return (
                f"Lỗi: Không tìm thấy file '{file_path}' trong site. "
                "Kiểm tra lại đường dẫn file trong URL."
            )
        except PermissionError as exc:
            return f"Lỗi quyền truy cập: {exc}"
        file_name = item.get("name", file_path.split("/")[-1])
        parent_ref = item.get("parentReference", {})

    drive_id = parent_ref.get("driveId", "")
    item_id = item.get("id", "")
    if not drive_id or not item_id:
        return "Lỗi: Không lấy được driveId/itemId của file. Kiểm tra quyền truy cập."

    return {
        "drive_id": drive_id,
        "item_id": item_id,
        "file_name": file_name,
        "file_path": file_path,
        "site": site,
    }


# ---------------------------------------------------------------------------
# Helpers — Workbook / sheet
# ---------------------------------------------------------------------------


def open_workbook_sheet(
    file_bytes: bytes, sheet_name: str | None
) -> tuple[Workbook, Worksheet, list[str], str] | str:
    """Mở workbook (read-only) và chọn sheet cần đọc.

    Trả về (workbook, worksheet, sheet_names, target_sheet) khi thành công, hoặc
    str thông báo lỗi khi thất bại. Caller chịu trách nhiệm gọi workbook.close()
    sau khi đọc xong worksheet.
    """
    try:
        wb = openpyxl.load_workbook(BytesIO(file_bytes), read_only=True, data_only=True)
    except Exception as exc:
        return f"Lỗi khi đọc file Excel: {exc}"

    sheet_names = wb.sheetnames
    if sheet_name is not None and sheet_name not in sheet_names:
        wb.close()
        return (
            f"Lỗi: Không tìm thấy sheet '{sheet_name}'. "
            f"Các sheet hiện có: {', '.join(sheet_names)}"
        )

    target_sheet = sheet_name or sheet_names[0]
    ws = wb[target_sheet]
    return wb, ws, sheet_names, target_sheet


# ---------------------------------------------------------------------------
# Helpers — JSON conversion
# ---------------------------------------------------------------------------


def build_field_names(header_row: list) -> list[str]:
    """Chuyển header row thành list tên field JSON duy nhất.

    Cell None/rỗng → placeholder 'Column_N' (N là vị trí 1-indexed).
    Tên trùng nhau (kể cả trùng placeholder) → thêm hậu tố _2, _3, ...
    """
    used: set[str] = set()
    field_names: list[str] = []
    for idx, cell in enumerate(header_row, start=1):
        if cell is None:
            base_name = f"Column_{idx}"
        else:
            text = str(cell).strip()
            base_name = text if text else f"Column_{idx}"

        name = base_name
        suffix = 2
        while name in used:
            name = f"{base_name}_{suffix}"
            suffix += 1

        used.add(name)
        field_names.append(name)
    return field_names


def normalize_cell_value(value):
    """Chuyển 1 cell value sang kiểu JSON-serializable.

    Giữ nguyên str/int/float/bool/None để AI filter số/boolean chính xác.
    datetime/date/time convert qua .isoformat() vì json.dumps không tự serialize được.
    """
    if isinstance(value, (datetime.datetime, datetime.date, datetime.time)):
        return value.isoformat()
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def row_matches(record: dict, filters: dict[str, list[str]]) -> bool:
    """1 row khớp filter khi: với MỌI column trong filters, giá trị cell nằm
    trong danh sách giá trị cho phép của column đó (AND giữa các column,
    OR giữa các giá trị trong cùng 1 column). So sánh dạng chuỗi (str)."""
    for column, allowed_values in filters.items():
        allowed_strs = {str(v) for v in allowed_values}
        cell_value = record.get(column)
        cell_str = "" if cell_value is None else str(cell_value)
        if cell_str not in allowed_strs:
            return False
    return True


def rows_to_records(field_names: list[str], data_rows: list[list]) -> list[dict]:
    """Zip mỗi data row với field_names thành 1 dict/record.

    Row ngắn hơn header → key thiếu nhận None. Row dài hơn → cell thừa bị bỏ qua.
    """
    records: list[dict] = []
    for row in data_rows:
        record = {}
        for i, name in enumerate(field_names):
            raw_value = row[i] if i < len(row) else None
            record[name] = normalize_cell_value(raw_value)
        records.append(record)
    return records
