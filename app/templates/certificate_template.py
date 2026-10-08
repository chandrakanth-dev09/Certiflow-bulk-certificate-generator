from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TemplateSettings:
    organization_name: str = "Certified Organization"
    title: str = "Certificate of Completion"
    accent_color: str = "#0F172A"


class CertificateTemplateService:
    def __init__(self, settings: TemplateSettings | None = None):
        self.settings = settings or TemplateSettings()

    def render(self, recipient_name: str, course: str, certificate_number: str, verification_url: str) -> dict:
        return {
            "organization_name": self.settings.organization_name,
            "title": self.settings.title,
            "recipient_name": recipient_name,
            "course": course,
            "certificate_number": certificate_number,
            "verification_url": verification_url,
        }
