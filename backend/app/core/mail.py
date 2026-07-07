"""Outbound mail port.

The only backend today is the console sender: it structlog-logs the message
so the dev flow for verification/reset is "read the token from the logs".
SMTP (or a provider API) is future work behind the same ``send`` interface;
``MAIL_BACKEND`` is the seam. The mail body is the ONLY place a raw action
token may appear — nothing else logs tokens.
"""
from dataclasses import dataclass

from app.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class MailMessage:
    to: str
    subject: str
    body: str


class ConsoleMailSender:
    def send(self, message: MailMessage) -> None:
        logger.info(
            "mail_sent",
            backend="console",
            to=message.to,
            subject=message.subject,
            body=message.body,
        )


def get_mail_sender() -> ConsoleMailSender:
    # Keyed on MAIL_BACKEND for when a real backend exists; the Literal type
    # on the setting means anything else fails at startup, not here.
    if settings.MAIL_BACKEND == "console":
        return ConsoleMailSender()
    raise ValueError(f"Unknown MAIL_BACKEND: {settings.MAIL_BACKEND}")
