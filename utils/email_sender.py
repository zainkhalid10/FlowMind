"""Email sending utility for FlowMind invitations."""

import os
import smtplib
import threading
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path


def _append_email_log(line: str):
    """Append invite email diagnostics to a local log file."""
    try:
        log_path = Path(__file__).resolve().parents[1] / "invite_email.log"
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"{datetime.utcnow().isoformat()}Z | {line}\n")
    except Exception:
        pass


def _load_mail_config():
    """Load email config from project .env."""
    from dotenv import load_dotenv

    env_path = Path(__file__).resolve().parents[1] / ".env"
    load_dotenv(dotenv_path=env_path)

    return {
        "email": os.getenv("MAIL_EMAIL", "").strip(),
        "password": os.getenv("MAIL_PASSWORD", "").strip(),
        "from_name": os.getenv("MAIL_FROM_NAME", "FlowMind").strip() or "FlowMind",
    }


def send_invite_email(
    to_email: str,
    to_name: str,
    manager_name: str,
    filename: str,
    deadline: str,
    temp_password: str,
    login_link: str,
):
    """Send client invitation email via Gmail SMTP."""
    try:
        config = _load_mail_config()
        print(f"[invite-email] Config loaded: email={config['email']}, has_password={bool(config['password'])}")
        _append_email_log(f"Config loaded: email={config['email']}, has_password={bool(config['password'])}")
        
        if not config["email"] or not config["password"]:
            msg = f"Missing MAIL_EMAIL or MAIL_PASSWORD. Skipping send to {to_email}"
            print(f"[invite-email] {msg}")
            _append_email_log(msg)
            return

        deadline_display = deadline or "Not specified"
        if deadline and "T" in deadline:
            try:
                dt = datetime.fromisoformat(deadline)
                deadline_display = dt.strftime("%d %B %Y")
            except Exception:
                pass

        plain_text = f"""Hi {to_name},

{manager_name} has shared a document with you for requirement review on FlowMind.

Document: {filename}
Review deadline: {deadline_display}

Your login credentials:
Email: {to_email}
Password: {temp_password}

Login here: http://localhost:5500/login.html

Once logged in you will see the requirements and can approve, reject, or request changes directly on the platform.

This password is temporary. You can change it after logging in.

- FlowMind"""

        html_version = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset=\"UTF-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />
  <style>
    body {{ margin:0; padding:24px; background:#f3f4f6; font-family: Arial, sans-serif; color:#1a1a1a; }}
    .wrap {{ max-width:640px; margin:0 auto; }}
    .card {{ background:#fff; border-radius:12px; border:1px solid #e5e7eb; overflow:hidden; }}
    .header {{ padding:22px 24px 8px; text-align:center; }}
    .logo {{ font-size:28px; font-weight:700; letter-spacing:0.2px; }}
    .logo-flow {{ color:#111; }}
    .logo-mind {{ color:#534AB7; }}
    .content {{ padding:8px 24px 24px; line-height:1.6; font-size:14px; }}
    .meta {{ background:#f9fafb; border:1px solid #e5e7eb; border-radius:10px; padding:12px 14px; margin:14px 0; }}
    .codebox {{ background:#f3f4f6; border:1px solid #d1d5db; border-radius:8px; padding:12px; font-family: Consolas, monospace; font-size:13px; }}
    .button-wrap {{ text-align:center; margin:18px 0 10px; }}
    .btn {{ display:inline-block; background:#534AB7; color:#fff !important; text-decoration:none; padding:11px 18px; border-radius:8px; font-weight:600; }}
    .footer {{ padding:14px 24px 20px; color:#6b7280; font-size:12px; text-align:center; border-top:1px solid #f3f4f6; }}
  </style>
</head>
<body>
  <div class=\"wrap\">
    <div class=\"card\">
      <div class=\"header\">
        <div class=\"logo\"><span class=\"logo-flow\">Flow</span><span class=\"logo-mind\">Mind</span></div>
      </div>
      <div class=\"content\">
        <p>Hi {to_name},</p>
        <p>{manager_name} has shared a document with you for requirement review on FlowMind.</p>

        <div class=\"meta\">
          <div><strong>Document:</strong> {filename}</div>
          <div><strong>Review deadline:</strong> {deadline_display}</div>
        </div>

        <p><strong>Your login credentials:</strong></p>
        <div class=\"codebox\">
          <div>Email: {to_email}</div>
          <div>Password: {temp_password}</div>
        </div>

        <div class=\"button-wrap\">
          <a class=\"btn\" href=\"{login_link}\">Login to FlowMind</a>
        </div>

        <p>Once logged in you will see the requirements and can approve, reject, or request changes directly on the platform.</p>
        <p>This password is temporary. You can change it after logging in.</p>
      </div>
      <div class=\"footer\">This is an automated message from FlowMind.</div>
    </div>
  </div>
</body>
</html>"""

        msg = MIMEMultipart("alternative")
        msg["Subject"] = "You've been invited to review requirements — FlowMind"
        msg["From"] = f"{config['from_name']} <{config['email']}>"
        msg["To"] = to_email
        msg.attach(MIMEText(plain_text, "plain", "utf-8"))
        msg.attach(MIMEText(html_version, "html", "utf-8"))

        _append_email_log(f"Attempting send to={to_email} from={config['email']}")
        print(f"[invite-email] Connecting to smtp.gmail.com:587...")
        _append_email_log(f"Connecting to smtp.gmail.com:587")
        
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=20) as server:
            print(f"[invite-email] Connection established, starting TLS...")
            _append_email_log("Connection established, starting TLS")
            
            server.ehlo()
            server.starttls()
            server.ehlo()
            
            print(f"[invite-email] Logging in as {config['email']}...")
            _append_email_log(f"Logging in as {config['email']}")
            server.login(config["email"], config["password"])
            
            print(f"[invite-email] Sending message...")
            _append_email_log("Sending message")
            server.send_message(msg)

        print(f"[invite-email] Sent to {to_email}")
        _append_email_log(f"Sent successfully to={to_email}")
    except Exception as e:
        # Never break invite flow because of email failure.
        print(f"[invite-email] Failed for {to_email}: {e}")
        _append_email_log(f"FAILED to={to_email} err={e}")


def send_confirmation_email_to_manager(
    manager_email: str,
    manager_name: str,
    client_email: str,
    client_name: str,
    filename: str,
    deadline: str,
    temp_password: str,
):
    """Send confirmation email to manager with client credentials for their records."""
    try:
        config = _load_mail_config()
        if not config["email"] or not config["password"]:
            msg = f"Missing MAIL_EMAIL or MAIL_PASSWORD. Skipping manager confirmation for {manager_email}"
            print(f"[manager-confirm] {msg}")
            _append_email_log(msg)
            return

        deadline_display = deadline or "Not specified"
        if deadline and "T" in deadline:
            try:
                dt = datetime.fromisoformat(deadline)
                deadline_display = dt.strftime("%d %B %Y")
            except Exception:
                pass

        plain_text = f"""Hi {manager_name},

This is your confirmation that a client account has been created for {client_name} ({client_email}).

Document: {filename}
Review deadline: {deadline_display}

Client credentials (for your records):
Email: {client_email}
Temporary password: {temp_password}

The client has been sent an invitation email with their login credentials and can now access the document on FlowMind.

To view all your clients and their credentials, visit: http://localhost:5500/clients.html

- FlowMind"""

        html_version = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset=\"UTF-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />
  <style>
    body {{ margin:0; padding:24px; background:#f3f4f6; font-family: Arial, sans-serif; color:#1a1a1a; }}
    .wrap {{ max-width:640px; margin:0 auto; }}
    .card {{ background:#fff; border-radius:12px; border:1px solid #e5e7eb; overflow:hidden; }}
    .header {{ padding:22px 24px 8px; text-align:center; }}
    .logo {{ font-size:28px; font-weight:700; letter-spacing:0.2px; }}
    .logo-flow {{ color:#111; }}
    .logo-mind {{ color:#534AB7; }}
    .content {{ padding:8px 24px 24px; line-height:1.6; font-size:14px; }}
    .meta {{ background:#f9fafb; border:1px solid #e5e7eb; border-radius:10px; padding:12px 14px; margin:14px 0; }}
    .codebox {{ background:#f3f4f6; border:1px solid #d1d5db; border-radius:8px; padding:12px; font-family: Consolas, monospace; font-size:13px; }}
    .button-wrap {{ text-align:center; margin:18px 0 10px; }}
    .btn {{ display:inline-block; background:#534AB7; color:#fff !important; text-decoration:none; padding:11px 18px; border-radius:8px; font-weight:600; }}
    .footer {{ padding:14px 24px 20px; color:#6b7280; font-size:12px; text-align:center; border-top:1px solid #f3f4f6; }}
  </style>
</head>
<body>
  <div class=\"wrap\">
    <div class=\"card\">
      <div class=\"header\">
        <div class=\"logo\"><span class=\"logo-flow\">Flow</span><span class=\"logo-mind\">Mind</span></div>
      </div>
      <div class=\"content\">
        <p>Hi {manager_name},</p>
        <p>This is your confirmation that a client account has been created for <strong>{client_name}</strong> ({client_email}).</p>

        <div class=\"meta\">
          <div><strong>Document:</strong> {filename}</div>
          <div><strong>Review deadline:</strong> {deadline_display}</div>
        </div>

        <p><strong>Client credentials (for your records):</strong></p>
        <div class=\"codebox\">
          <div>Email: {client_email}</div>
          <div>Temporary password: {temp_password}</div>
        </div>

        <p>The client has been sent an invitation email with their login credentials and can now access the document on FlowMind.</p>

        <div class=\"button-wrap\">
          <a class=\"btn\" href=\"http://localhost:5500/clients.html\">View all clients</a>
        </div>
      </div>
      <div class=\"footer\">This is an automated message from FlowMind.</div>
    </div>
  </div>
</body>
</html>"""

        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"Client account created: {client_name} — FlowMind"
        msg["From"] = f"{config['from_name']} <{config['email']}>"
        msg["To"] = manager_email
        msg.attach(MIMEText(plain_text, "plain", "utf-8"))
        msg.attach(MIMEText(html_version, "html", "utf-8"))

        _append_email_log(f"Manager confirm: Attempting send to={manager_email} for client={client_email}")
        print(f"[manager-confirm] Connecting to smtp.gmail.com:587...")
        _append_email_log(f"Manager confirm: Connecting to smtp.gmail.com:587")
        
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=20) as server:
            print(f"[manager-confirm] Connection established, starting TLS...")
            _append_email_log("Manager confirm: Connection established, starting TLS")
            
            server.ehlo()
            server.starttls()
            server.ehlo()
            
            print(f"[manager-confirm] Logging in...")
            _append_email_log(f"Manager confirm: Logging in as {config['email']}")
            server.login(config["email"], config["password"])
            
            print(f"[manager-confirm] Sending message...")
            _append_email_log("Manager confirm: Sending message")
            server.send_message(msg)

        print(f"[manager-confirm] Sent to {manager_email}")
        _append_email_log(f"Manager confirm: Sent successfully to={manager_email}")
    except Exception as e:
        print(f"[manager-confirm] Failed for {manager_email}: {e}")
        _append_email_log(f"Manager confirm: FAILED to={manager_email} err={e}")


def send_invite_email_async(
    to_email: str,
    to_name: str,
    manager_name: str,
    filename: str,
    deadline: str,
    temp_password: str,
    login_link: str,
):
    """Send invitation email in a daemon background thread."""
    thread = threading.Thread(
        target=send_invite_email,
        args=(to_email, to_name, manager_name, filename, deadline, temp_password, login_link),
        daemon=True,
    )
    thread.start()


def send_confirmation_email_to_manager_async(
    manager_email: str,
    manager_name: str,
    client_email: str,
    client_name: str,
    filename: str,
    deadline: str,
    temp_password: str,
):
    """Send confirmation email to manager in a daemon background thread."""
    thread = threading.Thread(
        target=send_confirmation_email_to_manager,
        args=(manager_email, manager_name, client_email, client_name, filename, deadline, temp_password),
        daemon=True,
    )
    thread.start()
