import os
import secrets
from datetime import date
from decimal import Decimal
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, abort, jsonify, render_template, request, session
from markupsafe import Markup
from sqlalchemy import URL
from sqlalchemy.exc import DataError, IntegrityError, OperationalError
from werkzeug.exceptions import HTTPException

from .helpers import is_ajax
from .models import ROOM_CLASSES, ROOM_STATUSES, db

ROOT = Path(__file__).resolve().parent.parent


def create_app(test_config=None):
    load_dotenv(ROOT / ".env")
    key_path = ROOT / "instance" / "secret.key"
    key_path.parent.mkdir(exist_ok=True)
    if not key_path.exists():
        try:
            with key_path.open("x", encoding="ascii") as handle:
                handle.write(secrets.token_hex(32))
        except FileExistsError:
            pass
    app = Flask(
        __name__,
        template_folder=str(ROOT / "frontend/templates"),
        static_folder=str(ROOT / "frontend/assets"),
        static_url_path="/assets",
    )
    app.config.update(
        SECRET_KEY=key_path.read_text(encoding="ascii"),
        SQLALCHEMY_DATABASE_URI=URL.create(
            "mysql+pymysql",
            username=os.getenv("DB_USER", "root"),
            password=os.getenv("DB_PASSWORD", ""),
            host=os.getenv("DB_HOST", "127.0.0.1"),
            port=int(os.getenv("DB_PORT", "3306")),
            database=os.getenv("DB_NAME", "motel_python"),
            query={"charset": "utf8mb4"},
        ),
        SQLALCHEMY_ENGINE_OPTIONS={"pool_pre_ping": True},
        SESSION_COOKIE_NAME="motel_python_session",
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        MAX_CONTENT_LENGTH=1024 * 1024,
    )
    if test_config:
        app.config.update(test_config)
    db.init_app(app)

    @app.before_request
    def protect_forms():
        session.setdefault("csrf_token", secrets.token_urlsafe(32))
        if request.method == "POST":
            token = request.form.get("csrf_token", "")
            if not token or not secrets.compare_digest(session["csrf_token"], token):
                abort(400, "Phiên làm việc không hợp lệ. Vui lòng tải lại trang.")

    @app.context_processor
    def template_helpers():
        token = session.get("csrf_token", "")
        return dict(
            today=date.today(),
            room_statuses=ROOM_STATUSES,
            room_classes=ROOM_CLASSES,
            csrf_field=lambda: Markup(
                '<input type="hidden" name="csrf_token" value="' + token + '">'
            ),
        )

    @app.template_filter("money")
    def money(value):
        return f"{Decimal(value or 0):,.0f}".replace(",", ".") + "đ"

    @app.template_filter("text")
    def display_text(value):
        return "" if value is None else value

    def failure(message, status):
        if is_ajax():
            return (
                jsonify(success=False, message=message, type="danger", refresh=False),
                status,
            )
        return (
            render_template(
                "error.html", page_title="Thông báo", active_page="", message=message
            ),
            status,
        )

    @app.errorhandler(HTTPException)
    def http_error(error):
        db.session.rollback()
        return failure(error.description, error.code)

    @app.errorhandler(ValueError)
    def validation_error(error):
        db.session.rollback()
        return failure(str(error), 422)

    @app.errorhandler(IntegrityError)
    def conflict(error):
        db.session.rollback()
        return failure(
            "Dữ liệu bị trùng hoặc đã có lịch sử sử dụng. Kiểm tra số phòng, CCCD và kỳ hóa đơn.",
            409,
        )

    @app.errorhandler(DataError)
    def data_error(error):
        db.session.rollback()
        return failure("Dữ liệu vượt giới hạn cho phép.", 422)

    @app.errorhandler(OperationalError)
    def database_error(error):
        db.session.rollback()
        return failure(
            "Chưa kết nối được MySQL. Bật MySQL trong XAMPP và kiểm tra .env.", 503
        )

    @app.errorhandler(500)
    def server_error(error):
        db.session.rollback()
        return failure("Không thể xử lý yêu cầu lúc này.", 500)

    @app.after_request
    def headers(response):
        if request.endpoint != "static":
            response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        return response

    from .routes import register_routes

    register_routes(app)
    return app
