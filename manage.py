import argparse
import getpass
import re
import secrets
import sys
from datetime import date, datetime

from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.dialects import mysql
from sqlalchemy.schema import CreateTable
from werkzeug.security import generate_password_hash

from backend import ROOT, create_app
from backend.models import Contract, Invoice, Room, Tenant, User, db

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

MODELS = (User, Room, Tenant, Contract, Invoice)


def database_name(name):
    if not re.fullmatch(r"[A-Za-z0-9_]+", name or ""):
        raise SystemExit("Tên CSDL chỉ gồm chữ, số và dấu gạch dưới.")
    return name


def create_database():
    name = database_name(db.engine.url.database)
    engine = create_engine(db.engine.url.set(database=""))
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    f"CREATE DATABASE IF NOT EXISTS `{name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                )
            )
    finally:
        engine.dispose()
    db.create_all()


def upgrade_database():
    column = next(
        item
        for item in inspect(db.engine).get_columns("contracts")
        if item["name"] == "tenant_id"
    )
    if not column["nullable"]:
        if db.engine.dialect.name != "mysql":
            raise SystemExit("Cần nâng cấp contracts.tenant_id để cho phép NULL.")
        column_type = column["type"].compile(dialect=db.engine.dialect)
        with db.engine.begin() as connection:
            connection.execute(
                text(f"ALTER TABLE contracts MODIFY tenant_id {column_type} NULL")
            )
    removed = db.session.scalars(
        select(Tenant).where(
            Tenant.status == "inactive",
            ~Tenant.contracts.any(Contract.status == "active"),
        )
    ).all()
    for tenant in removed:
        tenant.delete_profile()
    db.session.commit()
    return len(removed)


def import_php(source_database):
    source_database = database_name(source_database)
    if source_database == db.engine.url.database:
        raise SystemExit("CSDL nguồn và đích phải khác nhau.")
    create_database()
    for model in MODELS:
        if db.session.scalar(select(model.id).limit(1)):
            raise SystemExit(
                "CSDL đích đã có dữ liệu. Dừng để không ghi đè hoặc nhập trùng."
            )

    source = create_engine(db.engine.url.set(database=source_database))
    try:
        with source.connect() as connection:
            for model in MODELS:
                if not inspect(connection).has_table(model.__tablename__):
                    raise ValueError(f"Nguồn thiếu bảng {model.__tablename__}.")
            counts = {}
            for model in MODELS:
                columns = {column.name for column in model.__table__.columns}
                rows = (
                    connection.execute(text(f"SELECT * FROM `{model.__tablename__}`"))
                    .mappings()
                    .all()
                )
                for row in rows:
                    values = {
                        key: value for key, value in row.items() if key in columns
                    }
                    db.session.add(model(**values))
                db.session.flush()
                counts[model.__tablename__] = len(rows)
            db.session.commit()
            print("Đã sao chép dữ liệu từ bản PHP:", counts)
            print("Tài khoản và mật khẩu giữ nguyên. CSDL PHP không thay đổi.")
    except Exception:
        db.session.rollback()
        raise
    finally:
        source.dispose()


