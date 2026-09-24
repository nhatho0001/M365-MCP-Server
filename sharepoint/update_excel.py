import json
from urllib.parse import quote

import httpx
from openpyxl.utils import get_column_letter
from openpyxl.utils.cell import range_boundaries

from auth import ensure_authenticated
from graph.client import graph_get, graph_patch, graph_post
from sharepoint.excel_common import build_field_names, resolve_drive_item, row_matches

MAX_PREVIEW_CHANGES = 200
_SCALAR_TYPES = (str, int, float, bool, type(None))

# (row, col) tuyệt đối, 0-indexed trong sheet
Cell = tuple[int, int]


# ---------------------------------------------------------------------------
# Helpers — lập kế hoạch thay đổi (thuần logic, không gọi mạng)
# ---------------------------------------------------------------------------


def _cell_address(row: int, col: int) -> str:
    return f"{get_column_letter(col + 1)}{row + 1}"


def _clean_value(value):
    """Graph coi null trong `values` là 'không đổi'; muốn xoá ô phải gửi ''."""
    return "" if value is None else value


def _plan_changes(
    values: list[list],
    formulas: list[list],
    start_row: int,
    start_col: int,
    operations: list[dict],
) -> dict | str:
    """Chuyển danh sách operations thành dict thay đổi {(row, col): giá trị mới}.

    Trả về dict {changes, warnings, matched_rows, rows_appended, header} hoặc str lỗi.
    """
    if not values or all(v in (None, "") for v in values[0]):
        return "Lỗi: Sheet trống hoặc dòng đầu tiên (header) rỗng."

    field_names = build_field_names([None if v == "" else v for v in values[0]])
    col_of = {name: start_col + i for i, name in enumerate(field_names)}

    original: dict[Cell, object] = {}
    formula_cells: set[Cell] = set()
    for i, row in enumerate(values):
        for j, v in enumerate(row):
            original[(start_row + i, start_col + j)] = v
    for i, row in enumerate(formulas):
        for j, f in enumerate(row):
            if isinstance(f, str) and f.startswith("="):
                formula_cells.add((start_row + i, start_col + j))

    last_row = start_row
    for (r, _), v in original.items():
        if v not in (None, ""):
            last_row = max(last_row, r)
    next_row = last_row + 1

    changes: dict[Cell, object] = {}
    matched_rows = 0
    rows_appended = 0

    def current(cell: Cell):
        return changes.get(cell, original.get(cell, ""))

    def check_scalar(value, where: str) -> str | None:
        if not isinstance(value, _SCALAR_TYPES):
            return f"Lỗi: {where} chỉ nhận string/number/boolean/null, nhận {type(value).__name__}."
        return None

    def check_columns(columns, where: str) -> str | None:
        unknown = [c for c in columns if c not in col_of]
        if unknown:
            return (
                f"Lỗi: {where} — không tìm thấy column {unknown}. "
                f"Các column hiện có: {field_names}"
            )
        return None

    for idx, op in enumerate(operations):
        where = f"operations[{idx}]"
        if not isinstance(op, dict):
            return f"Lỗi: {where} phải là object."
        op_type = op.get("type")

        if op_type == "set_cells":
            range_str, grid = op.get("range"), op.get("values")
            if not isinstance(range_str, str) or not isinstance(grid, list):
                return f"Lỗi: {where} (set_cells) cần 'range' (str) và 'values' (mảng 2 chiều)."
            try:
                min_col, min_row, max_col, max_row = range_boundaries(range_str)
            except Exception:
                return f"Lỗi: {where} range '{range_str}' không hợp lệ (ví dụ 'B2:C3')."
            if None in (min_col, min_row, max_col, max_row):
                return f"Lỗi: {where} range '{range_str}' phải là vùng ô cụ thể (ví dụ 'B2:C3')."
            n_rows, n_cols = max_row - min_row + 1, max_col - min_col + 1
            if (
                len(grid) != n_rows
                or not all(isinstance(r, list) and len(r) == n_cols for r in grid)
            ):
                return (
                    f"Lỗi: {where} 'values' phải có kích thước {n_rows} dòng x "
                    f"{n_cols} cột để khớp range '{range_str}'."
                )
            for i, row_vals in enumerate(grid):
                for j, v in enumerate(row_vals):
                    if err := check_scalar(v, f"{where}.values[{i}][{j}]"):
                        return err
                    changes[(min_row - 1 + i, min_col - 1 + j)] = _clean_value(v)

        elif op_type == "update_rows":
            filters, set_map = op.get("filters"), op.get("set")
            if not isinstance(filters, dict) or not filters:
                return f"Lỗi: {where} (update_rows) cần 'filters' không rỗng."
            if not isinstance(set_map, dict) or not set_map:
                return f"Lỗi: {where} (update_rows) cần 'set' không rỗng."
            if err := check_columns(list(filters) + list(set_map), where):
                return err
            for col, v in set_map.items():
                if err := check_scalar(v, f"{where}.set['{col}']"):
                    return err
            for r in range(start_row + 1, next_row):
                record = {name: current((r, c)) for name, c in col_of.items()}
                if row_matches(record, filters):
                    matched_rows += 1
                    for col, v in set_map.items():
                        changes[(r, col_of[col])] = _clean_value(v)

        elif op_type == "append_rows":
            rows = op.get("rows")
            if not isinstance(rows, list) or not rows:
                return f"Lỗi: {where} (append_rows) cần 'rows' là mảng không rỗng."
            for i, rec in enumerate(rows):
                if not isinstance(rec, dict) or not rec:
                    return f"Lỗi: {where}.rows[{i}] phải là object {{column: giá_trị}} không rỗng."
                if err := check_columns(list(rec), f"{where}.rows[{i}]"):
                    return err
                for col, v in rec.items():
                    if err := check_scalar(v, f"{where}.rows[{i}]['{col}']"):
                        return err
                    changes[(next_row, col_of[col])] = _clean_value(v)
                next_row += 1
                rows_appended += 1

        else:
            return (
                f"Lỗi: {where} có type '{op_type}' không hợp lệ. "
                "Hỗ trợ: set_cells, update_rows, append_rows."
            )

    # Chỉ giữ ô thực sự thay đổi
    diff: dict[Cell, object] = {}
    warnings: list[str] = []
    for cell, new in changes.items():
        old = original.get(cell, "")
        if old == new or str(old) == str(new):
            continue
        diff[cell] = new
        if cell in formula_cells:
            warnings.append(f"Ô {_cell_address(*cell)} đang chứa công thức, sẽ bị ghi đè.")

    return {
        "diff": diff,
        "original": original,
        "warnings": warnings,
        "matched_rows": matched_rows,
        "rows_appended": rows_appended,
    }


