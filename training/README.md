# `training/` — Dataset + Detector YOLO11 (Fase 1)

Pipeline da Fase 1 do ARGUS: **taxonomia canônica → ícones → dataset sintético
auto-rotulado → treino YOLO11 → publicação no HF Hub**. Fecha o requisito do
enunciado de *treinar um modelo supervisionado*. É o estágio **E1**; E2–E6 operam só
sobre as classes canônicas (agnóstico de nuvem).

## Dois ambientes (venvs separados)

| Tarefa | Python | Requirements | Onde |
|---|---|---|---|
| Gerar dataset / testes | 3.11–3.13 | `requirements.txt` (Pillow, PyYAML) | qualquer máquina |
| Treinar (torch/ultralytics) | **3.12** | `requirements-train.txt` | A5000 local **ou** Colab |

```bash
# venv de DADOS (leve — gera dataset, roda testes)
python3.13 -m venv training/.venv && source training/.venv/bin/activate
pip install -r training/requirements.txt

# venv de TREINO (pesado — só onde houver GPU)
python3.12 -m venv training/.venv-train && source training/.venv-train/bin/activate
pip install -r training/requirements-train.txt
```

## Fluxo

```bash
# 1) (opcional) ícones oficiais → PNGs reais por classe (senão usa glifos)
python training/icons/fetch_icons.py --aws-zip aws.zip --azure-zip azure.zip --out data/icons

# 2) dataset sintético auto-rotulado (~3–5k imgs)  [+ --icons-dir data/icons se houver]
python training/synthetic/generate_synthetic.py --n 3000 --out data/synthetic

# 3) sanidade (1 época) e depois treino completo (lê train_config.yaml)
python training/train_local.py --epochs 1 --quick      # smoke
python training/train_local.py                          # treino real (A5000)
#   …ou abra training/train_colab.ipynb no Colab (mesma config)

# 4) publicar o modelo
python training/publish_hf.py --weights training/runs/argus-detector/weights/best.pt \
       --repo SEU_USUARIO/argus-detector --metrics training/runs/argus-detector/metrics.json
```

## Componentes

- `taxonomy/mapeamento.yaml` — **fonte de verdade**: 21 classes canônicas com sinônimos
  de ícone (AWS/Azure), sinônimos de rótulo-texto (OCR), `dfd_type`, `stride`, `cpe_hints`.
  A ordem das classes define o índice YOLO. Em sincronia com `backend/app/taxonomy.py`.
- `taxonomy/loader.py` — carrega o YAML; casa nome-de-ícone e rótulo → classe.
- `synthetic/` — `glyphs.py` (glifos primitivos offline), `icon_bank.py` (ícone real ou
  glifo), `generate_synthetic.py` (compõe diagramas + emite labels YOLO + topologia GT
  + `data.yaml`).
- `icons/fetch_icons.py` — indexa os SVGs oficiais nas classes e rasteriza p/ PNG.
- `train_config.yaml` · `train_local.py` · `train_colab.ipynb` — treino espelhado.
- `publish_hf.py` — sobe `best.pt` + Model Card.
- `tests/test_dataset.py` — sanidade (formato YOLO, `data.yaml` coerente, sem vazamento
  entre splits). Roda no venv de dados, **sem** ultralytics.

```bash
source training/.venv/bin/activate && python -m pytest training/tests/ -q
```

## Notas

- `data/synthetic/`, `data/icons/`, `training/runs/` e `*.pt` são ignorados pelo git
  (reproduzíveis / vão p/ o HF Hub). Os 2 diagramas do enunciado ficam em `data/gold/`
  e **nunca** entram no treino — só no teste/avaliação.
- Sem os ícones oficiais o detector aprende **formas** (glifos); com eles, fica
  realista. O pipeline é idêntico nos dois casos.
