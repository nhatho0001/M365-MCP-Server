from datetime import datetime


def _addr(recipient: dict) -> str:
    ea = recipient.get("emailAddress", {})
    name = ea.get("name", "")
    addr = ea.get("address", "")
    if name and name != addr:
        return f"{name} <{addr}>"
    return addr


def _addrs(recipients: list[dict]) -> str:
    return ", ".join(_addr(r) for r in recipients) if recipients else "(trống)"


def _date(dt_str: str) -> str:
    try:
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        return dt.strftime("%d/%m/%Y %H:%M")
    except Exception:
        return dt_str


def format_email_summary(msg: dict, idx: int) -> str:
    status = "" if msg.get("isRead") else "[CHƯA ĐỌC] "
    attach = " 📎" if msg.get("hasAttachments") else ""
    sender = _addr(msg.get("from", {}))
    date = _date(msg.get("receivedDateTime", ""))
    subject = msg.get("subject") or "(không có tiêu đề)"
    preview = msg.get("bodyPreview", "")[:100]
    msg_id = msg.get("id", "")

    return (
        f"{idx}. {status}{subject}{attach}\n"
        f"   Từ: {sender}\n"
        f"   Ngày: {date}\n"
        f"   ID: {msg_id}\n"
        f"   Xem trước: {preview}..."
    )


def format_email_detail(msg: dict, body_text: str) -> str:
    subject = msg.get("subject") or "(không có tiêu đề)"
    sender = _addr(msg.get("from", {}))
    to_list = _addrs(msg.get("toRecipients", []))
    cc_list = _addrs(msg.get("ccRecipients", []))
    bcc_list = _addrs(msg.get("bccRecipients", []))
    date = _date(msg.get("receivedDateTime", ""))
    status = "Chưa đọc" if not msg.get("isRead") else "Đã đọc"
    importance = msg.get("importance", "normal")
    has_attach = "Có" if msg.get("hasAttachments") else "Không"

    lines = [
        f"Tiêu đề : {subject}",
        f"Từ      : {sender}",
        f"Đến     : {to_list}",
    ]
    if msg.get("ccRecipients"):
        lines.append(f"CC      : {cc_list}")
    if msg.get("bccRecipients"):
        lines.append(f"BCC     : {bcc_list}")
    lines += [
        f"Ngày    : {date}",
        f"Trạng thái: {status}",
        f"Độ ưu tiên: {importance}",
        f"Đính kèm: {has_attach}",
        f"ID      : {msg.get('id', '')}",
        "",
        "─" * 60,
        "",
        body_text,
    ]
    return "\n".join(lines)


def format_draft_summary(msg: dict, idx: int) -> str:
    to_list = _addrs(msg.get("toRecipients", []))
    subject = msg.get("subject") or "(không có tiêu đề)"
    preview = msg.get("bodyPreview", "")[:80]
    msg_id = msg.get("id", "")

    return (
        f"{idx}. {subject}\n"
        f"   Đến: {to_list}\n"
        f"   ID: {msg_id}\n"
        f"   Xem trước: {preview}..."
    )
