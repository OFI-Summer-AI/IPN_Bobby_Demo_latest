"""
Bobby — SMTP Email Service & HTML Templates
============================================
Dispatches branded HTML email notifications for:
1. Ticket Created Confirmation
2. Ticket Escalated (P1 Urgent Alert)
3. Ticket Resolved Notification (with detailed resolution summary, agent name, and CSAT survey)
"""
from __future__ import annotations
import asyncio
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import structlog
from config.settings import settings

logger = structlog.get_logger(__name__)


def _send_sync_email(to_email: str, subject: str, body_html: str, body_text: str = "") -> bool:
    """Synchronous SMTP email delivery with multi-recipient routing."""
    username = settings.smtp_username or settings.smtp_user
    if not settings.smtp_host or not username:
        logger.info("email_service.mock_send", to=to_email, subject=subject, note="SMTP credentials not set; mock email logged")
        return True

    # 1. Determine all valid target email addresses
    recipients = set()
    if to_email and "@" in to_email:
        recipients.add(to_email.strip())

    # Add configured default alert recipients (e.g. developer / admin inbox)
    if settings.smtp_to_emails:
        for e in settings.smtp_to_emails.split(","):
            e = e.strip()
            if e and "@" in e:
                recipients.add(e)

    # If all recipients are mock company addresses, make sure we deliver to the SMTP user or admin
    has_real_domain = any(not any(mock_d in r.lower() for mock_d in ("@company.com", "@example.com", "user_id")) for r in recipients)
    if not has_real_domain and username and "@" in username:
        recipients.add(username.strip())

    if not recipients:
        logger.warning("email_service.no_recipients", to=to_email, subject=subject)
        return False

    success = False
    for target in recipients:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        from_addr = settings.smtp_from_email or username
        msg["From"] = f"{settings.smtp_from_name} <{from_addr}>"
        msg["To"] = target

        if body_text:
            msg.attach(MIMEText(body_text, "plain", "utf-8"))
        if body_html:
            msg.attach(MIMEText(body_html, "html", "utf-8"))

        try:
            if settings.smtp_port == 465:
                server = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=12)
            else:
                server = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=12)
                if settings.smtp_use_tls:
                    server.starttls()

            if username and settings.smtp_password:
                server.login(username, settings.smtp_password)

            server.send_message(msg)
            server.quit()
            logger.info("email_service.sent_success", to=target, subject=subject)
            success = True
        except Exception as e:
            logger.error("email_service.send_failed", error=str(e), to=target, subject=subject)

    return success


async def send_email(to_email: str, subject: str, body_html: str, body_text: str = "") -> bool:
    """Non-blocking async email dispatcher using background executor."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _send_sync_email, to_email, subject, body_html, body_text)


# ── 1. Ticket Created Confirmation ───────────────────────────────────────────
async def send_ticket_created_email(
    to_email: str,
    recipient_name: str,
    ticket_id: str,
    subject_summary: str,
    priority: str = "Medium",
    category: str = "IT"
) -> bool:
    """Dispatches Ticket Created Confirmation email."""
    subject = f"[Ticket #{ticket_id}] Received: {subject_summary}"
    body_html = f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; line-height: 1.6; color: #1e293b; max-width: 600px; margin: 0 auto; padding: 24px; border: 1px solid #e2e8f0; border-radius: 12px; background-color: #ffffff;">
        <div style="background: linear-gradient(135deg, #064e3b 0%, #047857 100%); padding: 20px; border-radius: 8px; color: #ffffff;">
            <h2 style="margin: 0; font-size: 20px; font-weight: 700;">Bobby AI — Support Request Received</h2>
            <p style="margin: 4px 0 0 0; font-size: 13px; opacity: 0.9;">Inspired Pet Nutrition IT Service Desk</p>
        </div>
        <div style="padding: 24px 0 16px 0;">
            <p style="font-size: 15px; margin-top: 0;">Hello <strong>{recipient_name or 'there'}</strong>,</p>
            <p style="font-size: 14px; color: #334155;">Your request has been logged and assigned to the IT Support Team. Here are your ticket details:</p>
            
            <div style="background-color: #f8fafc; padding: 18px; border-radius: 6px; border: 1px solid #e2e8f0; margin: 18px 0;">
                <table style="width: 100%; border-collapse: collapse; font-size: 14px;">
                    <tr>
                        <td style="padding: 4px 0; color: #64748b; width: 120px;"><strong>Ticket ID:</strong></td>
                        <td style="padding: 4px 0; color: #0f172a; font-weight: 600;">#{ticket_id}</td>
                    </tr>
                    <tr>
                        <td style="padding: 4px 0; color: #64748b;"><strong>Subject:</strong></td>
                        <td style="padding: 4px 0; color: #0f172a;">{subject_summary}</td>
                    </tr>
                    <tr>
                        <td style="padding: 4px 0; color: #64748b;"><strong>Category:</strong></td>
                        <td style="padding: 4px 0; color: #0f172a;">{category}</td>
                    </tr>
                    <tr>
                        <td style="padding: 4px 0; color: #64748b;"><strong>Priority:</strong></td>
                        <td style="padding: 4px 0; color: #0f172a;">{priority.capitalize()}</td>
                    </tr>
                    <tr>
                        <td style="padding: 4px 0; color: #64748b;"><strong>Status:</strong></td>
                        <td style="padding: 4px 0; color: #059669; font-weight: 600;">In Progress</td>
                    </tr>
                </table>
            </div>
            <p style="font-size: 13px; color: #64748b;">You can check status or ask for updates anytime by chatting with Bobby on the IT Portal.</p>
        </div>
        <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;" />
        <p style="font-size: 12px; color: #94a3b8; text-align: center; margin: 0;">Inspired Pet Nutrition &copy; 2026 Bobby IT Service Desk. All rights reserved.</p>
    </div>
    """
    return await send_email(to_email, subject, body_html)


