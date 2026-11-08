from datetime import datetime
from decimal import Decimal

from flask import Blueprint, render_template, request
from sqlalchemy import select

from ..helpers import (
    action_response,
    amount,
    billing_month,
    date_field,
    generated_code,
    login_required,
    record_id,
)
from ..models import Contract, Invoice, db

invoices = Blueprint("invoices", __name__)


@invoices.route("/invoices", methods=["GET", "POST"])
@login_required
def index():
    if request.method == "POST":
        action = request.form.get("action")
        if action == "create":
            contract_id = record_id("contract_id")
            period = billing_month()
            due = date_field("due_date")
            old = int(amount("old_electricity", maximum=2147483647))
            new = int(amount("new_electricity", maximum=2147483647))
            if new < old:
                raise ValueError("Chỉ số điện mới không được nhỏ hơn chỉ số cũ.")
            if due < period:
                raise ValueError("Hạn thanh toán không hợp lệ.")
            contract = db.session.scalar(
                select(Contract).where(Contract.id == contract_id).with_for_update()
            )
            if not contract or contract.status != "active":
                raise ValueError("Không tìm thấy hợp đồng đang hiệu lực.")
            if (
                not contract.start_date.strftime("%Y-%m")
                <= period.strftime("%Y-%m")
                <= contract.end_date.strftime("%Y-%m")
            ):
                raise ValueError("Kỳ hóa đơn nằm ngoài thời hạn hợp đồng.")
            electricity = Decimal(new - old) * contract.room.electricity_price
            water = amount("water_charge", optional=True)
            if water is None:
                water = contract.room.water_price
            service = amount("service_charge", optional=True) or Decimal(0)
            total = contract.monthly_price + electricity + water + service
            if total > Decimal("999999999999"):
                raise ValueError("Tổng hóa đơn vượt giới hạn cho phép.")
            db.session.add(
                Invoice(
                    invoice_code=generated_code("INV"),
                    contract_id=contract.id,
                    billing_month=period,
                    room_charge=contract.monthly_price,
                    old_electricity=old,
                    new_electricity=new,
                    electricity_charge=electricity,
                    water_charge=water,
                    service_charge=service,
                    total=total,
                    due_date=due,
                    status="unpaid",
                )
            )
            db.session.commit()
            return action_response("Đã tạo hóa đơn.", "invoices.index")
        if action == "paid":
            invoice_id = record_id("id")
            invoice = db.session.scalar(
                select(Invoice).where(Invoice.id == invoice_id).with_for_update()
            )
            if not invoice or invoice.status == "paid":
                raise ValueError("Không tìm thấy hóa đơn hoặc hóa đơn đã thanh toán.")
            invoice.status = "paid"
            invoice.paid_at = datetime.now()
            db.session.commit()
            return action_response("Đã xác nhận thanh toán.", "invoices.index")
        raise ValueError("Thao tác không hợp lệ.")
    records = db.session.scalars(
        select(Invoice).order_by(Invoice.billing_month.desc(), Invoice.id.desc())
    ).all()
    active = db.session.scalars(
        select(Contract).where(Contract.status == "active")
    ).all()
    return render_template(
        "invoices.html",
        invoices=records,
        contracts=active,
        page_title="Hóa đơn",
        active_page="invoices",
    )
