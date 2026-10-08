from datetime import date

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.core.config import settings


class RecipientInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(..., min_length=1)
    email: EmailStr

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("recipient name must not be empty")
        return cleaned

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return value.strip().lower()


class GenerationJobCreateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    event_name: str = Field(..., min_length=1)
    certificate_title: str = Field(..., min_length=1)
    completion_date: date
    recipients: list[RecipientInput]

    @field_validator("event_name", "certificate_title")
    @classmethod
    def validate_required_text(cls, value: str, info):
        cleaned = value.strip()
        if not cleaned:
            raise ValueError(f"{info.field_name} must not be empty")
        return cleaned

    @model_validator(mode="after")
    def validate_batch(self):
        if not self.recipients:
            raise ValueError("recipients must contain at least 1 recipient")
        if len(self.recipients) > settings.MAX_BATCH_SIZE:
            raise ValueError(f"recipients exceeds the maximum allowed batch size of {settings.MAX_BATCH_SIZE}")
        seen = set()
        for recipient in self.recipients:
            if recipient.email.lower() in seen:
                raise ValueError("duplicate recipient emails are not allowed in the same request")
            seen.add(recipient.email.lower())
        return self


class GenerationJobCreateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    job_id: str
    status: str
    total_count: int
    message: str = "Certificate generation job accepted"


class GenerationJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    job_id: str
    status: str
    progress: dict
    created_at: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    error_message: str | None = None
