import json

from auth import ensure_authenticated
from sharepoint.excel_common import (
    build_field_names,
    fetch_excel_bytes,
    normalize_cell_value,
    open_workbook_sheet,
    row_matches,
)


async def filter_excel_impl(
    sharepoint_url: str,
    filters: dict[str, list[str]],
    sheet_name: str | None = None,
    max_rows: int = 100,
) -> str:
    if not filters:
        return "Lỗi: Cần ít nhất 1 điều kiện filter (column → danh sách giá trị)."

    token = ensure_authenticated()

    fetch_result = await fetch_excel_bytes(sharepoint_url, token)
    if isinstance(fetch_result, str):
        return fetch_result
    file_name, file_path, file_size, file_bytes, site_display = fetch_result

    sheet_result = open_workbook_sheet(file_bytes, sheet_name)
    if isinstance(sheet_result, str):
        return sheet_result
    wb, ws, sheet_names, target_sheet = sheet_result

    header_row: list | None = None
    field_names: list[str] = []
    matched_records: list[dict] = []
    total_data_rows = 0
    total_matched = 0

    for row in ws.iter_rows(values_only=True):
        if all(cell is None for cell in row):
            continue

        if header_row is None:
            header_row = list(row)
            field_names = build_field_names(header_row)
            unknown_columns = [c for c in filters if c not in field_names]
            if unknown_columns:
                wb.close()
                return (
                    f"Lỗi: Không tìm thấy column {unknown_columns} trong sheet "
                    f"'{target_sheet}'. Các column hiện có: {field_names}"
                )
            continue

        total_data_rows += 1
        record = {
            name: normalize_cell_value(row[i] if i < len(row) else None)
            for i, name in enumerate(field_names)
        }
        if row_matches(record, filters):
            total_matched += 1
            if len(matched_records) < max_rows:
                matched_records.append(record)

    wb.close()

    rows_returned = len(matched_records)
    truncated = total_matched > rows_returned

    result = {
        "site": site_display,
        "file_name": file_name,
        "file_path": file_path,
        "file_size_bytes": file_size,
        "sheet_names": sheet_names,
        "sheet": target_sheet,
        "filters": filters,
        "total_rows_scanned": total_data_rows,
        "total_matched": total_matched,
        "rows_returned": rows_returned,
        "truncated": truncated,
        "columns": field_names,
        "rows": matched_records,
    }

    return json.dumps(result, ensure_ascii=False, indent=2)
