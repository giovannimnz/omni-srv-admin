---
status: fixing
trigger: "Validar os ajustes recentes de teclado/idioma/RDP no atius-srv-1, confirmar paridade em atius-srv-2, atius-srv-3 e horistic-srv, reconstruir logs/scripts/skills/Obsidian/GBrain e tornar a correção definitiva contra drift."
created: 2026-08-29
updated: 2026-08-29
---

# XRDP Keyboard Fleet Drift

## Symptoms

- expected: Todos os quatro hosts mantêm teclado Português Brasil ABNT2 em novas sessões Microsoft RDP, com setas, Delete, Print Screen, barras, AltGr e clipboard corretos, inclusive após reboot, login e atualização de pacotes.
- actual: O estado live atual ainda não foi revalidado; existe uma correção recente e não commitada de 2026-08-28 no checkout do SRV-1 que altera os índices de scancode XRDP 0.9.24 e precisa ser confrontada com cada host.
- errors: Histórico recente relata setas disparando Print Screen, Delete mapeado incorretamente e barra ABNT_C1 ausente quando o keymap usa offsets live evdev em vez dos índices xfree86/base consumidos pelo XRDP 0.9.24.
- timeline: Rollout fleet anterior concluído em 2026-07-02; nova correção de scancodes apareceu no checkout em 2026-08-28. A task atual começou em 2026-08-29.
- reproduction: Abrir nova sessão Microsoft RDP em cada host e testar scancodes críticos; via SSH read-only, executar validate/diff, hashes, systemd, APT hook, watchdog, keylayout dos logs e readback da sessão X11.

## Current Focus

- bug_class: heisenbug-mandelbug (depende de host, sessão XRDP nova e update de pacote)
- hypothesis: "SRV-2, SRV-3 e Horistic mantêm keymaps gerados/indexados para evdev, enquanto o XRDP 0.9.24 consulta índices xfree86/base; isso roteia os scancodes estendidos aos símbolos errados. A CLI instalada em Horistic deriva REPO_ROOT de site-packages e não encontra os assets do módulo."
- test: "Executar os testes focais, criar uma distribuição wheel que contém assets do módulo e, após deploy sem restart, comparar os hashes live e executar validate/diff em cada host."
- expecting: "Cada host remoto terá o payload SHA-256 cdd4e2... e validate/diff passarão; a CLI instalada encontrará os assets distribuídos."
- next_action: "Endurecer o guard: validator deve exigir timer enabled+active e o reconciliador deve criar backup limitado somente quando detectar divergência, com jitter para a fleet; então fazer review/merge e solicitar confirmação de sessão Microsoft RDP nova."
- reasoning_checkpoint:
    hypothesis: "Os índices evdev do keymap nos três hosts causam scancodes estendidos errados porque XRDP 0.9.24 resolve km-*.ini pelos índices xfree86/base; o pacote uv do Horistic não inclui modules/xrdp-abnt2, logo REPO_ROOT em site-packages não contém seus assets."
    confirming_evidence:
      - "Leitura direta mostrou SRV-1 com Key98/100/102/104/107/111/123 corretas e SRV-2/SRV-3/Horistic com os offsets evdev incompatíveis."
      - "Horistic falha validate/diff com FileNotFoundError para modules/xrdp-abnt2/files sob site-packages."
    falsification_test: "Se um host com os valores xfree86/base ainda apresentar os mesmos símbolos errados em uma nova sessão Microsoft RDP, ou se uma wheel com assets continuar a falhar por caminho ausente, a hipótese está incompleta."
    fix_rationale: "Substituir os keymaps pelos assets canônicos corrige a tabela efetivamente consultada pelo XRDP; incluir os assets no pacote elimina a dependência indevida do checkout."
    blind_spots: "A entrada física do cliente Microsoft RDP exige confirmação em sessão nova pelo operador; não será simulada por SSH."
    candidate_causes:
      - "config: keymaps remotos antigos e xrdp.ini/helper divergentes."
      - "code/package: omni instalado em Horistic não distribui os assets que xrdp_abnt2 resolve."
    and_gate: "yes: para Horistic, o mapa errado e a CLI sem assets contribuem de forma independente; o mapa explica o teclado, a falha de pacote bloqueia o validador persistente."

## Evidence

- timestamp: 2026-08-29
  result: "GBrain localizou o rollout fleet de 2026-07-02 com PASS histórico em SRV-1/SRV-2/SRV-3/Horistic e a fonte canônica do XRDP ABNT2."
- timestamp: 2026-08-29
  result: "Checkout já estava dirty; arquivos XRDP relevantes têm mtime de 2026-08-28 01:58-02:01 BRT e implementam índices xfree86/base para XRDP 0.9.24, testes novos e documentação."
- timestamp: 2026-08-29
  result: "Graphify GSD foi reconstruído sob resource governor e publicado em .planning/graphs: 14228 nodes, 20831 edges, commit b1d66b2, stale=false."
