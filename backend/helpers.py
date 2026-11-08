import hashlib
import hmac
import re
import secrets
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from functools import wraps

import bcrypt
from flask import abort, flash, g, jsonify, redirect, request, session, url_for
from werkzeug.security import check_password_hash

from .models import User, db


def is_ajax():
    return request.headers.get("X-Requested-With", "").lower() == "xmlhttprequest"


def action_response(message, endpoint, success=True, status=200, kind="success"):
    if is_ajax():
        return (
            jsonify(success=success, message=message, type=kind, refresh=success),
            status,
        )
    flash(message, kind)
    return redirect(url_for(endpoint))


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user_id = session.get("user_id")
        g.user = db.session.get(User, user_id) if user_id else None
        if not g.user:
            if is_ajax():
                abort(401, "Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.")
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)

    return wrapped


def verify_password(stored, password):
    if stored.startswith("$sha1$"):
        return hmac.compare_digest(
            stored[6:], hashlib.sha1(password.encode()).hexdigest()
        )
    if stored.startswith(("$2y$", "$2a$", "$2b$")):
        try:
            normalized = stored.replace("$2y$", "$2b$", 1)
            return bcrypt.checkpw(password.encode()[:72], normalized.encode())
        except ValueError:
            return False
    try:
        return check_password_hash(stored, password)
    except (ValueError, TypeError):
        return False


def text_field(name, limit, required=True):
    value = request.form.get(name, "").strip()
    if (required and not value) or len(value) > limit:
        raise ValueError(f"Trường {name} cần đầy đủ thông tin và tối đa {limit} ký tự.")
    return value


def amount(name, positive=False, maximum=999999999999, optional=False):
    raw = request.form.get(name, "").strip()
    if optional and raw == "":
        return None
    try:
        value = Decimal(raw)
        if (
            not value.is_finite()
            or value < 0
            or value > Decimal(str(maximum))
            or (positive and value == 0)
        ):
            raise ValueError
        if name == "area":
            if value != value.quantize(Decimal("0.01")):
                raise ValueError
        elif value != value.to_integral_value():
            raise ValueError
        return value
    except (InvalidOperation, ValueError):
        raise ValueError(
            f"Trường {name} phải là số hợp lệ, không âm và trong giới hạn."
        ) from None


def record_id(name):
    return int(amount(name, positive=True, maximum=2147483647))


def date_field(name, required=True):
    raw = request.form.get(name, "").strip()
    if not raw and not required:
        return None
    try:
        value = date.fromisoformat(raw)
        if value.year < 1000:
            raise ValueError
        return value
    except ValueError:
        raise ValueError(f"Trường {name} phải là ngày hợp lệ.") from None


def billing_month():
    raw = request.form.get("billing_month", "")
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", raw):
        raise ValueError("Kỳ hóa đơn không hợp lệ.")
    try:
        value = date.fromisoformat(raw + "-01")
        if value.year < 1000:
            raise ValueError
        return value
    except ValueError:
        raise ValueError("Kỳ hóa đơn không hợp lệ.") from None


def generated_code(prefix):
    return (
        prefix + datetime.now().strftime("%y%m%d%H%M%S") + secrets.token_hex(3).upper()
    )
