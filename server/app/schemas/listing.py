from typing import Literal

from pydantic import BaseModel, Field


class ListingIn(BaseModel):
    listing_type: Literal["sale", "rent"]
    project: str = Field(min_length=1, max_length=200)
    price: int | None = Field(default=None, ge=0, le=10_000_000_000)  # sale price or monthly rent
    deposit: int | None = Field(default=None, ge=0, le=10_000_000_000)
    bhk: int | None = Field(default=None, ge=1, le=10)
    area_sqft: int | None = Field(default=None, ge=1, le=1_000_000)
    location: str | None = Field(default=None, max_length=200)
    furnishing: str | None = Field(default=None, max_length=30)
    status: Literal["available", "held", "sold", "rented", "withdrawn"] = "available"
    rera_number: str | None = Field(default=None, max_length=100)
