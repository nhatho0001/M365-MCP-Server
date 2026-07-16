from mcp.server.fastmcp import FastMCP
from sharepoint.filter_excel import filter_excel_impl
from sharepoint.read_excel import read_excel_impl


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
