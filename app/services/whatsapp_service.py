from __future__ import annotations

import json
from datetime import date
from urllib.error import HTTPError
from urllib.parse import quote_plus
from urllib.request import Request, urlopen

from app.core.config import get_settings


def _normalize_phone_for_whatsapp(raw_mobile_number: str) -> str:
    digits = "".join(ch for ch in raw_mobile_number if ch.isdigit())
    if digits.startswith("0"):
        digits = digits.lstrip("0")

    if len(digits) == 10:
        return f"91{digits}"
    return digits


def build_tenant_registration_message(
    tenant_name: str,
    pg_name: str,
    owner_name: str,
    joining_date: date | None,
    android_link: str,
    ios_link: str,
) -> str:
    joining_date_label = joining_date.isoformat() if joining_date else "Not provided"
    clean_tenant_name = tenant_name.strip() if tenant_name else "Tenant"
    clean_pg_name = pg_name.strip() if pg_name else "Your PG"
    clean_owner_name = owner_name.strip() if owner_name else "PG Owner"

    return (
        f"Hello {clean_tenant_name},\n\n"
        f"You have been registered as a tenant at {clean_pg_name}.\n"
        f"PG Owner: {clean_owner_name}\n"
        f"Joining Date: {joining_date_label}\n\n"
        "You can access your details and manage your stay using our app:\n\n"
        f"Android: {android_link}\n"
        f"iOS: {ios_link}\n\n"
        "If you have any questions, please contact your PG owner.\n\n"
        "Welcome to your new home!"
    )


def send_whatsapp_message(mobile_number: str, message: str, template_params: list[str] | None = None) -> dict:
    settings = get_settings()
    if not settings.whatsapp_enabled:
        return {"status": "skipped", "reason": "whatsapp_disabled"}

    if settings.whatsapp_access_token and settings.whatsapp_access_token.strip() == "<your_meta_token>":
        return {
            "status": "failed",
            "provider": "meta_cloud_api",
            "reason": "invalid_access_token_placeholder",
        }

    if settings.whatsapp_phone_number_id and settings.whatsapp_access_token:
        try:
            phone = _normalize_phone_for_whatsapp(mobile_number)
            endpoint = f"https://graph.facebook.com/{settings.whatsapp_meta_api_version}/{settings.whatsapp_phone_number_id}/messages"
            payload = {
                "messaging_product": "whatsapp",
                "to": phone,
                "type": "template",
                "template": {
                    "name": settings.whatsapp_template_name,
                    "language": {"code": settings.whatsapp_template_language},
                },
            }

            if template_params and settings.whatsapp_template_name != "hello_world":
                payload["template"]["components"] = [
                    {
                        "type": "body",
                        "parameters": [{"type": "text", "text": value} for value in template_params],
                    }
                ]

            request = Request(
                endpoint,
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {settings.whatsapp_access_token}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            with urlopen(request, timeout=15) as response:
                status_code = getattr(response, "status", 200)
                body = response.read(4000).decode("utf-8", errors="ignore")
                if 200 <= status_code < 300:
                    return {
                        "status": "sent",
                        "provider": "meta_cloud_api",
                        "status_code": status_code,
                        "provider_response": body,
                        "template_name": settings.whatsapp_template_name,
                    }
                return {
                    "status": "failed",
                    "provider": "meta_cloud_api",
                    "status_code": status_code,
                    "provider_response": body,
                    "template_name": settings.whatsapp_template_name,
                }
        except HTTPError as http_error:
            error_body = http_error.read().decode("utf-8", errors="ignore")
            return {
                "status": "failed",
                "provider": "meta_cloud_api",
                "status_code": http_error.code,
                "provider_response": error_body,
                "template_name": settings.whatsapp_template_name,
            }
        except Exception as exc:
            return {
                "status": "failed",
                "provider": "meta_cloud_api",
                "error": str(exc),
                "template_name": settings.whatsapp_template_name,
            }

    if not settings.whatsapp_provider_url:
        return {
            "status": "failed",
            "reason": "missing_whatsapp_provider_configuration",
        }

    try:
        phone = _normalize_phone_for_whatsapp(mobile_number)
        url = (
            settings.whatsapp_provider_url
            .replace("{phone}", quote_plus(phone))
            .replace("{message}", quote_plus(message))
        )

        with urlopen(url, timeout=10) as response:
            status_code = getattr(response, "status", 200)
            body = response.read(2000).decode("utf-8", errors="ignore")
            if 200 <= status_code < 300:
                return {
                    "status": "sent",
                    "provider": "custom_url",
                    "status_code": status_code,
                    "provider_response": body,
                }
            return {
                "status": "failed",
                "provider": "custom_url",
                "status_code": status_code,
                "provider_response": body,
            }
    except Exception as exc:
        return {"status": "failed", "provider": "custom_url", "error": str(exc)}
