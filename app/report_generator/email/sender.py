"""
EMLGenerator — builds a .eml file ready to open in Outlook.

Usage::

    from .sender import EMLGenerator

    gen = EMLGenerator()
    eml_bytes = gen.generate_eml(
        html_content="<html>…</html>",
        subject="Executive Report — Week 27, 2026",
    )
    # eml_bytes can be served as a file download or saved to disk
"""

from __future__ import annotations

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


class EMLGenerator:
    """Builds a ``.eml`` file (RFC 2822 MIME message) for manual sending.

    The generated message has no ``From`` or ``To`` headers so that Outlook
    prompts the user to fill them in when they open the file, exactly like
    composing a new email.
    """

    @staticmethod
    def generate_eml(
        html_content: str,
        subject: str,
    ) -> bytes:
        """Build a ``.eml`` file as bytes.

        Parameters
        ----------
        html_content : str
            Full HTML document (including ``<!DOCTYPE html>``).
        subject : str
            Email subject line (shown in Outlook's subject field).

        Returns
        -------
        bytes
            The raw ``.eml`` file content, ready to serve as a download or
            write to disk.
        """
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = ""
        msg["To"] = ""

        part = MIMEText(html_content, "html", _charset="utf-8")
        msg.attach(part)

        return msg.as_bytes()
