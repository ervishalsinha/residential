import unittest
import uuid
from datetime import datetime, timezone

from fastapi import Depends
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models import Base, Payment, Property, PropertyType, ResidentProfile, Role, User
from main import app


TEST_ENGINE = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=TEST_ENGINE)


def _override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


class PaymentRoutingValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=TEST_ENGINE)

    @classmethod
    def tearDownClass(cls):
        Base.metadata.drop_all(bind=TEST_ENGINE)

    def setUp(self):
        Base.metadata.drop_all(bind=TEST_ENGINE)
        Base.metadata.create_all(bind=TEST_ENGINE)
        app.dependency_overrides.clear()
        app.dependency_overrides[get_db] = _override_get_db
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()

    def _seed(self, *, owner_active_method: str | None, owner_upi: str | None, owner_account: str | None, owner_ifsc: str | None):
        db = TestingSessionLocal()
        try:
            role_owner = Role(id=str(uuid.uuid4()), name="property_admin")
            role_resident = Role(id=str(uuid.uuid4()), name="resident")
            db.add_all([role_owner, role_resident])

            owner = User(
                id=str(uuid.uuid4()),
                full_name="Owner One",
                mobile_number="9000000001",
                email="owner@example.com",
                password_hash="hashed",
                role_id=role_owner.id,
                payment_upi_id=owner_upi,
                payment_bank_account_number=owner_account,
                payment_bank_ifsc=owner_ifsc,
                active_payment_method=owner_active_method,
            )
            resident_user = User(
                id=str(uuid.uuid4()),
                full_name="Resident One",
                mobile_number="9000000002",
                email="resident@example.com",
                password_hash="hashed",
                role_id=role_resident.id,
            )

            property_type = PropertyType(id=str(uuid.uuid4()), name="Apartment")
            property_row = Property(
                id=str(uuid.uuid4()),
                name="Sample Property",
                owner_user_id=owner.id,
                property_type_id=property_type.id,
                address_line1="Street 1",
                city="Pune",
                state="Maharashtra",
                pincode="411001",
                total_units=10,
            )

            resident_profile = ResidentProfile(
                id=str(uuid.uuid4()),
                user_id=resident_user.id,
                owner_user_id=owner.id,
                owner_mobile=owner.mobile_number,
                property_id=property_row.id,
                occupancy_status="active",
                joining_date=datetime.now(timezone.utc).date(),
            )

            payment = Payment(
                id=str(uuid.uuid4()),
                resident_id=resident_user.id,
                property_id=property_row.id,
                amount=5000,
                payment_type="rent",
                status="pending",
                due_date=datetime.now(timezone.utc).replace(tzinfo=None),
                rent_year=2026,
                rent_month=5,
            )

            db.add_all([owner, resident_user, property_type, property_row, resident_profile, payment])
            db.commit()
            return {
                "owner_id": owner.id,
                "resident_id": resident_user.id,
                "payment_id": payment.id,
            }
        finally:
            db.close()

    def test_active_method_validation_requires_upi_details(self):
        seeded = self._seed(owner_active_method="upi", owner_upi="owner@upi", owner_account=None, owner_ifsc=None)

        def _owner_user_override(db: Session = Depends(get_db)):
            return db.query(User).filter(User.id == seeded["owner_id"]).first()

        app.dependency_overrides[get_current_user] = _owner_user_override

        response = self.client.put(
            "/api/v1/auth/payment-settings",
            json={
                "active_payment_method": "upi",
                "payment_upi_id": "",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("UPI ID is required", response.json().get("detail", ""))

    def test_resident_payment_blocked_when_owner_settings_incomplete(self):
        seeded = self._seed(
            owner_active_method="bank",
            owner_upi=None,
            owner_account="123456789012",
            owner_ifsc=None,
        )

        def _resident_user_override(db: Session = Depends(get_db)):
            return db.query(User).filter(User.id == seeded["resident_id"]).first()

        app.dependency_overrides[get_current_user] = _resident_user_override

        response = self.client.put(
            f"/api/v1/payments/{seeded['payment_id']}",
            json={"status": "paid", "gateway_channel": "upi"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Owner payment destination is not configured", response.json().get("detail", ""))


if __name__ == "__main__":
    unittest.main()
