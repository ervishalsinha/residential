import unittest
import uuid

from fastapi import Depends
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models import Base, Property, PropertyType, ResidentProfile, Role, User
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


class OwnerMultiPropertyTests(unittest.TestCase):
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
        self.seeded = self._seed_base()

        def _owner_override(db: Session = Depends(get_db)):
            return db.query(User).filter(User.id == self.seeded["owner_id"]).first()

        app.dependency_overrides[get_current_user] = _owner_override

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()

    def _seed_base(self):
        db = TestingSessionLocal()
        try:
            owner_role = Role(id=str(uuid.uuid4()), name="property_admin")
            owner = User(
                id=str(uuid.uuid4()),
                full_name="Owner A",
                mobile_number="9000000011",
                email="owner@example.com",
                password_hash="hash",
                role_id=owner_role.id,
            )
            property_type_pg = PropertyType(id=str(uuid.uuid4()), name="pg")
            property_type_building = PropertyType(id=str(uuid.uuid4()), name="apartment")
            db.add_all([owner_role, owner, property_type_pg, property_type_building])
            db.commit()
            return {
                "owner_id": owner.id,
                "pg_type_id": property_type_pg.id,
                "building_type_id": property_type_building.id,
            }
        finally:
            db.close()

    def test_first_property_becomes_primary_and_selected(self):
        response = self.client.post(
            "/api/v1/properties",
            json={
                "name": "Sunrise PG",
                "property_type": "pg",
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload.get("is_primary"))
        self.assertEqual(payload.get("property_type"), "pg")

        me = self.client.get("/api/v1/auth/me")
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.json().get("selected_property_id"), payload.get("id"))

    def test_duplicate_property_name_is_blocked_per_owner(self):
        first = self.client.post(
            "/api/v1/properties",
            json={
                "name": "Blue Heights",
                "property_type": "building",
            },
        )
        self.assertEqual(first.status_code, 200)

        duplicate = self.client.post(
            "/api/v1/properties",
            json={
                "name": "blue heights",
                "property_type": "building",
            },
        )
        self.assertEqual(duplicate.status_code, 409)

    def test_cannot_delete_primary_or_last_property(self):
        first = self.client.post(
            "/api/v1/properties",
            json={
                "name": "Prime House",
                "property_type": "building",
            },
        )
        self.assertEqual(first.status_code, 200)

        delete_last = self.client.delete(f"/api/v1/properties/{first.json()['id']}")
        self.assertEqual(delete_last.status_code, 400)

        second = self.client.post(
            "/api/v1/properties",
            json={
                "name": "Prime Annex",
                "property_type": "building",
            },
        )
        self.assertEqual(second.status_code, 200)

        delete_primary = self.client.delete(f"/api/v1/properties/{first.json()['id']}")
        self.assertEqual(delete_primary.status_code, 400)

    def test_cannot_delete_property_with_active_residents(self):
        first = self.client.post(
            "/api/v1/properties",
            json={
                "name": "Main Block",
                "property_type": "building",
            },
        )
        self.assertEqual(first.status_code, 200)

        second = self.client.post(
            "/api/v1/properties",
            json={
                "name": "Annex Block",
                "property_type": "building",
            },
        )
        self.assertEqual(second.status_code, 200)

        db = TestingSessionLocal()
        try:
            resident_role = Role(id=str(uuid.uuid4()), name="resident")
            resident = User(
                id=str(uuid.uuid4()),
                full_name="Resident 1",
                mobile_number="9000000012",
                email="r1@example.com",
                password_hash="hash",
                role_id=resident_role.id,
            )
            profile = ResidentProfile(
                id=str(uuid.uuid4()),
                user_id=resident.id,
                owner_user_id=self.seeded["owner_id"],
                property_id=second.json()["id"],
                occupancy_status="active",
            )
            db.add_all([resident_role, resident, profile])
            db.commit()
        finally:
            db.close()

        blocked = self.client.delete(f"/api/v1/properties/{second.json()['id']}")
        self.assertEqual(blocked.status_code, 400)

    def test_switch_property_updates_selected_property(self):
        first = self.client.post(
            "/api/v1/properties",
            json={
                "name": "Owner Tower",
                "property_type": "building",
            },
        )
        second = self.client.post(
            "/api/v1/properties",
            json={
                "name": "Owner PG",
                "property_type": "pg",
            },
        )
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)

        switch = self.client.post(f"/api/v1/properties/{second.json()['id']}/switch")
        self.assertEqual(switch.status_code, 200)
        self.assertEqual(switch.json().get("selected_property_id"), second.json()["id"])

        me = self.client.get("/api/v1/auth/me")
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.json().get("selected_property_id"), second.json()["id"])


if __name__ == "__main__":
    unittest.main()
