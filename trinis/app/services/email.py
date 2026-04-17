# PATH: /home/lumoura/trinis_ai/trinis/app/services/email.py
"""
Email service using Resend.
All transactional emails support EN, PT and ES.
"""
import resend
from app.core.config import get_settings


def _get_client():
    settings = get_settings()
    resend.api_key = settings.resend_api_key
    return resend


# ── Translations ──────────────────────────────────────────────────────────────

_T = {
    "confirmation": {
        "en": {
            "subject": "Confirm your ProductSync email",
            "title": "Confirm your email",
            "body": "Thanks for signing up! Click the button below to confirm your email address and activate your account.",
            "cta": "Confirm email →",
            "expire": "This link expires in 24 hours. If you didn't create an account, you can safely ignore this email.",
        },
        "pt": {
            "subject": "Confirme seu e-mail no ProductSync",
            "title": "Confirme seu e-mail",
            "body": "Obrigado por se cadastrar! Clique no botão abaixo para confirmar seu endereço de e-mail e ativar sua conta.",
            "cta": "Confirmar e-mail →",
            "expire": "Este link expira em 24 horas. Se você não criou uma conta, pode ignorar este e-mail.",
        },
        "es": {
            "subject": "Confirma tu correo en ProductSync",
            "title": "Confirma tu correo",
            "body": "¡Gracias por registrarte! Haz clic en el botón de abajo para confirmar tu dirección de correo y activar tu cuenta.",
            "cta": "Confirmar correo →",
            "expire": "Este enlace expira en 24 horas. Si no creaste una cuenta, puedes ignorar este correo.",
        },
    },
    "reset_password": {
        "en": {
            "subject": "Reset your ProductSync password",
            "title": "Reset your password",
            "body": "We received a request to reset your password. Click the button below to choose a new one.",
            "cta": "Reset password →",
            "expire": "This link expires in 1 hour. If you didn't request a password reset, you can safely ignore this email.",
        },
        "pt": {
            "subject": "Redefina sua senha no ProductSync",
            "title": "Redefinir senha",
            "body": "Recebemos uma solicitação para redefinir sua senha. Clique no botão abaixo para escolher uma nova.",
            "cta": "Redefinir senha →",
            "expire": "Este link expira em 1 hora. Se você não solicitou a redefinição, pode ignorar este e-mail.",
        },
        "es": {
            "subject": "Restablece tu contraseña en ProductSync",
            "title": "Restablecer contraseña",
            "body": "Recibimos una solicitud para restablecer tu contraseña. Haz clic en el botón de abajo para elegir una nueva.",
            "cta": "Restablecer contraseña →",
            "expire": "Este enlace expira en 1 hora. Si no solicitaste el restablecimiento, puedes ignorar este correo.",
        },
    },
    "welcome": {
        "en": {
            "subject": "Welcome to ProductSync 🎉",
            "title": "Welcome!",
            "body": "Your account is ready. Connect your first Shopify store and run your first sync.",
            "cta": "Get started →",
        },
        "pt": {
            "subject": "Bem-vindo ao ProductSync 🎉",
            "title": "Bem-vindo!",
            "body": "Sua conta está pronta. Conecte sua primeira loja Shopify e execute sua primeira sincronização.",
            "cta": "Começar →",
        },
        "es": {
            "subject": "Bienvenido a ProductSync 🎉",
            "title": "¡Bienvenido!",
            "body": "Tu cuenta está lista. Conecta tu primera tienda Shopify y ejecuta tu primera sincronización.",
            "cta": "Empezar →",
        },
    },
    "invite": {
        "en": {
            "subject": "You've been invited to join {workspace} on ProductSync",
            "title": "You've been invited!",
            "body": "<strong>{invited_by}</strong> has invited you to join <strong>{workspace}</strong> on ProductSync. Click the button below to accept the invitation and create your account.",
            "cta": "Accept invitation →",
            "expire": "This invitation expires in 72 hours. If you weren't expecting this, you can safely ignore it.",
        },
        "pt": {
            "subject": "Você foi convidado para {workspace} no ProductSync",
            "title": "Você foi convidado!",
            "body": "<strong>{invited_by}</strong> convidou você para se juntar ao <strong>{workspace}</strong> no ProductSync. Clique no botão abaixo para aceitar o convite e criar sua conta.",
            "cta": "Aceitar convite →",
            "expire": "Este convite expira em 72 horas. Se você não esperava este e-mail, pode ignorá-lo.",
        },
        "es": {
            "subject": "Te han invitado a unirte a {workspace} en ProductSync",
            "title": "¡Te han invitado!",
            "body": "<strong>{invited_by}</strong> te ha invitado a unirte a <strong>{workspace}</strong> en ProductSync. Haz clic en el botón de abajo para aceptar la invitación y crear tu cuenta.",
            "cta": "Aceptar invitación →",
            "expire": "Esta invitación expira en 72 horas. Si no esperabas este correo, puedes ignorarlo.",
        },
    },
}


