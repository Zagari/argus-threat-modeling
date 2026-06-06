# Ícones oficiais AWS / Azure

Os pacotes oficiais de ícones de arquitetura **exigem download manual** (aceite de
termos de uso), por isso não são versionados nem baixados automaticamente. Baixe-os
e aponte `fetch_icons.py` para o `.zip` (ou para a pasta já extraída).

## Onde baixar

- **AWS — "AWS Architecture Icons"**: https://aws.amazon.com/architecture/icons/
  Baixe o *Asset Package* (.zip). Contém ~739 ícones de serviço/recurso em SVG.
- **Azure — "Azure architecture icons"**:
  https://learn.microsoft.com/azure/architecture/icons/
  Baixe o `Azure_Public_Service_Icons_*.zip` (~705 SVGs).

## Como indexar

```bash
source training/.venv/bin/activate        # venv de dados
pip install cairosvg                       # + cairo nativo (brew install cairo / apt install libcairo2)

python training/icons/fetch_icons.py \
  --aws-zip   ~/Downloads/AWS-Architecture-Icons.zip \
  --azure-zip ~/Downloads/Azure_Public_Service_Icons.zip \
  --out data/icons --list-unmatched
```

Isso grava `data/icons/<classe_canonica>/<cloud>_<nome>.png` e um `manifest.json`.
O gerador (`synthetic/generate_synthetic.py --icons-dir data/icons`) passa a usar os
ícones reais; classes sem ícone caem no glifo primitivo.

## Estender a cobertura

`--list-unmatched` mostra os SVGs que não casaram com nenhuma classe. Para incluí-los,
acrescente palavras-chave em `training/taxonomy/mapeamento.yaml` (listas `aws:`/`azure:`)
e rode de novo. A pasta `data/icons/` é ignorada pelo git (ver `.gitignore`).