def _build_blocks(diff: dict[Cell, object]) -> list[dict]:
    """Gộp các ô thay đổi liền kề thành các vùng chữ nhật để giảm số request.

    Ô nằm trong 1 vùng nhưng không thay đổi thì không xuất hiện (vùng chỉ được
    hình thành từ các ô liên tiếp đều có thay đổi).
    """
    by_row: dict[int, dict[int, object]] = {}
    for (r, c), v in diff.items():
        by_row.setdefault(r, {})[c] = v

    runs: list[tuple[int, int, int]] = []  # (row, col_start, col_end)
    for r in sorted(by_row):
        cols = sorted(by_row[r])
        start = prev = cols[0]
        for c in cols[1:]:
            if c == prev + 1:
                prev = c
                continue
            runs.append((r, start, prev))
            start = prev = c
        runs.append((r, start, prev))

    blocks: list[dict] = []
    open_blocks: dict[tuple[int, int], dict] = {}
    for r, c0, c1 in runs:
        row_vals = [by_row[r][c] for c in range(c0, c1 + 1)]
        block = open_blocks.get((c0, c1))
        if block and block["r1"] == r - 1:
            block["r1"] = r
            block["values"].append(row_vals)
        else:
            block = {"r0": r, "r1": r, "c0": c0, "c1": c1, "values": [row_vals]}
            blocks.append(block)
            open_blocks[(c0, c1)] = block

    for b in blocks:
        b["address"] = f"{_cell_address(b['r0'], b['c0'])}:{_cell_address(b['r1'], b['c1'])}"
    return blocks


# ---------------------------------------------------------------------------
# Impl
# ---------------------------------------------------------------------------


def _http_error_message(exc: httpx.HTTPStatusError) -> str:
    status = exc.response.status_code
    if status in (409, 423):
        return f"File đang bị khoá hoặc xung đột ({status}). Thử lại sau khi đóng file."
    detail = ""
    try:
        detail = exc.response.json().get("error", {}).get("message", "")
    except Exception:
        pass
    return f"Graph API lỗi {status}: {detail or exc}"


