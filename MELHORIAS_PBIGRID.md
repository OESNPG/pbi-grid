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

## Sobreposição atrás do visual: `behind` (overlay)

`behind: true` numa sobreposição desenha o visual **atrás** do visual-base (z da célula − 20, acima
só da moldura), em vez de por cima. Assim ele não bloqueia cliques nem dicas do gráfico. Uso típico:
mensagem de "sem dados" que só aparece quando o gráfico (com fundo transparente) fica vazio.

```yaml
- span: 4
  name: f1caae20811b9d0a7c43        # gráfico com fundo transparente
  overlay:
  - name: a5a0f1caae20811b9d0a      # card com a medida do aviso (em branco quando há dados)
    behind: true
    width: 512
    height: 60
    offset_y: 16
```

Usado nos avisos de k-anonimização do painel de egressos (outubro/2026).

## Altura das páginas de info mais justa (`info_table._text_lines` + tema capes)

A altura da página-tooltip do ⓘ é estimada pelo tamanho do texto. Antes, as marcações HTML (`<b>`, `<br>`)
contavam como texto, as quebras de parágrafo não contavam e o tema `capes` ainda multiplicava por 1,5: as infos
longas sobravam com ~150 px em branco. Agora a contagem usa só o texto visível, soma as linhas de cada parágrafo
(cada `<br>` quebra a linha; `<br><br>` deixa uma em branco), com caracteres por linha calibrados no Power BI
(0,48 × fonte ≈ 44 letras em 230 px) e margem fixa de 16 px; o `content_scale` do tema `capes` caiu para 1,0 e o visual HTML da página
ficou sem o espaçamento interno do contêiner (padding 0). Uma primeira versão, mais justa, deixou barra de rolagem nas
infos curtas: a dica do Power BI não rola, então errar para mais é o lado seguro. Nas 46 infos de egressos, a altura
total caiu ~34% (ex.: mapa da Visão Geral, 546 → 351 px). Novembro/2026.

## Preservar o que veio do Desktop: grupos e ajuste de exibição da página

- **Grupos (`keep_unlisted_visuals`):** o visual que o layout não lista é copiado como está, mas o `to_dict`
  tirava o `parentGroupName` de todos os visuais. Um filho de grupo tem a posição **relativa ao grupo**; sem o
  vínculo, ele ia parar no canto da página. Agora o visual preservado (`Visual.keep_group`) continua no grupo; só
  o visual reposicionado pela grade sai dele, como antes.
- **`displayOption` da página:** o generate gravava sempre `FitToPage`, e era preciso devolver o `page.json`
  original à mão (as abas dos painéis são `FitToWidth`). Agora a página que já existe mantém o ajuste salvo no
  Desktop; só a página nova usa o padrão.

Testes em `tests/unit/test_preserva_desktop.py`. Encontrado ao sincronizar o painel de temas estratégicos
(grupo com o mapa da aba Temas Estratégicos). Novembro/2026.
- **Espaçador `empty_row`:** a coluna/linha de espaço (`name: empty_row`) virava uma caixa de texto vazia com esse
  nome, uma por aba (as repetidas se sobrescreviam). Em temas ela ficou por cima de 4 a 8 px do rodapé, que tem link.
  Agora o espaçador só ocupa lugar na grade, sem visual. As caixas que já existiam em egressos e temas foram retiradas.
