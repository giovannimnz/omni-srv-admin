# Atius SSO — UI Review histórico pré-fix

**Captura:** 2026-07-31 07:38:49–07:39:01 BRT  
**Delegação:** `deleg_115bbf83`  
**Viewport:** `1440x900`, DPR `1`  
**Baseline:** referência live `https://sso.atius.com.br/login` + padrões abstratos GSD  
**Classificação:** `HISTORICAL_PRE_FIX_UI_REVIEW_RECONSTRUCTED_POST_TIMEOUT_SUPERSEDED_BY_VISUAL_V2`

## Limite de autoria

O subagente capturou os seis `/login`, computed styles, probes semânticos, contact sheet e pixel metrics. Ele terminou por timeout antes de emitir score ou summary.

A pontuação abaixo foi reconstruída no closeout a partir dos raw artifacts. Não é um verdict emitido pelo subagente.

## Pillar Scores

| Pilar | Score | Finding histórico |
|---|---:|---|
| Copywriting | 4/4 | `Atius SSO`, `DESTINO SEGURO`, `Email ou username`, `Senha` e `Entrar com Atius SSO` estavam coerentes; hostname específico nos alvos era conteúdo contextual esperado. |
| Visuals | 2/4 | Hierarquia reconhecível, mas admin-edge/AdGuard usavam card `482px` vs `454.25px` e logo `72px` vs `44px`, alterando escala e foco. |
| Color | 3/4 | Paleta dark, CTA laranja e contraste principal estavam alinhados; backgrounds, ícones e tokens exatos ainda divergiam. |
| Typography | 2/4 | Drift sistemático nos cinco alvos: título `10px` vs `11px`; hostname `600` vs `400`; labels `600/650` vs `500`; CTA `400/700` vs `500`; line-heights divergentes. |
| Spacing | 2/4 | Card mais alto, logo maior e offsets verticais de formulário/CTA diferentes; VPN adicionava mais deslocamento no formulário. |
| Experience Design | 3/4 | Todos os seis `/login` responderam `200`, a tarefa estática era compreensível e campos/CTA tinham dimensões utilizáveis; focus, teclado, mobile, estados e OIDC central não foram cobertos por esta captura. |

**Overall: 16/24**

**Verdict histórico:** `NEEDS_WORK_PRE_FIX_WITHOUT_TASK_BLOCKING_FAILURE`

## Top 3 Priority Fixes históricos

1. Normalizar o contrato tipográfico app-local para título `11px/400/16.5px`, hostname `14px/400/20px`, labels `14px/500/20px` e CTA `14px/500/20px`.
2. Normalizar card, logo e ritmo vertical para card `448x454.25`, radius `12px`, logo `44x44`, inputs/CTA `44px` e radius `10px`.
3. Consolidar tokens visuais e testes de regressão entre admin-edge, AdGuard, VPN e mirrors standalone para impedir novo drift.

## Findings objetivos

### Copywriting

O DOM raw confirmou:

- referência: `Atius SSO`, `DESTINO SEGURO`, `Nenhum destino selecionado`, `Email ou username`, `Senha`, `Entrar com Atius SSO`;
- alvos: mesma copy de formulário e CTA, substituindo o estado neutro pelo hostname contextual do app.

A vision model auxiliar leu Atius/domínios incorretamente na miniatura. OCR visual não foi usado como fonte textual; `raw/text-probe.json` e `raw/host-term-probe.json` são a fonte.

### Visuals

- Referência: card `448x454.25`, radius `12px`, logo final canônico `44x44`.
- Grafana/Portainer/Docker/AdGuard pré-fix: card `448x482`, logo `72x72`.
- Inputs e CTA mantinham largura `398px` e altura `44px`.
- O contact sheet confirma a mesma composição geral, mas com escala e ritmo diferentes.

### Color

- CTA referência: `rgb(249,115,22)`.
- CTA app-local: `rgb(255,113,18)`.
- Input referência: `rgb(31,41,55)`.
- Input app-local: `rgb(30,42,57)`.
- Fundo/card e ícones também apresentavam diferenças localizadas.

A paleta permanecia coerente; por isso o gap foi classificado como warning, não blocker.

### Typography

| Elemento | Referência | Grafana/Portainer/Docker/AdGuard | VPN |
|---|---|---|---|
| DESTINO SEGURO | `11px / 400 / 16.5px / normal` | `10px / 400 / normal / 0.8px` | `10px / 400 / 15px / 0.8px` |
| Hostname | `14px / 400 / 20px` | `16px / 600 / normal` | `14px / 600 / 21px` |
| Labels | `14px / 500 / 20px` | `14px / 650 / normal` | texto visual interno `14px / 600 / 20px` |
| CTA | `14px / 500 / 20px` | `14px / 700 / normal` | computed `14px / 400 / 21px` |

### Spacing

- Referência: card top `222.875`, bottom `677.125`.
- Admin-edge/AdGuard: card top `209`, bottom `691`.
- Form referência: top `432.125`, height `220`.
- Admin-edge/AdGuard: top `444`, height `218`.
- VPN: top `444`, height `226`; CTA top `626` vs `608.125` canônico.

Os alvos mantinham alinhamento horizontal, mas não paridade vertical.

### Experience Design

Coberto:

- seis páginas `/login` com HTTP `200`;
- campos de login/senha;
- controle de revelar senha visível;
- CTA de `44px`;
- destino explícito por hostname.

Não coberto neste review histórico:

- mobile/tablet;
- keyboard/focus order;
- mensagens de erro/loading/disabled;
- login autenticado;
- logout;
- dashboard interno;
- central OIDC.

## Pixel metrics

Os pixel diffs foram calculados contra screenshots integrais e crops fixos. Como a referência e os alvos continham conteúdo contextual diferente, não são um threshold de aceite isolado.

Card-crop mismatch `>3`:

- Grafana: `38.172%`;
- Portainer: `38.229%`;
- Docker: `38.131%`;
- VPN: `42.663%`;
- AdGuard: `38.199%`.

Use computed styles e asserts semânticos como critério principal; pixel diff apenas como corroborador.

## Critérios de aceite

1. Copy exata e hostname contextual correto.
2. Card `448x454.25`, radius `12px`.
3. Logo `44x44`.
4. DESTINO SEGURO `11px/400/16.5px`, tracking normal.
5. Hostname `14px/400/20px`.
6. Labels `14px/500/20px`.
7. Inputs `398x44`, radius `10px`, font `14px/400/20px`.
8. CTA `398x44`, radius `10px`, font `14px/500/20px`.
9. Sem emoji textual como substituto de asset/ícone.
10. Lifecycle host-local `2` ciclos por site, screenshots e checksums válidos.

## Pipeline failures sem impacto de produto

- `07:44:48`: `vision_analyze` retornou `503 model_not_found` no provider auxiliar.
- `07:44:59`: `browser_navigate(file://...)` retornou `400` no Camofox.
- Capturas headless e computed styles já estavam concluídos.
- Último tool result bem-sucedido: `07:45:56`.
- Timeout: `07:45:59`, durante síntese final.

## Supersession

Este review descreve somente o estado pré-fix.

Autoridade atual:

- `docs/evidence/atius-sso/2026-07-31-visual-reference-v2/computed-style-final.json`;
- `docs/evidence/atius-sso/2026-07-31-visual-reference-v2-lifecycle-20260731-093627/report.json`;
- `finalVerdict=PASS`;
- `PASS_HOST_LOCAL_SSO_VISUAL`;
- `hostLocalLifecycle=true`;
- `centralOidcFlow=false`.

O score histórico `16/24` não revoga nem substitui o visual-v2 posterior.