async def update_excel_impl(
    sharepoint_url: str,
    operations: list[dict],
    sheet_name: str | None = None,
    dry_run: bool = True,
    max_cells: int = 500,
) -> str:
    if not operations:
        return "Lỗi: Cần ít nhất 1 operation."

    token = ensure_authenticated()

    item = await resolve_drive_item(sharepoint_url, token)
    if isinstance(item, str):
        return item
    if not item["file_name"].lower().endswith(".xlsx"):
        return (
            "Lỗi: Ghi file chỉ hỗ trợ định dạng .xlsx. "
            f"File được resolve: {item['file_name']}"
        )

    wb_path = f"drives/{item['drive_id']}/items/{item['item_id']}/workbook"

    try:
        if sheet_name is None:
            sheets = await graph_get(
                f"{wb_path}/worksheets", token, params={"$select": "name", "$top": "1"}
            )
            names = [s.get("name") for s in sheets.get("value", [])]
            if not names:
                return "Lỗi: Workbook không có sheet nào."
            sheet_name = names[0]

        sheet_path = f"{wb_path}/worksheets/{quote(sheet_name, safe='')}"
        used = await graph_get(
            f"{sheet_path}/usedRange",
            token,
            params={"$select": "address,rowIndex,columnIndex,values,formulas"},
        )
    except ValueError:
        return f"Lỗi: Không tìm thấy sheet '{sheet_name}' hoặc workbook không truy cập được."
    except PermissionError as exc:
        return f"Lỗi quyền truy cập: {exc}"
    except httpx.HTTPStatusError as exc:
        return f"Lỗi khi đọc sheet: {_http_error_message(exc)}"

    plan = _plan_changes(
        used.get("values", []),
        used.get("formulas", []),
        used.get("rowIndex", 0),
        used.get("columnIndex", 0),
        operations,
    )
    if isinstance(plan, str):
        return plan

    diff: dict[Cell, object] = plan["diff"]
    if len(diff) > max_cells:
        return (
            f"Lỗi: Sẽ thay đổi {len(diff)} ô, vượt giới hạn max_cells={max_cells}. "
            "Thu hẹp filter hoặc tăng max_cells nếu chắc chắn."
        )

    original = plan["original"]
    change_list = [
        {
            "cell": _cell_address(*cell),
            "old": original.get(cell, ""),
            "new": new,
        }
        for cell, new in sorted(diff.items())
    ]
    blocks = _build_blocks(diff)

    result: dict = {
        "site": item["site"],
        "file_name": item["file_name"],
        "file_path": item["file_path"],
        "sheet": sheet_name,
        "dry_run": dry_run,
        "cells_changed": len(diff),
        "rows_matched": plan["matched_rows"],
        "rows_appended": plan["rows_appended"],
        "warnings": plan["warnings"],
        "changes": change_list[:MAX_PREVIEW_CHANGES],
        "changes_truncated": len(change_list) > MAX_PREVIEW_CHANGES,
    }

    if dry_run:
        result["note"] = "Chưa ghi gì vào file. Gọi lại với dry_run=false để áp dụng."
        return json.dumps(result, ensure_ascii=False, indent=2)

    if not diff:
        result["note"] = "Không có ô nào cần thay đổi."
        return json.dumps(result, ensure_ascii=False, indent=2)

    # Ghi thật: mở session, PATCH tuần tự từng vùng (Workbook API không khuyến
    # khích request song song trong 1 session), rồi đóng session.
    written: list[str] = []
    errors: list[str] = []
    session_id = ""
    try:
        session = await graph_post(
            f"{wb_path}/createSession", token, {"persistChanges": True}
        )
        session_id = session.get("id", "")
        headers = {"workbook-session-id": session_id} if session_id else None

        for block in blocks:
            try:
                await graph_patch(
                    f"{sheet_path}/range(address='{block['address']}')",
                    token,
                    {"values": block["values"]},
                    headers=headers,
                )
                written.append(block["address"])
            except httpx.HTTPStatusError as exc:
                errors.append(f"{block['address']}: {_http_error_message(exc)}")
                break
    except PermissionError as exc:
        errors.append(f"Lỗi quyền ghi: {exc}")
    except httpx.HTTPStatusError as exc:
        errors.append(_http_error_message(exc))
    except Exception as exc:
        errors.append(f"Lỗi không xác định: {exc}")
    finally:
        if session_id:
            try:
                await graph_post(
                    f"{wb_path}/closeSession",
                    token,
                    {},
                    headers={"workbook-session-id": session_id},
                )
            except Exception:
                pass

    result["ranges_written"] = written
    result["errors"] = errors
    if errors:
        result["note"] = (
            "Ghi dở dang: các vùng trong 'ranges_written' đã được lưu, phần còn lại thì chưa."
        )
    return json.dumps(result, ensure_ascii=False, indent=2)