- timestamp: 2026-08-29
  result: "Leitura completa do contrato do módulo confirmou a correção-alvo: no XRDP 0.9.24, os índices consumidos devem ser xfree86/base (setas Key98/100/102/104, Delete Key107, Print Key111 e ABNT_C1 Key123); usar offsets evdev explica exatamente os sintomas relatados."
- timestamp: 2026-08-29
  result: "Auditoria live read-only: SRV-1 passou validate/diff, XRDP 0.9.24 e todos os seis keymaps têm hash cdd4e2...; havia sessão Xvnc :1 e sessões loginctl ativas, portanto nenhum restart foi feito. As três rotas VPN dos SRVs falharam no banner SSH e as rotas públicas responderam."
- timestamp: 2026-08-29
  result: "SRV-2 e SRV-3 executam XRDP 0.9.24, mas validate falha por ausência dos três overrides em xrdp.ini e diff mostra helper antigo sem km-00000416/overrides; seus keymaps têm hash e24a96..., divergente do SRV-1. Também têm sessões RDP ativas."
- timestamp: 2026-08-29
  result: "Horistic responde pela rota pública e seus keymaps têm hash e24a96..., mas `omni xrdp-abnt2 validate/diff` aborta com FileNotFoundError: REPO_ROOT do pacote uv resolve para site-packages/modules/xrdp-abnt2/files inexistente."
- timestamp: 2026-08-29
  result: "Teste diferencial direto confirmou a causa: SRV-1 tem Key98=65362 (Up), Key100=65361 (Left), Key102=65363 (Right), Key104=65364 (Down), Key107=65535 (Delete), Key111=65377 (Print) e Key123=47 (/); SRV-2/SRV-3/Horistic têm Key98=65318, Key100=65315, Key102=65314, Key104=65421, Key107=65377, Key111=65362 e Key123=269025043 — o mapa evdev deslocado que produz os sintomas. Horistic respondeu igualmente nos caminhos privado 10.21.1.21 e público."
- timestamp: 2026-08-29
  result: "O diff local mostra que o patch pendente substitui precisamente o contrato evdev por xfree86/base, adiciona os oito estados ABNT e endurece validator/testes. `python3 -m pytest -q cli/omni/tests/test_xrdp_abnt2.py` passou: 10 testes."
- timestamp: 2026-08-29
  result: "Backup do diff focal XRDP criado antes de mutações do repo: /home/ubuntu/.backups/xrdp-keyboard-fleet-20260829/repo-xrdp-focused-pre-fix.tgz (sha256 cb9cb66b7e6f10946eb39ba2e51bd0e526fe113ebe640f2b5b0c8e7af1ad)."
- timestamp: 2026-08-29
  result: "Escopo de closeout ampliado pelo operador: reconciliação systemd sem restart, auditoria Landscape somente se material, skill Codex nativa, e registros Obsidian/GBrain."
- timestamp: 2026-08-29
  result: "Commit focal 41ba2acb em branch fix/xrdp-keyboard-fleet-drift-20260829 e PR #19 criados; testes focais 12/12 e validate-pack codex-skills passaram. Os três hosts remotos estão em main limpo, com XRDP/XRDP-sesman ativos, pré-requisitos presentes e conectividade pública confirmada; as rotas VPN de SRV-2/SRV-3 falharam no banner conforme registrado."
- timestamp: 2026-08-29
  result: "Rollout serial passou em SRV-2, SRV-3 e Horistic: cada install criou backup, não reiniciou XRDP, validate/diff passaram, timer está enabled+active e os cinco keymaps agora têm SHA-256 cdd4e2def3657b451fdef8d9c2038e28112f1df2498e768f3c8ddd5eb0a34237. Sessões e processos XRDP/Xvnc ativos permaneceram presentes. Horistic atualizou `uv tool` para omni 0.2.4 e sua CLI instalada passou validate/diff, corrigindo os assets ausentes."

## Eliminated

## Resolution

- root_cause: "Configuração/payload: o rollout de 2026-08-28 que corrige os índices consumidos pelo XRDP 0.9.24 está somente no SRV-1. SRV-2, SRV-3 e Horistic ainda usam km-abnt2 evdev antigo (hash e24a96...) e portanto interpretam scancodes estendidos em índices errados; SRV-2/SRV-3 também não têm os overrides de xrdp.ini e helper atualizados. A instalação uv de Horistic possui um bug independente de empacotamento (assets ausentes sob REPO_ROOT em site-packages), que impede validate/diff quando a CLI não é importada do checkout."
- fix: "Pendente de rollout coordenado: preservar backup e aplicar o payload focal já presente no checkout para SRV-2/SRV-3/Horistic, sem restart de xrdp, depois validar hash/CLI e nova sessão Microsoft RDP; reparar o empacotamento uv de Horistic para distribuir os assets ou resolver seu caminho instalado."
- verification: "Pré-fix confirmado diretamente em quatro hosts; SRV-1 validado e os outros três divergentes. Teste focal local: 10 passed. Verificação de pós-rollout e confirmação humana ainda pendentes."
- files_changed: []
