from datetime import date
from decimal import Decimal

from flask import Blueprint, render_template
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
    month = date.today().strftime("%Y-%m")
    stats = dict(
        rooms=len(rooms),
        rented=sum(room.status == "rented" for room in rooms),
        revenue=sum(
            invoice.total
            for invoice in invoices
            if invoice.status == "paid"
            and invoice.billing_month.strftime("%Y-%m") == month
        ),
        overdue=sum(invoice.overdue for invoice in invoices),
    )
    return render_template(
        "index.html",
        stats=stats,
        recent_invoices=invoices[:5],
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
