import secrets

from flask import Blueprint, redirect, render_template, request, session, url_for
from sqlalchemy import select
from werkzeug.security import generate_password_hash

from ..helpers import login_required, verify_password
from ..models import User, db

auth = Blueprint("auth", __name__)


@auth.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("reports.dashboard"))
    error = ""
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        if len(email) > 190 or len(password) > 1024:
            raise ValueError("Thông tin đăng nhập quá dài.")
        user = db.session.scalar(select(User).where(User.email == email))
        if user and verify_password(user.password, password):
            if user.password.startswith("$"):
                user.password = generate_password_hash(password)
                db.session.commit()
            session.clear()
            session.update(
                user_id=user.id,
                user_name=user.name,
                csrf_token=secrets.token_urlsafe(32),
            )
            return redirect(url_for("reports.dashboard"))
        error = "Email hoặc mật khẩu không đúng."
    return render_template("login.html", error=error)


@auth.post("/logout")
@login_required
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
