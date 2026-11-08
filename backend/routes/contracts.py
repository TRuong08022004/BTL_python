from flask import Blueprint, render_template, request
from sqlalchemy import select

from ..helpers import (
    action_response,
    amount,
    date_field,
    generated_code,
    login_required,
    record_id,
)
from ..models import Contract, Room, Tenant, db

contracts = Blueprint("contracts", __name__)


@contracts.route("/contracts", methods=["GET", "POST"])
@login_required
def index():
    if request.method == "POST":
        tenant_id, room_id = record_id("tenant_id"), record_id("room_id")
        start, end = date_field("start_date"), date_field("end_date")
        if end <= start:
            raise ValueError("Ngày kết thúc phải sau ngày bắt đầu.")
        price = amount("monthly_price", positive=True)
        deposit = amount("deposit")
        tenant = db.session.scalar(
            select(Tenant).where(Tenant.id == tenant_id).with_for_update()
        )
        if not tenant or tenant.status != "active" or tenant.active_contract:
            raise ValueError("Khách không hoạt động hoặc đã có hợp đồng hiệu lực.")
        room = db.session.scalar(
            select(Room).where(Room.id == room_id).with_for_update()
        )
        if not room or room.status != "empty" or room.active_contract:
            raise ValueError("Phòng không còn trống. Hãy tải lại danh sách.")
        contract = Contract(
            contract_code=generated_code("HD"),
            tenant_id=tenant.id,
            room_id=room.id,
            start_date=start,
            end_date=end,
            monthly_price=price,
            deposit=deposit,
            status="active",
        )
        room.status = "rented"
        db.session.add(contract)
        db.session.commit()
        return action_response("Đã tạo hợp đồng.", "contracts.index")
    records = db.session.scalars(select(Contract).order_by(Contract.id.desc())).all()
    available_tenants = db.session.scalars(
        select(Tenant)
        .where(
            Tenant.status == "active",
            ~Tenant.contracts.any(Contract.status == "active"),
        )
        .order_by(Tenant.full_name)
    ).all()
    available_rooms = db.session.scalars(
        select(Room).where(Room.status == "empty").order_by(Room.room_number)
    ).all()
    return render_template(
        "contracts.html",
        contracts=records,
        tenants=available_tenants,
        rooms=available_rooms,
        page_title="Hợp đồng",
        active_page="contracts",
    )
