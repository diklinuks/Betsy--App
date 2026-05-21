"""Structured output for Betsy's reorder decision (rich rationale: why + alternatives
+ confidence — per the rationale-storage decision)."""
from __future__ import annotations

from pydantic import BaseModel, Field


class Proposal(BaseModel):
    chosen_supplier_id: str = Field(description="supplier_id Betsy recommends")
    quantity: int = Field(description="order quantity (respect MOQ)")
    reasoning: str = Field(description="2-4 sentences: the situation (stock vs reorder point, urgency), the supplier chosen with its price/lead/reliability and the order quantity, and WHY it was preferred over the next-best supplier (name that supplier and its numbers). Weigh price vs lead time vs reliability vs urgency. Use concrete numbers.")
    alternatives: list[str] = Field(default_factory=list, description="other supplier_ids considered and why they lost")
    confidence: float = Field(ge=0.0, le=1.0, description="0-1 confidence in this choice")
    escalate: bool = Field(default=False, description="True to ask Jenny even if under the cap (unusual/high-risk case)")
