from pydantic import BaseModel, EmailStr, Field

from app.models.models import UserRole


class PasswordValidatedModel(BaseModel):
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(PasswordValidatedModel):
    email: EmailStr


class BootstrapRequest(PasswordValidatedModel):
    tenant_name: str
    tenant_slug: str
    email: EmailStr
    full_name: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = 'bearer'


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class ChangePasswordResponse(BaseModel):
    ok: bool = True
    message: str = 'Password updated'


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ForgotPasswordResponse(BaseModel):
    ok: bool = True
    message: str = (
        'If an account exists for that email, password reset instructions have been sent.'
    )
    reset_token: str | None = None


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=16, max_length=4096)
    new_password: str = Field(min_length=8, max_length=128)


class ResetPasswordResponse(BaseModel):
    ok: bool = True
    message: str = 'Password has been reset'


class UserResponse(BaseModel):
    id: str
    tenant_id: str
    email: EmailStr
    full_name: str
    role: UserRole
