import json

from auth import ensure_authenticated
from sharepoint.excel_common import (
    build_field_names,
    fetch_excel_bytes,
    open_workbook_sheet,
    rows_to_records,
)


async def read_excel_impl(
    sharepoint_url: str,
    sheet_name: str | None = None,
    max_rows: int = 100,
) -> str:
    token = ensure_authenticated()

    fetch_result = await fetch_excel_bytes(sharepoint_url, token)
    if isinstance(fetch_result, str):
        return fetch_result
    file_name, file_path, file_size, file_bytes, site_display = fetch_result

    sheet_result = open_workbook_sheet(file_bytes, sheet_name)
    if isinstance(sheet_result, str):
        return sheet_result
    wb, ws, sheet_names, target_sheet = sheet_result

    rows_data: list[list] = []
    total_rows = 0
    for row in ws.iter_rows(values_only=True):
        if all(cell is None for cell in row):
            continue
        total_rows += 1
        if len(rows_data) < max_rows + 1:  # +1 để tính cả header
            rows_data.append(list(row))

    wb.close()

    # Format output (JSON)
    if total_rows == 0:
        header_row: list = []
        data_rows: list[list] = []
    else:
        header_row = rows_data[0]
        data_rows = rows_data[1:]

    field_names = build_field_names(header_row)
    records = rows_to_records(field_names, data_rows)

    total_data_rows = max(total_rows - 1, 0)  # trừ header
    rows_returned = len(records)
    truncated = total_data_rows > rows_returned

    result = {
        "site": site_display,
        "file_name": file_name,
        "file_path": file_path,
        "file_size_bytes": file_size,
        "sheet_names": sheet_names,
        "sheet": target_sheet,
        "total_rows": total_data_rows,
        "rows_returned": rows_returned,
        "truncated": truncated,
        "columns": field_names,
        "rows": records,
    }

    return json.dumps(result, ensure_ascii=False, indent=2)