def _get_t(template: str, locale: str) -> dict:
    """Get translations for a template, falling back to EN."""
    return _T[template].get(locale) or _T[template]["en"]


# ── Email template ────────────────────────────────────────────────────────────

def _html(title: str, body: str, cta_url: str, cta_label: str, footer: str = "") -> str:
    return f"""<!DOCTYPE html>
<html>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f9fafb;margin:0;padding:40px 20px;">
  <div style="max-width:480px;margin:0 auto;background:white;border-radius:12px;padding:40px;border:1px solid #e5e7eb;">
    <div style="margin-bottom:32px;">
      <span style="font-size:20px;font-weight:600;color:#111827;">ProductSync</span>
    </div>
    <h1 style="font-size:18px;font-weight:600;color:#111827;margin:0 0 8px;">{title}</h1>
    <p style="font-size:14px;color:#6b7280;margin:0 0 24px;">{body}</p>
    <a href="{cta_url}" style="display:inline-block;background:#4f46e5;color:white;text-decoration:none;padding:12px 24px;border-radius:8px;font-size:14px;font-weight:500;">{cta_label}</a>
    {f'<p style="font-size:12px;color:#9ca3af;margin:24px 0 0;">{footer}</p>' if footer else ''}
    <hr style="border:none;border-top:1px solid #f3f4f6;margin:24px 0;">
    <p style="font-size:11px;color:#d1d5db;margin:0;">ProductSync · If the button doesn't work, copy this link: {cta_url}</p>
  </div>
</body>
</html>"""


def _send(to_email: str, subject: str, html: str, from_domain: str) -> bool:
    try:
        _get_client().Emails.send({
            "from": f"ProductSync <noreply@{from_domain}>",
            "to": [to_email],
            "subject": subject,
            "html": html,
        })
        return True
    except Exception as e:
        print(f"⚠️ Failed to send email to {to_email}: {e}")
        return False


# ── Public API ────────────────────────────────────────────────────────────────

def send_confirmation_email(
    to_email: str,
    confirm_url: str,
    user_name: str | None = None,
    locale: str = "en",
) -> bool:
    settings = get_settings()
    t = _get_t("confirmation", locale)
    return _send(
        to_email,
        t["subject"],
        _html(t["title"], t["body"], confirm_url, t["cta"], t["expire"]),
        settings.resend_from_domain,
    )


def send_password_reset_email(
    to_email: str,
    reset_url: str,
    user_name: str | None = None,
    locale: str = "en",
) -> bool:
    settings = get_settings()
    t = _get_t("reset_password", locale)
    return _send(
        to_email,
        t["subject"],
        _html(t["title"], t["body"], reset_url, t["cta"], t["expire"]),
        settings.resend_from_domain,
    )


def send_welcome_email(
    to_email: str,
    user_name: str | None = None,
    locale: str = "en",
) -> bool:
    settings = get_settings()
    t = _get_t("welcome", locale)
    return _send(
        to_email,
        t["subject"],
        _html(t["title"], t["body"], f"{settings.app_base_url}/stores", t["cta"]),
        settings.resend_from_domain,
    )


def send_invite_email(
    to_email: str,
    invite_url: str,
    invited_by_name: str,
    workspace_name: str,
    user_name: str | None = None,
    locale: str = "en",
) -> bool:
    settings = get_settings()
    t = _get_t("invite", locale)
    body = t["body"].replace("{invited_by}", invited_by_name).replace("{workspace}", workspace_name)
    subject = t["subject"].replace("{workspace}", workspace_name)
    return _send(
        to_email,
        subject,
        _html(t["title"], body, invite_url, t["cta"], t["expire"]),
        settings.resend_from_domain,
    )