def seed_demo():
    if any(
        db.session.scalar(select(model.id).limit(1))
        for model in (Room, Tenant, Contract, Invoice)
    ):
        print("Đã có dữ liệu nghiệp vụ; bỏ qua mẫu.")
        return
    rooms = []
    for number, area, price, status in [
        ("102", 22, 3500000, "empty"),
        ("201", 25, 4000000, "repair"),
        ("203", 25, 4200000, "rented"),
        ("301", 24, 3900000, "empty"),
        ("305", 28, 4500000, "rented"),
        ("401", 25, 4100000, "rented"),
    ]:
        room = Room(
            room_number=number,
            area=area,
            monthly_price=price,
            status=status,
            description="Phòng minh họa",
        )
        db.session.add(room)
        rooms.append(room)
    tenants = []
    for index, name in enumerate(
        ("Trần Minh Anh", "Nguyễn Hoàng Nam", "Phạm Quốc Huy"), 1
    ):
        tenant = Tenant(
            tenant_code=f"KH{index:03}",
            full_name=name,
            phone=f"090000000{index}",
            status="active",
        )
        db.session.add(tenant)
        tenants.append(tenant)
    db.session.flush()
    contracts = []
    for index, room in enumerate((rooms[2], rooms[4], rooms[5])):
        contract = Contract(
            contract_code=f"HD{index+1:03}",
            tenant_id=tenants[index].id,
            room_id=room.id,
            start_date=date(2026, 1, 1),
            end_date=date(2027, 12, 31),
            monthly_price=room.monthly_price,
            deposit=room.monthly_price,
            status="active",
        )
        db.session.add(contract)
        contracts.append(contract)
    db.session.flush()
    for index, contract in enumerate(contracts):
        db.session.add(
            Invoice(
                invoice_code=f"INV20260700{index+1}",
                contract_id=contract.id,
                billing_month=date(2026, 7, 1),
                room_charge=contract.monthly_price,
                old_electricity=100,
                new_electricity=150,
                electricity_charge=175000,
                water_charge=100000,
                service_charge=80000,
                total=contract.monthly_price + 355000,
                due_date=date(2026, 7, 10),
                status="paid" if index == 1 else "unpaid",
                paid_at=datetime(2026, 7, 10) if index == 1 else None,
            )
        )
    db.session.commit()
    print("Đã tạo 6 phòng, 3 khách thuê, 3 hợp đồng và 3 hóa đơn minh họa.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=["init", "import-php", "reset-password", "export-schema", "upgrade"],
    )
    parser.add_argument("--source-db", default="motel_management")
    parser.add_argument("--email", default="admin@motel.vn")
    parser.add_argument("--demo", action="store_true")
    args = parser.parse_args()
    app = create_app()
    with app.app_context():
        if args.command == "import-php":
            import_php(args.source_db)
        elif args.command == "upgrade":
            create_database()
            removed = upgrade_database()
            print(f"Đã nâng cấp CSDL. Đã xóa {removed} hồ sơ khách từng bị ẩn.")
        elif args.command == "export-schema":
            name = database_name(db.engine.url.database)
            sql = f"CREATE DATABASE IF NOT EXISTS `{name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;\nUSE `{name}`;\n"
            for table in db.metadata.sorted_tables:
                sql += (
                    str(
                        CreateTable(table, if_not_exists=True).compile(
                            dialect=mysql.dialect()
                        )
                    )
                    + ";\n"
                )
            (ROOT / "database").mkdir(exist_ok=True)
            (ROOT / "database/schema.sql").write_text(sql, encoding="utf-8")
            print("Đã xuất database/schema.sql.")
        elif args.command == "init":
            create_database()
            upgrade_database()
            if not db.session.scalar(select(User).where(User.email == args.email)):
                password = secrets.token_urlsafe(12)
                db.session.add(
                    User(
                        name="Quản trị viên",
                        email=args.email,
                        password=generate_password_hash(password),
                        role="admin",
                    )
                )
                db.session.commit()
                print(f"Tài khoản: {args.email}\nMật khẩu khởi tạo: {password}")
            else:
                print("Giữ nguyên tài khoản hiện có.")
            if args.demo:
                seed_demo()
        else:
            user = db.session.scalar(select(User).where(User.email == args.email))
            if not user:
                raise SystemExit(
                    "Không tìm thấy tài khoản. Chạy init hoặc kiểm tra --email."
                )
            password = getpass.getpass("Mật khẩu mới (ít nhất 10 ký tự): ")
            if len(password) < 10 or password != getpass.getpass("Nhập lại: "):
                raise SystemExit("Mật khẩu quá ngắn hoặc không khớp.")
            user.password = generate_password_hash(password)
            db.session.commit()
            print("Đã đổi mật khẩu của bản Python.")


if __name__ == "__main__":
    main()
