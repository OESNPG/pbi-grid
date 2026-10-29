# pbi-grid — limitações e melhorias (round-trip de relatórios maduros)

Contexto: adaptar um relatório **já construído e ajustado à mão** (`temas_estrategicos_stg`,
4 páginas, ~150 visuais + 30 tooltips) ao formato do pbi-grid, **sem perdas** e sem
embaralhar posições. O `generate` puro não dava conta disso — exigia um layout com
âncoras absolutas e um script de pós-processamento. As melhorias abaixo movem essa
lógica para dentro do próprio engine, todas **opt-in** (default = comportamento antigo).

---

## Limitações identificadas

1. **`generate` descarta o que não está no layout.** Cada página é reconstruída só
   com os visuais descritos no YAML; qualquer visual do source ausente do layout
   **some**. Num relatório maduro, o layout raramente descreve os ~150 visuais.

2. **Páginas fora do layout somem do `pages.json`.** O `build` só emite as páginas
   listadas + as tooltips geradas por `info_icon`. As 30 tooltips hand-made do
   relatório desapareciam (só voltavam via restauração manual do `pages.json`).

3. **Não há posição absoluta.** A grade não reproduz posições em pixel; só linhas/
   colunas + `offset` de overlay. Reproduzir um layout ajustado à mão obrigava a
   truque de "overlay-âncora" com offsets calculados.

4. **Toda coluna emite um visual-base.** Não existia coluna "só de overlays", então
   o truque de âncora deixava um placeholder que precisava ser removido depois.

5. **`visualInteractions` penduradas quebram o render.** O `build` preserva as
   interações da página vindas do source, mas ao trocar o conjunto de visuais sobra
   referência a visual inexistente → erro "Cannot read properties of undefined".

6. **Altura da página não acompanha o conteúdo.** Fica na altura do source/canvas e
   corta conteúdo mais baixo; não havia auto-fit.

7. **`pbi_grid_config.tmdl` é sempre sobrescrito.** Bastava 1 `info_icon` para o
   `generate` reescrever a tabela e quebrar as 32 colunas de um config mantido à mão.

---

## Melhorias implementadas (opt-in)

Novo bloco **`options:`** no topo do layout + um campo de coluna `overlay_only`.
Todas default `false` — sem ligar nada, o pbi-grid se comporta como antes.

| Limitação | Melhoria | Como liga |
|-----------|----------|-----------|
| 1 | `keep_unlisted_visuals` — carrega os visuais do source ausentes do layout, **na posição original** (raw_data verbatim). Dispensa âncoras. | `options.keep_unlisted_visuals: true` |
| 2 | `keep_unlisted_pages` — preserva páginas do source ausentes no layout (tooltips), verbatim. | `options.keep_unlisted_pages: true` |
| 4 | `overlay_only` — coluna que **não** emite visual-base, só seus overlays (âncora pura, sem placeholder). | `overlay_only: true` na coluna |
| 5 | `prune_interactions` — remove `visualInteractions` cuja origem/destino não existe na página. | `options.prune_interactions: true` |
| 6 | `fit_page_height` — ajusta a altura de cada página (não-tooltip) para caber o conteúdo (+ `fit_page_margin`, default 24). | `options.fit_page_height: true` |
| 7 | `preserve_config_table` — não sobrescreve o `pbi_grid_config.tmdl` se ele já existir no SemanticModel. | `options.preserve_config_table: true` |

### Exemplo de bloco `options:`

```yaml
options:
  keep_unlisted_visuals: true    # reconciliação sem perdas nativa
  keep_unlisted_pages: true      # preserva tooltips ocultas
  prune_interactions: true       # limpa interações penduradas
  fit_page_height: true          # altura acompanha o conteúdo
  fit_page_margin: 24
  preserve_config_table: true    # não quebra o config de 32 colunas
```

### Arquivos alterados

- `src/grid/schema.py` — campos em `LayoutSpec` (bloco `options`) e `ColSpec.overlay_only`.
- `src/grid/engine.py` — `_render_col` (overlay_only); `build` (keep_unlisted_visuals,
  keep_unlisted_pages, prune_interactions, fit_page_height).
- `src/grid/renderer.py` — `render(..., preserve_config_table=False)` + `_config_table_exists`.
- `src/cli.py` — passa `preserve_config_table` ao `render`.

---

## Resultado do teste (temas_estrategicos_stg)

Layout **sem âncoras** (versão do último commit) + só o bloco `options:` acima,
compilado com o `build` (em memória):

| Página | Visuais originais | Presentes | Duplicatas | Perdas | Altura ajustada |
|--------|-------------------|-----------|------------|--------|-----------------|
| Visão Geral | 45 | 45 | 0 | 0 | 1352 |
| Macrotemas | 31 | 31 | 0 | 0 | 1928 |
| Temas Estratégicos | 47 | 47 | 0 | 0 | 1784 |
| Capacidade Instalada | 23 | 23 | 0 | 0 | 2221 |

- 32 tooltips do source → **32 preservadas**.
- Interações penduradas restantes: **0**.

Ou seja: o bloco `options:` de 6 linhas substitui as linhas-âncora + todo o
`post_generate_fix.py` (remoção de placeholder, restauração de tooltips, limpeza de
interações e ajuste de altura). Sobra só o `generate` + reabrir o `.pbip`.

### Como testar

```bash
cd /Users/vanessaborges/dev_repo/pbi-grid
.venv/bin/python -m src.cli generate \
  --layout /Users/vanessaborges/dev_repo/pbi_agenda/analytics/pbi_grid/temas_estrategicos_stg.yaml \
  --output /Users/vanessaborges/dev_repo/pbi_agenda/analytics/power_bi/temas_estrategicos
```
(com o layout usando o bloco `options:` e **sem** as linhas-âncora)

### Como reverter as mudanças de código

As alterações estão **não commitadas** no repo do pbi-grid. Para descartar:
```bash
cd /Users/vanessaborges/dev_repo/pbi-grid && git checkout -- src/
```

---

## Ressalvas

- `preserve_config_table` foi implementado mas **não testado em disco** aqui (o
  teste foi só do `build` em memória; ele atua no `render`). Vale um teste real.
- `keep_unlisted_visuals` acopla o layout ao código: se as opções forem ignoradas
  (código revertido) e as âncoras removidas, há perda. Manter os dois juntos.
- `empty_row` repetido colapsa em um só diretório (visual sem conteúdo) — comportamento
  pré-existente, sem impacto visual.
- Migração das tooltips para `info_icon` nativo **não** foi feita (decisão sua) — por
  isso `preserve_config_table` em vez de reconstruir a tabela.

---

## Painéis com moldura: `backdrop` e `border_radius` (coluna)

Para desenhar uma moldura que envolve título + cards (várias linhas) sem empurrar os visuais:

```yaml
- id: painel
  height: 0                 # linha "vazia" só para ancorar a moldura
  cols:
  - span: 12
    name: empty_row
    overlay_only: true      # sem visual-base
    border: true
    border_color: '#C5D4EB'
    border_radius: 8        # cantos arredondados só desta borda (default: token layout.border_radius)
    backdrop: true          # rowspan SEM bloquear as linhas seguintes
    rowspan: 4              # esta linha + título + cards + respiro
- id: painel_titulo   # ... visuais normais por cima da moldura
```

`backdrop` só muda o `rowspan_carry` (não reserva espaço); a forma da borda fica com z menor que as
linhas seguintes, então fica atrás. Usado na Visão Geral de `egressos` (outubro/2026).
