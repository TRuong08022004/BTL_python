from flask import Blueprint, abort, render_template, request
from sqlalchemy import select

from ..helpers import (
    action_response,
    date_field,
    generated_code,
    login_required,
    record_id,
    text_field,
)
from ..models import Tenant, db

tenants = Blueprint("tenants", __name__)


def tenant_form_data():
    return dict(
        full_name=text_field("full_name", 150),
        phone=text_field("phone", 20),
        identity_number=text_field("identity_number", 30, required=False) or None,
        date_of_birth=date_field("date_of_birth", required=False),
        move_in_date=date_field("move_in_date", required=False),
        address=text_field("address", 255, required=False),
    )


@tenants.route("/tenants", methods=["GET", "POST"])
@login_required
def index():
    if request.method == "POST":
        action = request.form.get("action")
        if action in ("create", "update"):
            values = tenant_form_data()
            if action == "create":
                tenant = Tenant(tenant_code=generated_code("KH"), **values)
                db.session.add(tenant)
            else:
                tenant = db.session.scalar(
                    select(Tenant)
                    .where(Tenant.id == record_id("id"), Tenant.status == "active")
                    .with_for_update()
                )
                if tenant is None:
                    abort(404, "Không tìm thấy khách thuê.")
                for name, value in values.items():
                    setattr(tenant, name, value)
            db.session.commit()
            return action_response(
                (
                    "Đã thêm khách thuê."
                    if action == "create"
                    else "Đã cập nhật khách thuê."
                ),
                "tenants.index",
            )
        if action == "delete":
            tenant = db.session.scalar(
                select(Tenant)
                .where(Tenant.id == record_id("id"), Tenant.status == "active")
                .with_for_update()
            )
            if tenant is None:
                abort(404, "Không tìm thấy khách thuê.")
            if tenant.active_contract:
                raise ValueError(
                    "Cần kết thúc hợp đồng và trả phòng trước khi xóa khách thuê."
                )
            if tenant.contracts:
                tenant.status = "inactive"
            else:
                db.session.delete(tenant)
            db.session.commit()
            return action_response(
                "Đã xóa khách khỏi danh sách quản lý.", "tenants.index"
            )
        raise ValueError("Thao tác không hợp lệ.")
    records = db.session.scalars(
        select(Tenant).where(Tenant.status == "active").order_by(Tenant.id.desc())
    ).all()
    return render_template(
        "tenants.html",
        tenants=records,
        page_title="Khách thuê",
        active_page="tenants",
    )
