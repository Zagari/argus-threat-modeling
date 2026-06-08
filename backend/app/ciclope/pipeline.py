"""Cíclope — o baseline LLM-only (o "olho único").

A imagem do diagrama vai DIRETO a um VLM, que numa única passagem extrai
componentes, conexões e ameaças STRIDE no mesmo `ThreatModel` do ARGUS.
É o melhor baseline possível (prompt sofisticado + structured output), para
uma comparação justa — não uma versão enfraquecida.
"""

from __future__ import annotations

import time
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.argus import scoring
from app.config import get_config
from app.llm import provider
from app.llm.mock import mock_threat_model
from app.schemas import ThreatModel
from app.taxonomy import CANONICAL_CLASSES

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "llm" / "prompts"
_env = Environment(loader=FileSystemLoader(_PROMPTS_DIR), autoescape=select_autoescape(disabled_extensions=("j2",)))

SYSTEM_PROMPT = (
    "Você é um especialista em segurança de software com mais de 20 anos de experiência "
    "aplicando a metodologia STRIDE de modelagem de ameaças a arquiteturas de sistemas. "
    "Você lê diagramas de arquitetura (de qualquer nuvem) e produz modelos de ameaças "
    "precisos, específicos e acionáveis. Responda sempre em português."
)


def analyze(image_bytes: bytes, *, system_name: str | None = None, mime: str = "image/jpeg") -> ThreatModel:
    cfg = get_config()

    if cfg.mock:
        mock_tm = mock_threat_model(system_name or "Sistema (mock)", provenance="ciclope")
        mock_tm.meta.update({
            "provider": "mock", "model": "mock", "latency_s": 0.0,
            "usage": {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0,
                      "total_tokens": 0, "cost_usd": 0.0, "cost_known": False, "mock": True},
        })
        scoring.apply(mock_tm.threats)
        mock_tm.meta["dread_dist"] = scoring.distribution(mock_tm.threats)
        return mock_tm

    prompt = _env.get_template("ciclope.j2").render(canonical_classes=CANONICAL_CLASSES)

    t0 = time.perf_counter()
    with provider.meter() as usage:
        tm: ThreatModel = provider.vision(  # type: ignore[assignment]
            image_bytes,
            prompt,
            response_model=ThreatModel,
            mime=mime,
            system=SYSTEM_PROMPT,
        )
    latency = round(time.perf_counter() - t0, 3)

    # Garante a proveniência e registra metadados de execução.
    for threat in tm.threats:
        threat.provenance = "ciclope"
    if system_name:
        tm.system_name = system_name
    tm.meta.update(
        {
            "provider": cfg.provider,
            "model": cfg.model,
            "latency_s": latency,
            "system": "ciclope",
            "usage": usage.snapshot(),
        }
    )
    scoring.apply(tm.threats)
    tm.meta["dread_dist"] = scoring.distribution(tm.threats)
    return tm
