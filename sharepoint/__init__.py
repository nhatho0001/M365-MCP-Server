from mcp.server.fastmcp import FastMCP
from sharepoint.filter_excel import filter_excel_impl
from sharepoint.read_excel import read_excel_impl
from sharepoint.update_excel import update_excel_impl


def register_sharepoint_tools(mcp: FastMCP) -> None:
    @mcp.tool()
    async def read_sharepoint_excel(
        sharepoint_url: str,
        sheet_name: str | None = None,
        max_rows: int = 100,
    ) -> str:
        """
        Đọc nội dung file Excel (.xlsx) từ SharePoint Online.

        Trả về chuỗi JSON (không phải markdown table) là một object gồm:
        - Metadata: site, file_name, file_path, file_size_bytes, sheet_names,
          sheet, total_rows, rows_returned, truncated, columns.
        - "rows": mảng object — mỗi object là một dòng dữ liệu, key lấy từ
          header row (dòng đầu tiên của sheet), value giữ nguyên kiểu gốc
          (string/number/boolean/null); riêng datetime/date/time trong Excel
          được convert sang chuỗi ISO 8601.

        Args:
            sharepoint_url: URL đầy đủ tới file Excel trên SharePoint.
                            Ví dụ: https://company.sharepoint.com/sites/MySite/Shared Documents/data.xlsx
            sheet_name: Tên sheet cần đọc. Mặc định đọc sheet đầu tiên.
            max_rows: Số dòng dữ liệu tối đa trả về trong "rows" (mặc định 100, không tính header).
        """
        return await read_excel_impl(sharepoint_url, sheet_name, max_rows)

    @mcp.tool()
    async def filter_sharepoint_excel(
        sharepoint_url: str,
        filters: dict[str, list[str]],
        sheet_name: str | None = None,
        max_rows: int = 100,
    ) -> str:
        """
        Đọc file Excel (.xlsx) từ SharePoint Online, chỉ trả về các dòng khớp
        điều kiện filter theo giá trị cột.

        `filters` là object dạng {tên_cột: [giá_trị_1, giá_trị_2, ...]}. Một
        dòng được coi là khớp khi: với MỌI cột có mặt trong filters, giá trị
        của dòng ở cột đó nằm trong danh sách giá trị cho phép (điều kiện AND
        giữa các cột khác nhau, OR giữa các giá trị trong cùng 1 cột). So sánh
        thực hiện dưới dạng chuỗi (str), không phân biệt kiểu số/text gốc.
        Ví dụ: {"Status": ["Active", "Pending"], "Region": ["North"]} → lấy các
        dòng có Status là Active HOẶC Pending, VÀ Region là North.

        Tên cột trong filters phải khớp với tên ở header row (dòng đầu tiên
        của sheet) hoặc tên đã được trả về trong "columns" từ lần gọi
        read_sharepoint_excel trước đó. Nếu 1 cột trong filters không tồn tại
        trong sheet, tool trả về lỗi kèm danh sách cột hợp lệ.

        Trả về chuỗi JSON gồm:
        - Metadata: site, file_name, file_path, file_size_bytes, sheet_names,
          sheet, filters, total_rows_scanned, total_matched, rows_returned,
          truncated, columns.
        - "rows": mảng object — các dòng khớp filter, key lấy từ header row,
          value giữ nguyên kiểu gốc (string/number/boolean/null); riêng
          datetime/date/time trong Excel được convert sang chuỗi ISO 8601.

        Args:
            sharepoint_url: URL đầy đủ tới file Excel trên SharePoint.
                            Ví dụ: https://company.sharepoint.com/sites/MySite/Shared Documents/data.xlsx
            filters: Object {tên_cột: [giá_trị_cho_phép, ...]}. Bắt buộc có ít nhất 1 cột.
            sheet_name: Tên sheet cần đọc. Mặc định đọc sheet đầu tiên.
            max_rows: Số dòng khớp filter tối đa trả về trong "rows" (mặc định 100).
        """
        return await filter_excel_impl(sharepoint_url, filters, sheet_name, max_rows)

    @mcp.tool()
    async def update_sharepoint_excel(
        sharepoint_url: str,
        operations: list[dict],
        sheet_name: str | None = None,
        dry_run: bool = True,
        max_cells: int = 500,
    ) -> str:
        """
        Cập nhật file Excel (.xlsx) trên SharePoint Online qua Graph Workbook API
        (chỉ ghi các ô thay đổi, giữ nguyên format/chart/pivot của file).

        MẶC ĐỊNH dry_run=true: chỉ trả về preview (ô nào đổi từ giá trị cũ sang
        mới), KHÔNG ghi gì. Hãy cho user xem preview và chỉ gọi lại với
        dry_run=false sau khi user xác nhận.

        `operations` là mảng các object, mỗi object có "type":
        - "set_cells": ghi thẳng theo địa chỉ ô.
          {"type": "set_cells", "range": "B2:C3", "values": [[1, 2], [3, 4]]}
          (values là mảng 2 chiều, kích thước phải khớp range)
        - "update_rows": tìm dòng khớp filter rồi sửa các cột theo tên header.
          {"type": "update_rows",
           "filters": {"ID": ["1001", "1002"], "Region": ["North"]},
           "set": {"Status": "Done", "Note": ""}}
          filters cùng ngữ nghĩa filter_sharepoint_excel (AND giữa cột, OR giữa
          các giá trị, so sánh dạng chuỗi). Tên cột lấy từ header row (dòng đầu
          của vùng dữ liệu) — xem "columns" từ read_sharepoint_excel.
        - "append_rows": thêm dòng mới sau dòng dữ liệu cuối, map theo tên cột.
          {"type": "append_rows", "rows": [{"ID": "1003", "Status": "New"}]}
          Cột không nêu trong row để trống.

        Value chỉ nhận string/number/boolean/null (null hoặc "" = xoá ô). Chuỗi
        bắt đầu bằng "=" sẽ được Excel hiểu là công thức. Các operation được
        áp dụng lần lượt trên cùng 1 sheet; operation sau thấy kết quả của
        operation trước.

        Trả về JSON: site, file_name, file_path, sheet, dry_run, cells_changed,
        rows_matched, rows_appended, warnings (vd. ghi đè công thức), changes
        (tối đa 200 mục {cell, old, new}), và khi ghi thật: ranges_written,
        errors. Việc ghi KHÔNG atomic: nếu lỗi giữa chừng, các vùng đã ghi vẫn
        được giữ (xem ranges_written).

        Args:
            sharepoint_url: URL tới file Excel trên SharePoint (sharing link hoặc direct URL). Cần quyền chỉnh sửa.
            operations: Danh sách thao tác như mô tả ở trên. Bắt buộc có ít nhất 1.
            sheet_name: Tên sheet cần sửa. Mặc định sheet đầu tiên.
            dry_run: true (mặc định) = chỉ preview; false = ghi thật.
            max_cells: Số ô tối đa được phép thay đổi trong 1 lần gọi (mặc định 500).
        """
        return await update_excel_impl(
            sharepoint_url, operations, sheet_name, dry_run, max_cells
        )
