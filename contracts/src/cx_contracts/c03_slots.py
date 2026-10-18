"""C3: Onboarding slot contract v0.4."""
from __future__ import annotations
from decimal import Decimal
from enum import Enum
from pydantic import BaseModel, Field, model_validator


class PriceType(str, Enum):
    fixed = "fixed"
    from_ = "from"
    range_ = "range"
    quote = "quote"


class AddressVisibility(str, Enum):
    public = "public"
    private = "private"
    service_area = "service_area"


class Address(BaseModel):
    street: str | None = None
    city: str | None = None
    state: str | None = None
    zip_code: str | None = None
    country: str = "US"
    visibility: AddressVisibility = AddressVisibility.public


class ServiceHours(BaseModel):
    """Open intervals per day. E.g. {"monday": [["09:00","17:00"]]}"""
    monday: list[list[str]] = Field(default_factory=list)
    tuesday: list[list[str]] = Field(default_factory=list)
    wednesday: list[list[str]] = Field(default_factory=list)
    thursday: list[list[str]] = Field(default_factory=list)
    friday: list[list[str]] = Field(default_factory=list)
    saturday: list[list[str]] = Field(default_factory=list)
    sunday: list[list[str]] = Field(default_factory=list)
    exceptions: dict[str, list[list[str]]] = Field(default_factory=dict)


class Service(BaseModel):
    name: str
    category: str | None = None
    price_type: PriceType = PriceType.fixed
    price_min: Decimal | None = None
    price_max: Decimal | None = None
    duration_minutes: int | None = None
    add_ons: list[str] = Field(default_factory=list)
    deposit: Decimal | None = None
    description: str | None = None

    @model_validator(mode="after")
    def validate_range(self) -> "Service":
        if self.price_type == PriceType.range_ and (
            self.price_min is None or self.price_max is None
        ):
            raise ValueError("range price_type requires price_min and price_max")
        return self


class OnboardingSlots(BaseModel):
    # Required
    business_name: str | None = None
    vertical: str | None = None
    owner_name: str | None = None
    owner_mobile: str | None = None
    services: list[Service] = Field(default_factory=list)
    hours: ServiceHours | None = None
    timezone: str | None = None
    greeting_tone: str | None = None
    # Optional
    address: Address | None = None
    email: str | None = None
    languages: list[str] = Field(default_factory=lambda: ["en"])
    escalation_number: str | None = None
    staff: list[str] = Field(default_factory=list)
    booking_rules: str | None = None
    cancellation_policy: str | None = None
    payment_methods: list[str] = Field(default_factory=list)
    calendar_provider: str | None = None
    website: str | None = None
    socials: dict[str, str] = Field(default_factory=dict)

    def is_complete(self) -> bool:
        return all([
            self.business_name, self.vertical, self.owner_name,
            self.owner_mobile, len(self.services) > 0,
            self.hours is not None, self.timezone, self.greeting_tone,
        ])
