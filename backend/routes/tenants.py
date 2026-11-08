from flask import Blueprint, render_template, request
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


@tenants.route("/tenants", methods=["GET", "POST"])
@login_required
def index():
    if request.method == "POST":
        action = request.form.get("action")
        if action == "create":
            tenant = Tenant(
                tenant_code=generated_code("KH"),
                full_name=text_field("full_name", 150),
                phone=text_field("phone", 20),
                identity_number=text_field("identity_number", 30, required=False)
                or None,
                date_of_birth=date_field("date_of_birth", required=False),
                move_in_date=date_field("move_in_date", required=False),
                address=text_field("address", 255, required=False),
            )
            db.session.add(tenant)
            db.session.commit()
            return action_response("Đã thêm khách thuê.", "tenants.index")
        if action == "delete":
            tenant = db.get_or_404(Tenant, record_id("id"))
            if tenant.contracts:
                raise ValueError("Khách đã có hợp đồng nên không thể xóa.")
            db.session.delete(tenant)
            db.session.commit()
            return action_response("Đã xóa khách thuê.", "tenants.index")
        raise ValueError("Thao tác không hợp lệ.")
    records = db.session.scalars(select(Tenant).order_by(Tenant.id.desc())).all()
    return render_template(
        "tenants.html", tenants=records, page_title="Khách thuê", active_page="tenants"
    )