# ── 2. P1 Escalation Alert ───────────────────────────────────────────────────
async def send_escalation_email(
    to_email: str,
    recipient_name: str,
    ticket_id: str,
    subject_summary: str
) -> bool:
    """Dispatches P1 Escalation Confirmation email."""
    subject = f"[P1 Escalation Alert] Ticket #{ticket_id} - {subject_summary}"
    body_html = f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; line-height: 1.6; color: #1e293b; max-width: 600px; margin: 0 auto; padding: 24px; border: 1px solid #e2e8f0; border-radius: 12px; background-color: #ffffff;">
        <div style="background: linear-gradient(135deg, #991b1b 0%, #dc2626 100%); padding: 20px; border-radius: 8px; color: #ffffff;">
            <h2 style="margin: 0; font-size: 20px; font-weight: 700;">🚨 Bobby AI — Priority 1 (P1) Escalation</h2>
            <p style="margin: 4px 0 0 0; font-size: 13px; opacity: 0.9;">Urgent Incident Dispatch</p>
        </div>
        <div style="padding: 24px 0 16px 0;">
            <p style="font-size: 15px; margin-top: 0;">Hello <strong>{recipient_name or 'there'}</strong>,</p>
            <p style="font-size: 14px; color: #334155;">Your support ticket has been escalated to <strong>Priority 1 (Urgent)</strong> and forwarded directly to our on-call IT engineers:</p>
            
            <div style="background-color: #fef2f2; padding: 18px; border-left: 4px solid #ef4444; margin: 18px 0; border-radius: 6px; border: 1px solid #fee2e2; border-left-width: 4px;">
                <table style="width: 100%; border-collapse: collapse; font-size: 14px;">
                    <tr>
                        <td style="padding: 4px 0; color: #64748b; width: 130px;"><strong>Ticket ID:</strong></td>
                        <td style="padding: 4px 0; color: #0f172a; font-weight: 600;">#{ticket_id}</td>
                    </tr>
                    <tr>
                        <td style="padding: 4px 0; color: #64748b;"><strong>Subject:</strong></td>
                        <td style="padding: 4px 0; color: #0f172a;">{subject_summary}</td>
                    </tr>
                    <tr>
                        <td style="padding: 4px 0; color: #64748b;"><strong>Assigned Team:</strong></td>
                        <td style="padding: 4px 0; color: #991b1b; font-weight: 600;">IT Helpdesk Rapid Response</td>
                    </tr>
                    <tr>
                        <td style="padding: 4px 0; color: #64748b;"><strong>Target SLA:</strong></td>
                        <td style="padding: 4px 0; color: #0f172a;">15 Minutes</td>
                    </tr>
                </table>
            </div>
            <p style="font-size: 13px; color: #64748b;">A technician is actively investigating this request and will contact you directly if further information is required.</p>
        </div>
        <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;" />
        <p style="font-size: 12px; color: #94a3b8; text-align: center; margin: 0;">Inspired Pet Nutrition &copy; 2026 Bobby IT Service Desk. All rights reserved.</p>
    </div>
    """
    return await send_email(to_email, subject, body_html)


# ── 3. Ticket Resolved Notification (With Detailed Resolution & CSAT) ────────
async def send_ticket_resolved_email(
    to_email: str,
    recipient_name: str,
    ticket_id: str,
    subject_summary: str,
    resolution_notes: str,
    resolved_by: str = "IT Service Desk Team",
) -> bool:
    """
    Dispatches a comprehensive Ticket Resolved Notification with:
    - Specific Resolution Details & Actions Taken
    - Resolving Agent Information
    - Timestamp
    - Interactive CSAT 5-Star Rating buttons
    - Re-open Instructions
    """
    now_str = datetime.now().strftime("%d %b %Y, %H:%M %Z")
    subject = f"[Resolved] Ticket #{ticket_id} - {subject_summary}"
    
    body_html = f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; line-height: 1.6; color: #1e293b; max-width: 620px; margin: 0 auto; padding: 24px; border: 1px solid #e2e8f0; border-radius: 12px; background-color: #ffffff;">
        
        <!-- Header -->
        <div style="background: linear-gradient(135deg, #065f46 0%, #059669 100%); padding: 22px; border-radius: 8px; color: #ffffff;">
            <div style="display: flex; align-items: center; justify-content: space-between;">
                <div>
                    <h2 style="margin: 0; font-size: 20px; font-weight: 700;">✅ Ticket Resolved</h2>
                    <p style="margin: 4px 0 0 0; font-size: 13px; opacity: 0.9;">Inspired Pet Nutrition IT Service Management</p>
                </div>
            </div>
        </div>

        <!-- Body -->
        <div style="padding: 24px 0 16px 0;">
            <p style="font-size: 15px; margin-top: 0;">Hello <strong>{recipient_name or 'there'}</strong>,</p>
            <p style="font-size: 14px; color: #334155;">Your support request has been completed and marked as <strong>Resolved</strong> by our IT Support Specialist.</p>
            
            <!-- Ticket Overview Box -->
            <div style="background-color: #f8fafc; padding: 16px 18px; border-radius: 6px; border: 1px solid #e2e8f0; margin-bottom: 20px;">
                <table style="width: 100%; border-collapse: collapse; font-size: 13px;">
                    <tr>
                        <td style="padding: 3px 0; color: #64748b; width: 130px;"><strong>Ticket ID:</strong></td>
                        <td style="padding: 3px 0; color: #0f172a; font-weight: 600;">#{ticket_id}</td>
                    </tr>
                    <tr>
                        <td style="padding: 3px 0; color: #64748b;"><strong>Subject:</strong></td>
                        <td style="padding: 3px 0; color: #0f172a;">{subject_summary}</td>
                    </tr>
                    <tr>
                        <td style="padding: 3px 0; color: #64748b;"><strong>Resolved By:</strong></td>
                        <td style="padding: 3px 0; color: #0f172a;">{resolved_by}</td>
                    </tr>
                    <tr>
                        <td style="padding: 3px 0; color: #64748b;"><strong>Resolution Time:</strong></td>
                        <td style="padding: 3px 0; color: #0f172a;">{now_str}</td>
                    </tr>
                </table>
            </div>

            <!-- Resolution Details Box -->
            <div style="background-color: #f0fdf4; border-left: 4px solid #22c55e; padding: 16px 18px; border-radius: 6px; margin-bottom: 24px;">
                <h4 style="margin: 0 0 8px 0; font-size: 14px; color: #166534;">📋 Resolution Summary:</h4>
                <div style="font-size: 13px; color: #15803d; white-space: pre-line; line-height: 1.5;">
                    {resolution_notes}
                </div>
            </div>

            <!-- CSAT Survey -->
            <div style="background-color: #fdfaf6; border: 1px solid #fed7aa; padding: 18px; border-radius: 8px; text-align: center; margin-bottom: 20px;">
                <p style="margin: 0 0 10px 0; font-size: 14px; font-weight: 600; color: #9a3412;">How was your support experience with Bobby?</p>
                <div style="display: inline-flex; gap: 8px; justify-content: center;">
                    <a href="http://localhost:5173/feedback?ticket={ticket_id}&rating=5" style="display: inline-block; padding: 8px 14px; background: #ea580c; color: #ffffff; text-decoration: none; border-radius: 6px; font-size: 13px; font-weight: 600;">⭐⭐⭐⭐⭐ Great</a>
                    <a href="http://localhost:5173/feedback?ticket={ticket_id}&rating=3" style="display: inline-block; padding: 8px 14px; background: #ffffff; border: 1px solid #fdba74; color: #9a3412; text-decoration: none; border-radius: 6px; font-size: 13px;">⭐⭐⭐ OK</a>
                    <a href="http://localhost:5173/feedback?ticket={ticket_id}&rating=1" style="display: inline-block; padding: 8px 14px; background: #ffffff; border: 1px solid #fdba74; color: #9a3412; text-decoration: none; border-radius: 6px; font-size: 13px;">⭐ Poor</a>
                </div>
            </div>

            <p style="font-size: 12.5px; color: #64748b; margin: 0;">If this issue is not resolved to your satisfaction, simply reply to this email or chat with Bobby to reopen your ticket.</p>
        </div>

        <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;" />
        <p style="font-size: 12px; color: #94a3b8; text-align: center; margin: 0;">Inspired Pet Nutrition &copy; 2026 Bobby IT Service Desk. All rights reserved.</p>
    </div>
    """
    return await send_email(to_email, subject, body_html)
