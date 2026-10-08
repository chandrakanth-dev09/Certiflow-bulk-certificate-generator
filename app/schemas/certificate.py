from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class CertificateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    job_id: str
    recipient_name: str
    recipient_email: str
    certificate_title: str
    event_name: str
    completion_date: date
    certificate_number: str
    status: str
    file_path: str | None = None
    failure_reason: str | None = None
    created_at: datetime
    generated_at: datetime | None = None


class CertificateVerifyResult(BaseModel):
    valid: bool
    certificate_number: str | None = None
    recipient_name: str | None = None
    event_name: str | None = None
    completion_date: date | None = None
    status: str | None = None
