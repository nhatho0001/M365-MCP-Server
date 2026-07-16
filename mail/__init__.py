from mcp.server.fastmcp import FastMCP
from mail.list_emails import list_emails_impl
from mail.read_email import read_email_impl
from mail.search_emails import search_emails_impl
from mail.drafts import (
    create_draft_impl,
    list_drafts_impl,
    update_draft_impl,
    delete_draft_impl,
    send_draft_impl,
)
from mail.send_email import send_email_impl
from mail.mark_as_read import mark_as_read_impl
from mail.attachments import list_attachments_impl, read_attachment_impl


def register_mail_tools(mcp: FastMCP) -> None:
    """Đăng ký tất cả email tools vào FastMCP instance.

    Để thêm tool mới: tạo file trong mail/, viết hàm _impl(),
    sau đó thêm @mcp.tool() wrapper ở đây.
    """

    @mcp.tool()
    async def list_emails(folder: str = "inbox", limit: int = 10) -> str:
        """Liệt kê email trong một folder.

        Args:
            folder: Tên folder (inbox, drafts, sent, deleted, junk, archive) hoặc tên tùy chỉnh.
            limit: Số lượng email tối đa (1-50).
        """
        return await list_emails_impl(folder, limit)

    @mcp.tool()
    async def read_email(message_id: str, mark_as_read: bool = False) -> str:
        """Đọc nội dung đầy đủ của một email theo ID.

        Args:
            message_id: ID của email (lấy từ list_emails hoặc search_emails).
            mark_as_read: Nếu True, đánh dấu email là đã đọc sau khi xem.
        """
        return await read_email_impl(message_id, mark_as_read)

    @mcp.tool()
    async def search_emails(
        query: str = "",
        folder: str = "inbox",
        from_address: str = "",
        subject: str = "",
        unread_only: bool = False,
        has_attachments: bool = False,
        from_date: str = "",
        to_date: str = "",
        limit: int = 10,
    ) -> str:
        """Tìm kiếm email với các điều kiện lọc.

        Lưu ý: from_address, subject, unread_only, has_attachments, from_date, to_date
        chỉ áp dụng khi 'query' để trống (query dùng $search, các filter còn lại dùng $filter).

        Args:
            query: Từ khóa tìm kiếm tự do (KQL). Ưu tiên hơn các filter khác.
            folder: Folder để tìm kiếm.
            from_address: Lọc theo địa chỉ email người gửi.
            subject: Lọc theo từ khóa trong tiêu đề.
            unread_only: Chỉ lấy email chưa đọc.
            has_attachments: Chỉ lấy email có đính kèm.
            from_date: Lọc email nhận từ ngày này trở đi. Định dạng 'YYYY-MM-DD' hoặc ISO 8601 datetime.
            to_date: Lọc email nhận đến ngày này. Định dạng 'YYYY-MM-DD' hoặc ISO 8601 datetime.
            limit: Số kết quả tối đa (1-50).
        """
        return await search_emails_impl(
            query,
            folder,
            from_address,
            subject,
            unread_only,
            has_attachments,
            from_date,
            to_date,
            limit,
        )

    @mcp.tool()
    async def create_draft(
        to: str = "",
        cc: str = "",
        bcc: str = "",
        subject: str = "",
        body: str = "",
        importance: str = "normal",
    ) -> str:
        """Tạo email nháp mới trong folder Drafts.

        Args:
            to: Địa chỉ email người nhận (nhiều địa chỉ cách nhau bằng dấu phẩy).
            cc: Địa chỉ CC (tùy chọn).
            bcc: Địa chỉ BCC (tùy chọn).
            subject: Tiêu đề email.
            body: Nội dung email (hỗ trợ plain text hoặc HTML).
            importance: Độ ưu tiên: low, normal, hoặc high.
        """
        return await create_draft_impl(to, cc, bcc, subject, body, importance)

    @mcp.tool()
    async def list_drafts(limit: int = 10) -> str:
        """Liệt kê các email nháp trong folder Drafts.

        Args:
            limit: Số lượng nháp tối đa (1-50).
        """
        return await list_drafts_impl(limit)

    @mcp.tool()
    async def update_draft(
        message_id: str,
        subject: str | None = None,
        body: str | None = None,
        to: str | None = None,
        cc: str | None = None,
        bcc: str | None = None,
    ) -> str:
        """Cập nhật nội dung email nháp đang tồn tại.

        Args:
            message_id: ID của email nháp cần cập nhật.
            subject: Tiêu đề mới (bỏ qua nếu không muốn thay đổi).
            body: Nội dung mới (bỏ qua nếu không muốn thay đổi).
            to: Người nhận mới (bỏ qua nếu không muốn thay đổi).
            cc: CC mới (bỏ qua nếu không muốn thay đổi).
            bcc: BCC mới (bỏ qua nếu không muốn thay đổi).
        """
        return await update_draft_impl(message_id, subject, body, to, cc, bcc)

    @mcp.tool()
    async def delete_draft(message_id: str) -> str:
        """Xóa vĩnh viễn một email nháp.

        Args:
            message_id: ID của email nháp cần xóa.
        """
        return await delete_draft_impl(message_id)

    @mcp.tool()
    async def send_draft(message_id: str) -> str:
        """Gửi một email nháp đã có sẵn.

        Args:
            message_id: ID của email nháp cần gửi.
        """
        return await send_draft_impl(message_id)

    @mcp.tool()
    async def send_email(
        to: str,
        subject: str,
        body: str,
        cc: str = "",
        bcc: str = "",
        is_html: bool = False,
        importance: str = "normal",
    ) -> str:
        """Soạn và gửi email ngay lập tức (không lưu nháp).

        Args:
            to: Địa chỉ email người nhận (nhiều địa chỉ cách nhau bằng dấu phẩy).
            subject: Tiêu đề email.
            body: Nội dung email.
            cc: Địa chỉ CC (tùy chọn).
            bcc: Địa chỉ BCC (tùy chọn).
            is_html: True nếu body là HTML, False nếu là plain text.
            importance: Độ ưu tiên: low, normal, hoặc high.
        """
        return await send_email_impl(to, subject, body, cc, bcc, is_html, importance)

    @mcp.tool()
    async def mark_email_as_read(message_id: str, is_read: bool = True) -> str:
        """Đánh dấu email là đã đọc hoặc chưa đọc.

        Args:
            message_id: ID của email.
            is_read: True để đánh dấu đã đọc, False để đánh dấu chưa đọc.
        """
        return await mark_as_read_impl(message_id, is_read)

    @mcp.tool()
    async def list_attachments(message_id: str) -> str:
        """Liệt kê tất cả file đính kèm của một email.

        Args:
            message_id: ID của email (lấy từ list_emails hoặc search_emails).
        """
        return await list_attachments_impl(message_id)

    @mcp.tool(structured_output=False)
    async def read_attachment(message_id: str, attachment_id: str) -> list | str:
        """Đọc và trả về nội dung file đính kèm trong email.

        Hỗ trợ: txt, csv, json, html, xml, md (text), xlsx (Excel),
        pdf (PDF), docx (Word), png/jpg/gif/webp (ảnh — hiển thị trực tiếp
        để xem nội dung). Định dạng ảnh khác và định dạng chưa hỗ trợ trả về thông báo.

        Args:
            message_id: ID của email chứa file đính kèm.
            attachment_id: ID của file đính kèm (lấy từ list_attachments).
        """
        return await read_attachment_impl(message_id, attachment_id)
