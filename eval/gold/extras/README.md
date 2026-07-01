# `eval/gold/extras/` — diagramas extras (imagens do usuário)

Diagramas **adicionais** trazidos pelo usuário para ampliar o gold set/julgamento (Opção A).

**Convenção:**
1. O usuário deixa aqui as **imagens** (`.png`/`.jpg`) dos diagramas de arquitetura (slug limpo, sem
   espaços — facilita o glob). Imagens são gitignored.
2. Para cada imagem `<slug>.<ext>`, a **GT neutra** é autorada **lendo a imagem** (mesmo formato das
   `eval/gold/*.gt.json`: `components` em classes canônicas + `edges` com `crosses_boundary`). O usuário
   **revisa** a GT. ⚠️ A GT é salva **FLAT em `eval/gold/<slug>.gt.json`** (NÃO dentro de `extras/`),
   porque o juiz busca a GT em `eval/gold/<stem>.gt.json` (ver `run_judge.py:64`), onde `stem` = nome
   da imagem sem extensão (ver `harness.py:67`). A GT é versionada; a imagem não.
3. O harness (`run_comparison.py --images "eval/gold/extras/*"`) e o juiz (`run_judge.py`, que casa a
   GT pelo stem) processam estes diagramas como os demais.

As **imagens** (`*.png`/`*.jpg`) ficam fora do git (regeneráveis/pesadas); a **GT** (`*.gt.json`) é
versionada.
