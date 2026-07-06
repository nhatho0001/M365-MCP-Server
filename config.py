import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

GRAPH_BASE = "https://graph.microsoft.com/v1.0"
TOKEN_PATH = Path.home() / ".outlook-mcp-tokens.json"

AZURE_CLIENT_ID = os.getenv("AZURE_CLIENT_ID", "")
AZURE_TENANT_ID = os.getenv("AZURE_TENANT_ID", "common")

SCOPES = [
    "Mail.Read",
    "Mail.ReadWrite",
    "Mail.Send",
    "User.Read",
]

EMAIL_SELECT = (
    "id,subject,from,toRecipients,ccRecipients,"
    "receivedDateTime,bodyPreview,hasAttachments,importance,isRead"
)

EMAIL_DETAIL_SELECT = (
    "id,subject,from,toRecipients,ccRecipients,bccRecipients,"
    "receivedDateTime,body,bodyPreview,hasAttachments,importance,isRead"
)

DEFAULT_PAGE_SIZE = 25
MAX_RESULT_COUNT = 50
