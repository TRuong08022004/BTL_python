from datetime import date, datetime
from decimal import Decimal

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
ROOM_STATUSES = {"empty": "Còn trống", "rented": "Đang thuê", "repair": "Bảo trì"}
ROOM_CLASSES = {
    "empty": "status-empty",
    "rented": "status-rented",
    "repair": "status-repair",
}


class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(190), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(10), nullable=False, default="admin")
    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)


class Room(db.Model):
    __tablename__ = "rooms"
    id = db.Column(db.Integer, primary_key=True)
    room_number = db.Column(db.String(30), unique=True, nullable=False)
    area = db.Column(db.Numeric(8, 2))
    monthly_price = db.Column(db.Numeric(12, 0), nullable=False)
    electricity_price = db.Column(db.Numeric(10, 0), nullable=False, default=3500)
    water_price = db.Column(db.Numeric(10, 0), nullable=False, default=100000)
    status = db.Column(db.String(10), nullable=False, default="empty")
    description = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)
    contracts = db.relationship("Contract", back_populates="room")

    @property
    def active_contract(self):
        return next(
            (contract for contract in self.contracts if contract.status == "active"),
            None,
        )

    @property
    def tenant_name(self):
        return self.active_contract.tenant.full_name if self.active_contract else ""


class Tenant(db.Model):
    __tablename__ = "tenants"
    id = db.Column(db.Integer, primary_key=True)
    tenant_code = db.Column(db.String(30), unique=True, nullable=False)
    full_name = db.Column(db.String(150), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    identity_number = db.Column(db.String(30), unique=True)
    date_of_birth = db.Column(db.Date)
    address = db.Column(db.String(255), default="")
    move_in_date = db.Column(db.Date)
    status = db.Column(db.String(10), default="active", nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)
    contracts = db.relationship("Contract", back_populates="tenant")

    @property
    def active_contract(self):
        return next(
            (contract for contract in self.contracts if contract.status == "active"),
            None,
        )

    @property
    def room_number(self):
        return self.active_contract.room.room_number if self.active_contract else ""


class Contract(db.Model):
    __tablename__ = "contracts"
    id = db.Column(db.Integer, primary_key=True)
    contract_code = db.Column(db.String(30), unique=True, nullable=False)
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id"), nullable=False)
    room_id = db.Column(db.Integer, db.ForeignKey("rooms.id"), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    monthly_price = db.Column(db.Numeric(12, 0), nullable=False)
    deposit = db.Column(db.Numeric(12, 0), nullable=False, default=0)
    status = db.Column(db.String(12), nullable=False, default="active")
    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)
    room = db.relationship("Room", back_populates="contracts")
    tenant = db.relationship("Tenant", back_populates="contracts")
    invoices = db.relationship("Invoice", back_populates="contract")


class Invoice(db.Model):
    __tablename__ = "invoices"
    id = db.Column(db.Integer, primary_key=True)
    invoice_code = db.Column(db.String(30), unique=True, nullable=False)
    contract_id = db.Column(db.Integer, db.ForeignKey("contracts.id"), nullable=False)
    billing_month = db.Column(db.Date, nullable=False)
    room_charge = db.Column(db.Numeric(12, 0), nullable=False)
    old_electricity = db.Column(db.Integer, nullable=False, default=0)
    new_electricity = db.Column(db.Integer, nullable=False, default=0)
    electricity_charge = db.Column(db.Numeric(12, 0), nullable=False, default=0)
    water_charge = db.Column(db.Numeric(12, 0), nullable=False, default=0)
    service_charge = db.Column(db.Numeric(12, 0), nullable=False, default=0)
    total = db.Column(db.Numeric(12, 0), nullable=False)
    due_date = db.Column(db.Date, nullable=False)
    paid_at = db.Column(db.DateTime)
    status = db.Column(db.String(10), nullable=False, default="unpaid")
    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)
    contract = db.relationship("Contract", back_populates="invoices")
    __table_args__ = (
        db.UniqueConstraint(
            "contract_id", "billing_month", name="unique_contract_month"
        ),
    )

    @property
    def overdue(self):
        return self.status != "paid" and self.due_date < date.today()
