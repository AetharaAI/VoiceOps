from pydantic import BaseModel, EmailStr

from app.models.models import UserRole


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class BootstrapRequest(BaseModel):
    tenant_name: str
    tenant_slug: str
    email: EmailStr
    full_name: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = 'bearer'


class UserResponse(BaseModel):
    id: str
    tenant_id: str
    email: EmailStr
    full_name: str
    role: UserRole
