from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class PropertyCreate(BaseModel):
    name: str
    property_type_id: UUID
    address_line1: str
    city: str
    state: str
    pincode: str
    total_units: int = 0


class PropertyUpdate(BaseModel):
    name: str | None = None
    address_line1: str | None = None
    city: str | None = None
    state: str | None = None
    pincode: str | None = None
    total_units: int | None = None


class UnitCreate(BaseModel):
    property_id: UUID
    unit_number: str
    floor: int | None = None
    capacity: int = 1


class UnitUpdate(BaseModel):
    unit_number: str | None = None
    floor: int | None = None
    capacity: int | None = None


class ResidentCreate(BaseModel):
    user_id: UUID
    property_id: UUID
    unit_id: UUID | None = None
    occupancy_status: str = "active"
    monthly_rent: float | None = None
    security_deposit: float | None = None
    electricity_bill: float | None = None
    maintenance_bill: float | None = None
    parking_charges: float | None = None
    wifi_charges: float | None = None
    cleaning_bill: float | None = None
    water_bill: float | None = None
    payment_due_day: int | None = None
    joining_date: datetime | None = None
    vacated_on: datetime | None = None
    aadhaar_image_url: str | None = None
    emergency_contact_name: str | None = None
    emergency_contact_number: str | None = None


class ManagedTenantCreate(BaseModel):
    full_name: str
    mobile_number: str
    password: str
    email: str | None = None
    property_id: UUID
    unit_id: UUID | None = None
    occupancy_status: str = "active"
    monthly_rent: float | None = None
    security_deposit: float | None = None
    electricity_bill: float | None = None
    maintenance_bill: float | None = None
    parking_charges: float | None = None
    wifi_charges: float | None = None
    cleaning_bill: float | None = None
    water_bill: float | None = None
    payment_due_day: int | None = None
    joining_date: datetime | None = None
    vacated_on: datetime | None = None
    aadhaar_image_url: str | None = None
    emergency_contact_name: str | None = None
    emergency_contact_number: str | None = None


class ResidentUpdate(BaseModel):
    unit_id: UUID | None = None
    occupancy_status: str | None = None
    monthly_rent: float | None = None
    security_deposit: float | None = None
    electricity_bill: float | None = None
    maintenance_bill: float | None = None
    parking_charges: float | None = None
    wifi_charges: float | None = None
    cleaning_bill: float | None = None
    water_bill: float | None = None
    payment_due_day: int | None = None
    joining_date: datetime | None = None
    vacated_on: datetime | None = None
    aadhaar_image_url: str | None = None
    emergency_contact_name: str | None = None
    emergency_contact_number: str | None = None


class ComplaintCreate(BaseModel):
    resident_id: UUID
    property_id: UUID
    category: str | None = None
    visibility: str = "owner_and_tenants"
    title: str
    description: str
    image_urls: list[str] | None = None
    priority: str = "medium"


class ComplaintUpdate(BaseModel):
    category: str | None = None
    visibility: str | None = None
    title: str | None = None
    description: str | None = None
    image_urls: list[str] | None = None
    priority: str | None = None
    status: str | None = None


class VisitorCreate(BaseModel):
    property_id: UUID
    resident_id: UUID
    name: str
    mobile_number: str
    purpose: str


class VisitorUpdate(BaseModel):
    name: str | None = None
    mobile_number: str | None = None
    purpose: str | None = None
    status: str | None = None


class PaymentCreate(BaseModel):
    resident_id: UUID
    property_id: UUID
    amount: float
    payment_type: str
    due_date: datetime | None = None
    rent_year: int | None = None
    rent_month: int | None = None


class PaymentUpdate(BaseModel):
    amount: float | None = None
    payment_type: str | None = None
    status: str | None = None
    due_date: datetime | None = None
    rent_year: int | None = None
    rent_month: int | None = None
    gateway_channel: str | None = None


class StaffCreate(BaseModel):
    property_id: UUID
    full_name: str
    role: str
    mobile_number: str


class StaffUpdate(BaseModel):
    full_name: str | None = None
    role: str | None = None
    mobile_number: str | None = None


class NoticeCreate(BaseModel):
    property_id: UUID
    title: str
    content: str
    published_by: UUID
    image_url: str | None = None
    image_urls: list[str] | None = None


class NoticeUpdate(BaseModel):
    title: str | None = None
    content: str | None = None
    image_url: str | None = None
    image_urls: list[str] | None = None


class OwnerExpenseCreate(BaseModel):
    property_id: UUID
    amount: float
    spent_on: str
    note: str | None = None


class OwnerExpenseUpdate(BaseModel):
    amount: float | None = None
    spent_on: str | None = None
    note: str | None = None


class ComplaintCommentCreate(BaseModel):
    message: str


class EmergencyCreate(BaseModel):
    property_id: UUID
    raised_by: UUID
    alert_type: str
    description: str


class EmergencyUpdate(BaseModel):
    alert_type: str | None = None
    description: str | None = None
    status: str | None = None
