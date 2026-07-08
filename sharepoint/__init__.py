from mcp.server.fastmcp import FastMCP
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

        Args:
            sharepoint_url: URL đầy đủ tới file Excel trên SharePoint.
                            Ví dụ: https://company.sharepoint.com/sites/MySite/Shared Documents/data.xlsx
            sheet_name: Tên sheet cần đọc. Mặc định đọc sheet đầu tiên.
            max_rows: Số dòng tối đa trả về (mặc định 100, không tính header).
        """
        return await read_excel_impl(sharepoint_url, sheet_name, max_rows)
