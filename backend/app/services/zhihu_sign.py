from __future__ import annotations

import base64
import hashlib
import hmac
import time
import uuid


def build_sign_payload(
    app_key: str,
    timestamp: str,
    log_id: str,
    extra_info: str = "",
) -> str:
    return f"app_key:{app_key}|ts:{timestamp}|logid:{log_id}|extra_info:{extra_info}"


def sign_payload(payload: str, app_secret: str) -> str:
    digest = hmac.new(
        app_secret.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return base64.b64encode(digest).decode("utf-8")


def build_zhihu_headers(
    app_key: str,
    app_secret: str,
    extra_info: str = "",
) -> dict[str, str]:
    timestamp = str(int(time.time()))
    log_id = f"life_path_{uuid.uuid4().hex}"
    payload = build_sign_payload(
        app_key=app_key,
        timestamp=timestamp,
        log_id=log_id,
        extra_info=extra_info,
    )
    sign = sign_payload(payload, app_secret)

    return {
        "X-App-Key": app_key,
        "X-Timestamp": timestamp,
        "X-Log-Id": log_id,
        "X-Sign": sign,
        "X-Extra-Info": extra_info,
    }
