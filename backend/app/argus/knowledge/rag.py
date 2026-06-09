"""RAG semântico (Chroma + sentence-transformers) — OPCIONAL e GRACIOSO.

Indexa as entidades do `KnowledgeStore` (embeddings LOCAIS, modelo multilíngue PT↔EN) e devolve
os mais relevantes a uma consulta. É um **realce de recall** sobre o determinístico: sem as libs
ou sem `ARGUS_RAG=1`, `ready()` é False e quem chama cai no caminho determinístico/substring.

O índice é construído UMA vez (em background, no startup — ver main.py) e persiste num diretório
(volume em produção). Reinícios apenas carregam. Imports pesados são preguiçosos (não entram no CI).
"""

from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Any

from app.argus.knowledge.store import get_store

_ENABLED = os.getenv("ARGUS_RAG", "0") == "1"
_MODEL_NAME = os.getenv("ARGUS_EMBED_MODEL", "paraphrase-multilingual-MiniLM-L12-v2")
_PERSIST = os.getenv("ARGUS_CHROMA_DIR", str(Path(__file__).resolve().parents[4] / "chroma"))
_COLLECTION = "kg"

_lock = threading.Lock()
_status = "off"          # off | indexando | pronto | erro
_error = ""
_model: Any = None
_collection: Any = None


def enabled() -> bool:
    return _ENABLED


def ready() -> bool:
    return _status == "pronto"


def status() -> dict:
    return {"status": _status, "model": _MODEL_NAME if _ENABLED else None, "error": _error or None}


def warm() -> None:
    """Carrega (ou constrói) o índice + modelo. Idempotente; chamado em background no startup."""
    global _status, _error, _model, _collection
    if not _ENABLED:
        return
    with _lock:
        if _status in ("pronto", "indexando"):
            return
        _status = "indexando"
    try:
        import chromadb
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer(_MODEL_NAME)
        client = chromadb.PersistentClient(path=_PERSIST)
        col = client.get_or_create_collection(_COLLECTION, metadata={"hnsw:space": "cosine"})
        if col.count() == 0:
            _build(col)
        _collection = col
        with _lock:
            _status = "pronto"
    except Exception as e:  # noqa: BLE001 — RAG é opcional; falha vira fallback, não derruba o app
        with _lock:
            _status, _error = "erro", str(e)


def _build(col: Any) -> None:
    ids, docs, metas = [], [], []
    for e in get_store().iter_entities():
        if e.kind == "Stride":
            continue
        ids.append(f"{e.kind}:{e.id}")
        docs.append(f"{e.id} {e.name} {e.text}".strip())
        metas.append({"kind": e.kind, "rid": e.id, "name": e.name, "url": e.url or ""})
    embs = _model.encode(docs, batch_size=64, normalize_embeddings=True, show_progress_bar=False).tolist()
    chunk = 2000
    for i in range(0, len(ids), chunk):
        col.add(ids=ids[i : i + chunk], documents=docs[i : i + chunk],
                metadatas=metas[i : i + chunk], embeddings=embs[i : i + chunk])


def search(query: str, *, kind: str | None = None, k: int = 8) -> list[dict]:
    """Top-K entidades por similaridade semântica (com `score`). [] se o índice não está pronto."""
    if not ready() or _collection is None or _model is None or not query.strip():
        return []
    try:
        qemb = _model.encode([query], normalize_embeddings=True).tolist()
        where = {"kind": kind} if kind else None
        res = _collection.query(query_embeddings=qemb, n_results=k, where=where)
        out: list[dict] = []
        for i in range(len(res["ids"][0])):
            m = res["metadatas"][0][i]
            dist = res["distances"][0][i]
            out.append({"id": m["rid"], "kind": m["kind"], "name": m.get("name", ""),
                        "url": m.get("url") or None, "score": round(1 - float(dist), 3)})
        return out
    except Exception:  # noqa: BLE001
        return []
