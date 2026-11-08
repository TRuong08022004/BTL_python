import hashlib
import unittest
from datetime import date, timedelta
from decimal import Decimal

import bcrypt
from sqlalchemy import select
from werkzeug.security import generate_password_hash

from backend import create_app
from backend.models import Contract, Invoice, Room, Tenant, User, db


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "tests",
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            }
        )
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        db.session.add(
            User(
                name="Admin",
                email="admin@motel.vn",
                password=generate_password_hash("test-password"),
                role="admin",
            )
        )
        db.session.commit()
        self.client = self.app.test_client()
        self.post(
            "/login", email="admin@motel.vn", password="test-password", ajax=False
        )

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def post(self, path, ajax=True, **data):
        self.client.get("/login")
        with self.client.session_transaction() as session:
            data["csrf_token"] = session["csrf_token"]
        headers = {"X-Requested-With": "XMLHttpRequest"} if ajax else {}
        return self.client.post(
            path, data=data, headers=headers, follow_redirects=not ajax
        )

    def room(self, **changes):
        data = dict(
            action="create",
            room_number="101",
            area="22.50",
            monthly_price="2500000",
            electricity_price="3500",
            water_price="100000",
            status="empty",
            description="Có cửa sổ",
        )
        data.update(changes)
        return self.post("/rooms", **data)

    def tenant(self, **changes):
        data = dict(
            action="create",
            full_name="Khách thử nghiệm",
            phone="0900000000",
            identity_number="012345678901",
            date_of_birth="2000-01-01",
            move_in_date=date.today().isoformat(),
            address="Hà Nội",
        )
        data.update(changes)
        return self.post("/tenants", **data)

    def contract(self):
        self.room()
        self.tenant()
        response = self.post(
            "/contracts",
            tenant_id=1,
            room_id=1,
            start_date=date.today().replace(day=1).isoformat(),
            end_date=(date.today() + timedelta(days=365)).isoformat(),
            monthly_price=2500000,
            deposit=2500000,
        )
        self.assertEqual(response.status_code, 200)
        return response

    def invoice(self, **changes):
        data = dict(
            action="create",
            contract_id=1,
            billing_month=date.today().strftime("%Y-%m"),
            old_electricity=100,
            new_electricity=150,
            water_charge="",
            service_charge=80000,
            due_date=date.today().isoformat(),
        )
        data.update(changes)
        return self.post("/invoices", **data)

    def test_full_contract_invoice_and_payment(self):
        self.contract()
        self.assertEqual(db.session.get(Room, 1).status, "rented")
        response = self.invoice()
        self.assertEqual(response.status_code, 200)
        invoice = db.session.scalar(select(Invoice))
        self.assertEqual(invoice.total, Decimal("2855000"))
        self.assertEqual(invoice.water_charge, Decimal("100000"))
        self.assertEqual(
            self.post("/invoices", action="paid", id=invoice.id).status_code, 200
        )
        self.assertEqual(invoice.status, "paid")
        self.assertIsNotNone(invoice.paid_at)
        paid_at = invoice.paid_at
        self.assertEqual(
            self.post("/invoices", action="paid", id=invoice.id).status_code, 422
        )
        self.assertEqual(invoice.paid_at, paid_at)

    def test_room_status_ajax_and_rules(self):
        self.room()
        response = self.post("/api/rooms/update-status", id=1, status="repair")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["data"]["status"], "repair")
        self.assertEqual(
            self.post("/api/rooms/update-status", id=1, status="rented").status_code,
            422,
        )
        self.assertEqual(
            self.post("/api/rooms/update-status", id=1, status="empty").status_code, 200
        )
        self.tenant()
        self.post(
            "/contracts",
            tenant_id=1,
            room_id=1,
            start_date=date.today().isoformat(),
            end_date=(date.today() + timedelta(days=365)).isoformat(),
            monthly_price=2500000,
            deposit=0,
        )
        self.assertEqual(
            self.post("/api/rooms/update-status", id=1, status="empty").status_code, 422
        )

    def test_room_validation_and_duplicates(self):
        for values in (
            {"monthly_price": -1},
            {"area": "NaN"},
            {"area": 0},
            {"monthly_price": "Infinity"},
            {"status": "rented"},
            {"room_number": "x" * 31},
        ):
            self.assertEqual(self.room(**values).status_code, 422)
        self.assertEqual(db.session.scalars(select(Room)).all(), [])
        self.assertEqual(self.room(area="999999.99").status_code, 200)
        self.assertEqual(self.room().status_code, 409)

    def test_tenant_validation_and_duplicate_identity(self):
        self.assertEqual(self.tenant(date_of_birth="2026-02-31").status_code, 422)
        self.assertEqual(self.tenant(full_name="").status_code, 422)
        self.assertEqual(self.tenant().status_code, 200)
        self.assertEqual(self.tenant(full_name="Khách khác").status_code, 409)

    def test_delete_only_records_without_history(self):
        self.contract()
        self.assertEqual(self.post("/rooms", action="delete", id=1).status_code, 422)
        self.assertEqual(self.post("/tenants", action="delete", id=1).status_code, 422)
        self.room(room_number="102")
        self.assertEqual(self.post("/rooms", action="delete", id=2).status_code, 200)
        self.assertIsNone(db.session.get(Room, 2))

    def test_duplicate_active_contract_rejected(self):
        self.contract()
        response = self.post(
            "/contracts",
            tenant_id=1,
            room_id=1,
            start_date=date.today().isoformat(),
            end_date=(date.today() + timedelta(days=365)).isoformat(),
            monthly_price=2500000,
            deposit=0,
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(len(db.session.scalars(select(Contract)).all()), 1)

    def test_invoice_validation_period_and_unique_month(self):
        self.contract()
        for changes in (
            {"new_electricity": 99},
            {"old_electricity": "1.5"},
            {"water_charge": -1},
            {"billing_month": "2000-01"},
            {"billing_month": "2026-13"},
            {"due_date": "2000-01-01"},
            {"service_charge": "NaN"},
        ):
            self.assertEqual(self.invoice(**changes).status_code, 422)
        self.assertEqual(db.session.scalars(select(Invoice)).all(), [])
        self.assertEqual(self.invoice().status_code, 200)
        self.assertEqual(self.invoice().status_code, 409)

    def test_csrf_rejects_missing_empty_and_wrong_tokens(self):
        anonymous = self.app.test_client()
        self.assertEqual(
            anonymous.post(
                "/login", data={"email": "admin@motel.vn", "password": "test-password"}
            ).status_code,
            400,
        )
        self.assertEqual(
            self.client.post("/rooms", data={"action": "create"}).status_code, 400
        )
        self.assertEqual(
            self.client.post(
                "/rooms",
                data={"csrf_token": "wrong"},
                headers={"X-Requested-With": "XMLHttpRequest"},
            ).status_code,
            400,
        )

    def test_auth_and_logout(self):
        self.post("/logout", ajax=False)
        self.assertEqual(self.client.get("/rooms").status_code, 302)
        response = self.client.get(
            "/rooms", headers={"X-Requested-With": "XMLHttpRequest"}
        )
        self.assertEqual(response.status_code, 401)
        self.assertTrue(response.is_json)
        self.post("/login", ajax=False, email="admin@motel.vn", password="wrong")
        with self.client.session_transaction() as session:
            self.assertNotIn("user_id", session)

    def test_php_bcrypt_password_migrates_on_login(self):
        user = db.session.get(User, 1)
        user.password = (
            bcrypt.hashpw(b"php-password", bcrypt.gensalt(rounds=4))
            .decode()
            .replace("$2b$", "$2y$", 1)
        )
        db.session.commit()
        self.post("/logout", ajax=False)
        self.post("/login", ajax=False, email=user.email, password="php-password")
        self.assertTrue(user.password.startswith("scrypt:"))
        with self.client.session_transaction() as session:
            self.assertEqual(session.get("user_id"), 1)

    def test_php_sha1_password_migrates_on_login(self):
        user = db.session.get(User, 1)
        user.password = "$sha1$" + hashlib.sha1(b"legacy-password").hexdigest()
        db.session.commit()
        self.post("/logout", ajax=False)
        self.post("/login", ajax=False, email=user.email, password="legacy-password")
        self.assertTrue(user.password.startswith("scrypt:"))

    def test_all_pages_and_report_without_external_analysis(self):
        self.contract()
        self.invoice()
        for path in ("/", "/rooms", "/tenants", "/contracts", "/invoices", "/reports"):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200, path)
            self.assertNotIn(b"<?php", response.data)
            self.assertNotIn(b"<canvas", response.data)
            self.assertNotIn(b"chart.js", response.data)
        report = self.client.get("/reports").get_data(as_text=True)
        self.assertIn("Chi tiết theo kỳ", report)
        self.assertNotIn("data-ai-report", report)
        self.assertNotIn("Trợ lý phân tích", report)
        self.assertEqual(
            self.client.get("/api/ai/analyze-monthly-report.php").status_code, 404
        )

    def test_template_escapes_untrusted_text(self):
        self.room(room_number="<script>alert(1)</script>")
        html = self.client.get("/rooms").get_data(as_text=True)
        self.assertIn("&lt;script&gt;", html)
        self.assertNotIn("<script>alert(1)</script>", html)


if __name__ == "__main__":
    unittest.main()
