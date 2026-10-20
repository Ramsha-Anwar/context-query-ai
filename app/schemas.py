from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field, ConfigDict, field_validator

class UserCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not any(c.isdigit() for c in v) or not any(c.isalpha() for c in v):
            raise ValueError("must contain at least one letter and one digit")
        if len(v.encode("utf-8")) > 72:
            raise ValueError("must be at most 72 bytes when encoded as UTF-8")
        return v

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int

class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    email: EmailStr
    role: str
    created_at: datetime

class ChangePasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not any(c.isdigit() for c in v) or not any(c.isalpha() for c in v):
            raise ValueError("must contain at least one letter and one digit")
        if len(v.encode("utf-8")) > 72:
            raise ValueError("must be at most 72 bytes when encoded as UTF-8")
        return v
# ... (keep existing schemas) ...

class DocumentSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    origin: str
    filename: str
    status: str
    chunk_count: int = 0

class HubResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    description: str | None
    ai_summary: str | None
    suggested_questions: list[str]
    document_count: int = 0
    chunk_count: int = 0
    created_at: datetime
    updated_at: datetime

class HubDetail(HubResponse):
    documents: list[DocumentSummary] = []  

class HubCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    content: str = Field(default="", max_length=20000)      
    documents: list[DocumentSummary] = []    

    