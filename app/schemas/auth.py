from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(default="", max_length=120)
    password: str = Field(min_length=12, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    email: EmailStr
    full_name: str
    role: str
    is_active: bool


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class ReviewHistoryItem(BaseModel):
    review_id: str
    review_type: str
    filename: str
    repository: str
    score: int | None
    summary: str
    created_at: str


class RepositoryCreate(BaseModel):
    owner: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9-]+$")
    name: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_.-]+$")
    default_branch: str = Field(default="main", min_length=1, max_length=120)


class RepositoryResponse(BaseModel):
    id: int
    owner: str
    name: str
    default_branch: str
    created_at: str
    url: str


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=12, max_length=128)
