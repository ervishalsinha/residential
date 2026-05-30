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


class OwnerPaymentSettingsUpdate(BaseModel):
    payment_upi_id: str | None = None
    payment_bank_account_number: str | None = None
    payment_bank_ifsc: str | None = None
    active_payment_method: str | None = None
