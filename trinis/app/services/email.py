# PATH: /home/lumoura/trinis_ai/trinis/app/services/email.py
"""
Email service using Resend.
Handles password reset and other transactional emails.
"""
import resend
from app.core.config import get_settings


def _get_client():
    settings = get_settings()
    resend.api_key = settings.resend_api_key
    return resend


def send_password_reset_email(
    to_email: str,
    reset_url: str,
    user_name: str | None = None,
) -> bool:
    """Send a password reset email. Returns True if sent successfully."""
    settings = get_settings()
    client = _get_client()

    name = user_name or "there"

    try:
        client.Emails.send({
            "from": f"ProductSync <noreply@{settings.resend_from_domain}>",
            "to": [to_email],
            "subject": "Reset your ProductSync password",
            "html": f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f9fafb; margin: 0; padding: 40px 20px;">
  <div style="max-width: 480px; margin: 0 auto; background: white; border-radius: 12px; padding: 40px; border: 1px solid #e5e7eb;">

    <div style="margin-bottom: 32px;">
      <span style="font-size: 20px; font-weight: 600; color: #111827;">ProductSync</span>
    </div>

    <h1 style="font-size: 18px; font-weight: 600; color: #111827; margin: 0 0 8px;">Reset your password</h1>
    <p style="font-size: 14px; color: #6b7280; margin: 0 0 24px;">
      Hi {name}, we received a request to reset your password. Click the button below to choose a new one.
    </p>

    <a href="{reset_url}"
       style="display: inline-block; background: #4f46e5; color: white; text-decoration: none;
              padding: 12px 24px; border-radius: 8px; font-size: 14px; font-weight: 500;">
      Reset password →
    </a>

    <p style="font-size: 12px; color: #9ca3af; margin: 24px 0 0;">
      This link expires in 1 hour. If you didn't request a password reset, you can safely ignore this email.
    </p>

    <hr style="border: none; border-top: 1px solid #f3f4f6; margin: 24px 0;">
    <p style="font-size: 11px; color: #d1d5db; margin: 0;">
      ProductSync · If the button doesn't work, copy this link: {reset_url}
    </p>
  </div>
</body>
</html>
            """,
        })
        return True
    except Exception as e:
        print(f"⚠️ Failed to send password reset email to {to_email}: {e}")
        return False


def send_welcome_email(to_email: str, user_name: str | None = None) -> bool:
    """Send a welcome email after registration."""
    settings = get_settings()
    client = _get_client()
    name = user_name or "there"

    try:
        client.Emails.send({
            "from": f"ProductSync <noreply@{settings.resend_from_domain}>",
            "to": [to_email],
            "subject": "Welcome to ProductSync 🎉",
            "html": f"""
<!DOCTYPE html>
<html>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f9fafb; margin: 0; padding: 40px 20px;">
  <div style="max-width: 480px; margin: 0 auto; background: white; border-radius: 12px; padding: 40px; border: 1px solid #e5e7eb;">
    <div style="margin-bottom: 32px;">
      <span style="font-size: 20px; font-weight: 600; color: #111827;">ProductSync</span>
    </div>
    <h1 style="font-size: 18px; font-weight: 600; color: #111827; margin: 0 0 8px;">Welcome, {name}! 👋</h1>
    <p style="font-size: 14px; color: #6b7280; margin: 0 0 24px;">
      Your account is ready. Connect your first Shopify store and run your first sync.
    </p>
    <a href="{settings.app_base_url}/stores"
       style="display: inline-block; background: #4f46e5; color: white; text-decoration: none;
              padding: 12px 24px; border-radius: 8px; font-size: 14px; font-weight: 500;">
      Get started →
    </a>
  </div>
</body>
</html>
            """,
        })
        return True
    except Exception as e:
        print(f"⚠️ Failed to send welcome email to {to_email}: {e}")
        return False


def send_confirmation_email(
    to_email: str,
    confirm_url: str,
    user_name: str | None = None,
) -> bool:
    """Send email confirmation link after registration."""
    settings = get_settings()
    client = _get_client()
    name = user_name or "there"

    try:
        client.Emails.send({
            "from": f"ProductSync <noreply@{settings.resend_from_domain}>",
            "to": [to_email],
            "subject": "Confirm your ProductSync email",
            "html": f"""
<!DOCTYPE html>
<html>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f9fafb; margin: 0; padding: 40px 20px;">
  <div style="max-width: 480px; margin: 0 auto; background: white; border-radius: 12px; padding: 40px; border: 1px solid #e5e7eb;">
    <div style="margin-bottom: 32px;">
      <span style="font-size: 20px; font-weight: 600; color: #111827;">ProductSync</span>
    </div>
    <h1 style="font-size: 18px; font-weight: 600; color: #111827; margin: 0 0 8px;">Confirm your email</h1>
    <p style="font-size: 14px; color: #6b7280; margin: 0 0 24px;">
      Hi {name}, thanks for signing up! Click the button below to confirm your email address and activate your account.
    </p>
    <a href="{confirm_url}"
       style="display: inline-block; background: #4f46e5; color: white; text-decoration: none;
              padding: 12px 24px; border-radius: 8px; font-size: 14px; font-weight: 500;">
      Confirm email →
    </a>
    <p style="font-size: 12px; color: #9ca3af; margin: 24px 0 0;">
      This link expires in 24 hours. If you didn't create an account, you can safely ignore this email.
    </p>
    <hr style="border: none; border-top: 1px solid #f3f4f6; margin: 24px 0;">
    <p style="font-size: 11px; color: #d1d5db; margin: 0;">
      ProductSync · If the button doesn't work, copy this link: {confirm_url}
    </p>
  </div>
</body>
</html>
            """,
        })
        return True
    except Exception as e:
        print(f"⚠️ Failed to send confirmation email to {to_email}: {e}")
        return False


def send_invite_email(
    to_email: str,
    invite_url: str,
    invited_by_name: str,
    workspace_name: str,
    user_name: str | None = None,
) -> bool:
    """Send a team invite email."""
    settings = get_settings()
    client = _get_client()

    try:
        client.Emails.send({
            "from": f"ProductSync <noreply@{settings.resend_from_domain}>",
            "to": [to_email],
            "subject": f"You've been invited to join {workspace_name} on ProductSync",
            "html": f"""
<!DOCTYPE html>
<html>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f9fafb; margin: 0; padding: 40px 20px;">
  <div style="max-width: 480px; margin: 0 auto; background: white; border-radius: 12px; padding: 40px; border: 1px solid #e5e7eb;">
    <div style="margin-bottom: 32px;">
      <span style="font-size: 20px; font-weight: 600; color: #111827;">ProductSync</span>
    </div>
    <h1 style="font-size: 18px; font-weight: 600; color: #111827; margin: 0 0 8px;">You&apos;ve been invited!</h1>
    <p style="font-size: 14px; color: #6b7280; margin: 0 0 24px;">
      <strong>{invited_by_name}</strong> has invited you to join <strong>{workspace_name}</strong> on ProductSync.
      Click the button below to accept the invitation and create your account.
    </p>
    <a href="{invite_url}"
       style="display: inline-block; background: #4f46e5; color: white; text-decoration: none;
              padding: 12px 24px; border-radius: 8px; font-size: 14px; font-weight: 500;">
      Accept invitation →
    </a>
    <p style="font-size: 12px; color: #9ca3af; margin: 24px 0 0;">
      This invitation expires in 72 hours. If you weren't expecting this, you can safely ignore it.
    </p>
    <hr style="border: none; border-top: 1px solid #f3f4f6; margin: 24px 0;">
    <p style="font-size: 11px; color: #d1d5db; margin: 0;">
      ProductSync · If the button doesn't work, copy this link: {invite_url}
    </p>
  </div>
</body>
</html>
            """,
        })
        return True
    except Exception as e:
        print(f"⚠️ Failed to send invite email to {to_email}: {e}")
        return False
