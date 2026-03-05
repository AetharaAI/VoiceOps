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


class UserResponse(BaseModel):
    id: str
    tenant_id: str
    email: EmailStr
    full_name: str
    role: UserRole
