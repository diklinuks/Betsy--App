"""Structured output for Betsy's reorder decision (rich rationale: why + alternatives
+ confidence — per the rationale-storage decision)."""
from __future__ import annotations

from pydantic import BaseModel, Field


class Proposal(BaseModel):
    chosen_supplier_id: str = Field(description="supplier_id Betsy recommends")
    quantity: int = Field(description="order quantity (respect MOQ)")
    reasoning: str = Field(description="why this supplier+quantity, weighing price vs lead time vs reliability vs urgency")
    alternatives: list[str] = Field(default_factory=list, description="other supplier_ids considered and why they lost")
    confidence: float = Field(ge=0.0, le=1.0, description="0-1 confidence in this choice")
    escalate: bool = Field(default=False, description="True to ask Jenny even if under the cap (unusual/high-risk case)")
