from auth import ensure_authenticated
from graph.client import graph_post
from mail.drafts import _build_recipients


async def send_email_impl(
    to: str,
    subject: str,
    body: str,
    cc: str = "",
    bcc: str = "",
    is_html: bool = False,
    importance: str = "normal",
    save_to_sent: bool = True,
) -> str:
    token = ensure_authenticated()
    content_type = "html" if is_html else "text"

    message: dict = {
        "subject": subject,
        "importance": importance,
        "body": {"contentType": content_type, "content": body},
        "toRecipients": _build_recipients(to),
    }
    if cc:
        message["ccRecipients"] = _build_recipients(cc)
    if bcc:
        message["bccRecipients"] = _build_recipients(bcc)

    payload = {
        "message": message,
        "saveToSentItems": save_to_sent,
    }
    await graph_post("me/sendMail", token, payload)
    return (
        f"Email đã được gửi thành công.\n"
        f"Tiêu đề: {subject}\n"
        f"Đến: {to}"
    )
