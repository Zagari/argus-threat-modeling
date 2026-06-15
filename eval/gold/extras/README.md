# `eval/gold/extras/` — diagramas extras (imagens do usuário)

Diagramas **adicionais** trazidos pelo usuário para ampliar o gold set/julgamento (Opção A).

**Convenção:**
1. O usuário deixa aqui as **imagens** (`.png`/`.jpg`) dos diagramas de arquitetura.
2. Para cada imagem `<nome>.<ext>`, a **GT neutra** é autorada **lendo a imagem** e salva ao lado como
   `<nome>.gt.json` (mesmo formato das `eval/gold/*.gt.json`: `components` em classes canônicas +
   `edges` com `crosses_boundary`). O usuário **revisa** a GT.
3. O harness (`run_comparison.py --images "eval/gold/extras/*"`) e o juiz (`run_judge.py`, que acha a
   `<nome>.gt.json`) processam estes diagramas como os demais.

As **imagens** (`*.png`/`*.jpg`) ficam fora do git (regeneráveis/pesadas); a **GT** (`*.gt.json`) é
versionada.
