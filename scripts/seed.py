from pathlib import Path
import sys

# Allow running this file directly: python scripts/seed.py
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.db.session import SessionLocal
from app.models import Complaint, EmergencyAlert, Notice, Payment, Property, PropertyType, ResidentProfile, Role, Staff, User, Visitor


def run_seed() -> None:
    db = SessionLocal()
    try:
        for role_name in ["super_admin", "property_admin", "resident", "security_guard"]:
            exists = db.query(Role).filter(Role.name == role_name).first()
            if not exists:
                db.add(Role(name=role_name))

        for property_type in ["apartment", "gated_society", "hostel", "pg", "standalone_building"]:
            exists = db.query(PropertyType).filter(PropertyType.name == property_type).first()
            if not exists:
                db.add(PropertyType(name=property_type))

        db.commit()

        apartment_type = db.query(PropertyType).filter(PropertyType.name == "apartment").first()
        resident_role = db.query(Role).filter(Role.name == "resident").first()
        admin_role = db.query(Role).filter(Role.name == "super_admin").first()
        if not apartment_type or not resident_role or not admin_role:
            raise RuntimeError("Required seed base entities are missing")

        admin_user = db.query(User).filter(User.mobile_number == "9999999999").first()
        if not admin_user:
            admin_user = User(full_name="Platform Admin", mobile_number="9999999999", role_id=admin_role.id)
            db.add(admin_user)
            db.flush()

        sample_property = db.query(Property).filter(Property.name == "Sunrise Residency").first()
        if not sample_property:
            sample_property = Property(
                name="Sunrise Residency",
                owner_user_id=admin_user.id,
                property_type_id=apartment_type.id,
                address_line1="Sector 21",
                city="Noida",
                state="Uttar Pradesh",
                pincode="201301",
                total_units=120,
            )
            db.add(sample_property)
            db.flush()
        elif not sample_property.owner_user_id:
            sample_property.owner_user_id = admin_user.id

        resident_user = db.query(User).filter(User.mobile_number == "8888888888").first()
        if not resident_user:
            resident_user = User(full_name="Demo Resident", mobile_number="8888888888", role_id=resident_role.id)
            db.add(resident_user)
            db.flush()

        resident_profile = db.query(ResidentProfile).filter(ResidentProfile.user_id == resident_user.id).first()
        if not resident_profile:
            db.add(ResidentProfile(user_id=resident_user.id, property_id=sample_property.id, occupancy_status="active"))

        complaint = db.query(Complaint).filter(Complaint.title == "Water leakage in kitchen").first()
        if not complaint:
            db.add(
                Complaint(
                    resident_id=resident_user.id,
                    property_id=sample_property.id,
                    category="plumbing",
                    title="Water leakage in kitchen",
                    description="Leakage observed under sink from the inlet pipe.",
                    priority="high",
                )
            )

        visitor = db.query(Visitor).filter(Visitor.mobile_number == "7777777777").first()
        if not visitor:
            db.add(
                Visitor(
                    property_id=sample_property.id,
                    resident_id=resident_user.id,
                    name="Ravi Kumar",
                    mobile_number="7777777777",
                    purpose="Family visit",
                )
            )

        payment = db.query(Payment).filter(Payment.payment_type == "maintenance").first()
        if not payment:
            db.add(Payment(resident_id=resident_user.id, property_id=sample_property.id, amount=3500.0, payment_type="maintenance"))

        staff_member = db.query(Staff).filter(Staff.mobile_number == "6666666666").first()
        if not staff_member:
            db.add(Staff(property_id=sample_property.id, full_name="Suresh Yadav", role="security_guard", mobile_number="6666666666"))

        notice = db.query(Notice).filter(Notice.title == "Water Tank Cleaning").first()
        if not notice:
            db.add(
                Notice(
                    property_id=sample_property.id,
                    title="Water Tank Cleaning",
                    content="Water supply will be interrupted from 10:00 AM to 2:00 PM on Sunday.",
                    published_by=admin_user.id,
                )
            )

        emergency = db.query(EmergencyAlert).filter(EmergencyAlert.alert_type == "medical").first()
        if not emergency:
            db.add(
                EmergencyAlert(
                    property_id=sample_property.id,
                    raised_by=resident_user.id,
                    alert_type="medical",
                    description="Resident in Tower B requires urgent medical support.",
                    status="active",
                )
            )

        db.commit()
        print("Seed data inserted successfully")
    finally:
        db.close()


if __name__ == "__main__":
    run_seed()
