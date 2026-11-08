from datetime import date
from decimal import Decimal
import re

from flask import Blueprint, abort, render_template, request
from sqlalchemy import select

from ..helpers import login_required
from ..models import Invoice, Room, db

reports = Blueprint("reports", __name__)


def monthly_summary(invoices):
    groups = {}
    for invoice in invoices:
        label = invoice.billing_month.strftime("%Y-%m")
        row = groups.setdefault(
            label, dict(label=label, total=Decimal(0), paid_count=0, invoice_count=0)
        )
        row["invoice_count"] += 1
        if invoice.status == "paid":
            row["total"] += invoice.total
            row["paid_count"] += 1
    return [groups[label] for label in sorted(groups)]


@reports.get("/")
@login_required
def dashboard():
    rooms = db.session.scalars(select(Room)).all()
    invoices = db.session.scalars(
        select(Invoice).order_by(Invoice.created_at.desc(), Invoice.id.desc())
    ).all()
    current_month = date.today().strftime("%Y-%m")
    month = request.args.get("month", current_month).strip()
    if not re.fullmatch(r"[0-9]{4}-(0[1-9]|1[0-2])", month) or month[:4] == "0000":
        abort(400, "Tháng thống kê không hợp lệ.")
    available_months = sorted(
        {current_month, month}
        | {invoice.billing_month.strftime("%Y-%m") for invoice in invoices},
        reverse=True,
    )
    paid_in_month = [
        invoice
        for invoice in invoices
        if invoice.status == "paid" and invoice.billing_month.strftime("%Y-%m") == month
    ]
    stats = dict(
        rooms=len(rooms),
        rented=sum(room.status == "rented" for room in rooms),
        revenue=sum((invoice.total for invoice in paid_in_month), Decimal(0)),
        overdue=sum(invoice.overdue for invoice in invoices),
    )
    return render_template(
        "index.html",
        stats=stats,
        recent_invoices=invoices[:5],
        revenue_month=month,
        revenue_month_label=f"{month[5:]}/{month[:4]}",
        revenue_months=[
            (value, f"{value[5:]}/{value[:4]}") for value in available_months
        ],
        has_paid_invoices=bool(paid_in_month),
        page_title="Tổng quan",
        active_page="dashboard",
    )


@reports.get("/reports")
@login_required
def index():
    invoices = db.session.scalars(select(Invoice)).all()
    return render_template(
        "reports.html",
        monthly=monthly_summary(invoices),
        page_title="Báo cáo",
        active_page="reports",
    )
