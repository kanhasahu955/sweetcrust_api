from typing import Any, Optional

from pydantic import EmailStr, Field

from package.common.schemas import APIModel


class SendOTPIn(APIModel):
    phone: str = Field(..., min_length=10, max_length=20)
    purpose: str = "login"
    email: Optional[EmailStr] = None


class VerifyOTPIn(APIModel):
    phone: str = Field(..., min_length=10, max_length=20)
    code: str = Field(..., min_length=4, max_length=10)
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    terms_accepted: bool = True


class GoogleLoginIn(APIModel):
    id_token: str
    terms_accepted: bool = True


class AdminLoginIn(APIModel):
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    password: str


class AdminRegisterIn(APIModel):
    name: str = Field(..., min_length=2, max_length=120)
    phone: str = Field(..., min_length=10, max_length=15)
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=128)


class AdminConfirmEmailIn(APIModel):
    email: EmailStr
    code: str = Field(..., min_length=4, max_length=10)


class AdminResendConfirmIn(APIModel):
    email: EmailStr


class AdminOTPLoginIn(APIModel):
    phone: str
    code: str


class DeliveryLoginIn(APIModel):
    phone: str
    password: Optional[str] = None
    code: Optional[str] = None


class RetailerLoginIn(APIModel):
    phone: str
    password: Optional[str] = None
    code: Optional[str] = None


class RetailerOtpVerifyIn(APIModel):
    phone: str = Field(..., min_length=10, max_length=15)
    code: str = Field(..., min_length=4, max_length=10)
    name: Optional[str] = None
    terms_accepted: bool = True


class RetailerGoogleIn(APIModel):
    id_token: str
    terms_accepted: bool = True


class RetailerGoogleFinishIn(APIModel):
    code: str


class ForgotPasswordIn(APIModel):
    phone: str


class ResetPasswordIn(APIModel):
    phone: str
    code: str
    new_password: str = Field(..., min_length=6)


class RefreshIn(APIModel):
    refresh_token: str


class LogoutIn(APIModel):
    refresh_token: Optional[str] = None


class GuestIn(APIModel):
    device_id: Optional[str] = None


class ProfileUpdateIn(APIModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    language: Optional[str] = None
    avatar_url: Optional[str] = None


class RetailerUploadBase64In(APIModel):
    purpose: str = "kyc"
    filename: str = "photo.jpg"
    content_base64: str = Field(..., min_length=8)
    content_type: str = "image/jpeg"


class MessageOut(APIModel):
    message: str


class TokenOut(APIModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: Optional[dict[str, Any]] = None
    message: Optional[str] = None
    approval_status: Optional[str] = None
    is_new: Optional[bool] = None
