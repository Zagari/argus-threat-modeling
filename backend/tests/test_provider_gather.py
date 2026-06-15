"""provider.gather: roda thunks em paralelo com contexto (meter) propagado e thread-safe; falha→None."""

from __future__ import annotations

from app.llm import provider


def test_gather_ordem_e_falha_vira_none() -> None:
    def boom() -> int:
        raise RuntimeError("falhou")

    assert provider.gather([lambda: 1, lambda: 2, lambda: 3]) == [1, 2, 3]      # resultados na ordem
    assert provider.gather([lambda: 10, boom, lambda: 30]) == [10, None, 30]     # falha de um → None


def test_gather_propaga_meter_e_e_thread_safe() -> None:
    with provider.meter() as m:
        # cada thunk (em sua thread) enxerga o MESMO medidor → contexto propagado
        seen = provider.gather([lambda: provider._meter.get() for _ in range(8)], max_workers=4)
        assert all(s is m for s in seen)
        # 60 somas concorrentes no mesmo medidor não dão race (lock no UsageMeter.add)
        provider.gather(
            [lambda: m.add(prompt=1, completion=1, total=2, cost=0.0, cost_known=False) for _ in range(60)],
            max_workers=8,
        )
    assert m.calls == 60 and m.prompt_tokens == 60 and m.total_tokens == 120
