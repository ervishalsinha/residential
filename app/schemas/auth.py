from pydantic import BaseModel



class RegisterRequest(BaseModel):
    full_name: str
    mobile_number: str
    email: str | None = None
    password: str
    role: str = "property_admin"

class LoginRequest(BaseModel):
    mobile_number: str
    password: str


class OTPRequest(BaseModel):
    mobile_number: str


class OTPVerifyRequest(BaseModel):
    mobile_number: str
    otp: str
    role: str | None = None


class ForgotPasswordRequest(BaseModel):
    mobile_number: str


class ResetPasswordRequest(BaseModel):
    mobile_number: str
    otp: str
    new_password: str


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    role: str


class AuthenticatedUser(BaseModel):
    id: str
    full_name: str
    mobile_number: str
    role: str
    payment_upi_id: str | None = None
    payment_bank_account_number: str | None = None
    payment_bank_ifsc: str | None = None
    active_payment_method: str | None = None
    razorpay_linked_account_id: str | None = None
    razorpay_linked_account_status: str | None = None


class OwnerPaymentSettingsUpdate(BaseModel):
    payment_upi_id: str | None = None
    payment_bank_account_number: str | None = None
    payment_bank_ifsc: str | None = None
    active_payment_method: str | None = None
    razorpay_linked_account_id: str | None = None


class OwnerLinkedAccountSyncRequest(BaseModel):
    legal_business_name: str | None = None
    business_type: str = "individual"
    contact_name: str | None = None
    email: str | None = None
    phone: str | None = None
    profile_category: str = "services"
    profile_subcategory: str = "consulting"
    street1: str | None = None
    street2: str | None = None
    city: str | None = None
    state: str | None = None
    postal_code: str | None = None
    country: str = "IN"


class OwnerLinkedAccountStatusResponse(BaseModel):
    razorpay_linked_account_id: str | None = None
    razorpay_linked_account_status: str | None = None
    route_linked_account_badge: str
