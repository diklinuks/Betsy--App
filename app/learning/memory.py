"""Semantic memory (S11, pgvector): embed decision rationale + lessons, recall by meaning.

This is the R6/R7 retrieval path that feeds Betsy's learning loop (Learning.md).
"""
from __future__ import annotations

from sqlalchemy import select

from app.agent.model import get_embeddings
from app.config.settings import RETRIEVAL_TOP_K
from app.db.models import MemoryEmbedding


def embed_memory(session, *, kind: str, text: str, decision_id: str | None = None,
                 supplier_id: str | None = None, product_id: str | None = None,
                 created_day: int = 0) -> None:
    """Embed a piece of memory and store it (W10). kind: rationale|reflection|rejection."""
    if not text or not text.strip():
        return
    vector = get_embeddings().embed_query(text)
    session.add(MemoryEmbedding(
        kind=kind, decision_id=decision_id, supplier_id=supplier_id,
        product_id=product_id, created_day=created_day, text=text, embedding=vector,
    ))
    session.flush()


def semantic_search(session, query: str, k: int = RETRIEVAL_TOP_K) -> list[dict]:
    """Return the k most similar past memories (cosine distance) to `query`."""
    qvec = get_embeddings().embed_query(query)
    rows = session.execute(
        select(
            MemoryEmbedding,
            MemoryEmbedding.embedding.cosine_distance(qvec).label("dist"),
        )
        .order_by("dist")
        .limit(k)
    ).all()
    return [
        {
            "kind": m.kind, "text": m.text, "decision_id": m.decision_id,
            "supplier_id": m.supplier_id, "product_id": m.product_id,
            "similarity": round(1.0 - float(dist), 3),
        }
        for m, dist in rows
    ]
