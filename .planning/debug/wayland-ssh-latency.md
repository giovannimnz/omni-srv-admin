---
status: diagnosed
trigger: "Pesquisar terminal e execucao remota sem criptografia para o desenvolvimento hibrido Wayland/NFS da sessao 019f7906-ebc4-72b2-8137-68ccce609766"
created: 2026-07-19
updated: 2026-07-19
---

## Symptoms

- expected: comandos de desenvolvimento executados no host proprietario do workspace devem iniciar com latencia proxima do enlace OCI/DRG, sem enfraquecer autenticacao, integridade ou verificacao de host.
- actual: uma conexao SSH nova custa centenas de milissegundos e apresenta variacao sob carga; foi levantada a hipotese de que a criptografia seria o gargalo.
- errors: nao ha erro funcional persistente; houve uma pausa transitoria de aproximadamente 10 segundos entre a oferta e a aceitacao da chave publica em `atius-srv-1` durante carga elevada.
- timeline: investigado em 2026-07-19 como continuacao do runtime hibrido Wayland/NFS implementado na sessao Codex 019f7906-ebc4-72b2-8137-68ccce609766.
- reproduction: em `atius-srv-3`, comparar `ssh -T <alias> true` frio com conexao direta DRG, conexao multiplexada e ciphers modernos diferentes.

## Current Focus

- hypothesis: "Confirmada no nivel de transporte/configuracao: setup e autenticacao de conexoes SSH nao multiplexadas, com caminho SSSD/IPA dos aliases lowercase, dominam a latencia; cipher por pacote nao e material para comandos pequenos."
- test: "Auditoria independente dos dados ja coletados: RTT, `ssh -G`, cold versus master persistente e comparacao controlada entre ChaCha20-Poly1305 e AES128-GCM."
- expecting: "Concluido: todos os quatro resultados medidos sustentam a hipotese e nenhum sustenta criptografia como gargalo."
- next_action: "Retornar diagnostico ao orquestrador; nenhum fix ou benchmark adicional autorizado."
- audit_caveat: "AcpAgentManager injeta a forma canonica `ssh <target> 'cd <workspace> && <command>'` no prompt, mas nao implementa nem intercepta o transporte; portanto, cada comando SSH emitido pelo agente depende da multiplexacao configurada no client. Nem toda operacao Wayland usa SSH: leitura, busca e diff permanecem no mount NFS."

## Evidence

- timestamp: 2026-07-19
  result: "Graphify localizou docs/operations/WAYLAND-FLEET-GITHUB-NFS.md e docs/operations/wayland-managed-runtime.md; ambos confirmam edicao NFS local em atius-srv-3 e execucao no host proprietario via SSH/DRG."
- timestamp: 2026-07-19
  result: "OpenSSH 9.6p1 em atius-srv-3 nao anuncia o cipher none em ssh -Q cipher; o codigo OpenSSH corrente marca none como interno e o exclui da lista negociavel."
- timestamp: 2026-07-19
  result: "ssh -G nos aliases lowercase mostrou ControlMaster false, ControlPersist no e ProxyCommand /usr/bin/sss_ssh_knownhostsproxy -p %p %h."
- timestamp: 2026-07-19
  result: "Master direto DRG abriu em aproximadamente 158-159 ms; depois do primeiro uso, execucoes de true ficaram em aproximadamente 14-18 ms."
- timestamp: 2026-07-19
  result: "ChaCha20-Poly1305 e AES128-GCM mediram ambos aproximadamente 13-14 ms com master direto persistente."
- timestamp: 2026-07-19
  result: "HPN-SSH suporta NoneSwitch somente depois da autenticacao, nao permite shell interativo e documenta que o ganho pressupoe pelo menos cerca de 100 ms de RTT; tambem alerta que HPN pode reduzir desempenho em LAN."
- timestamp: 2026-07-19
  result: "Auditoria independente confirmou quatro pontos nos dados existentes: RTT DRG sub-ms; aliases lowercase com SSSD/GSSAPI e sem ControlMaster; queda de aproximadamente 158-159 ms cold para 14-18 ms com master; equivalencia de aproximadamente 13-14 ms entre ChaCha20-Poly1305 e AES128-GCM."
- timestamp: 2026-07-19
  result: "Inspecao read-only do call site live em /home/ubuntu/GitHub/wayland/src/process/task/AcpAgentManager.ts confirmou que Wayland injeta orientacao e uma forma canonica `ssh ...` no prompt; nao existe neste seam um executor SSH persistente ou reescrita transparente de comandos."

## Eliminated

- hypothesis: "A criptografia simetrica de cada pacote e o principal custo dos comandos remotos."
  reason: "As duas cifras modernas tiveram o mesmo tempo de aproximadamente 13-14 ms quando todos os demais fatores foram mantidos; o enlace tem RTT de aproximadamente 0.5 ms."
- hypothesis: "OpenSSH padrao pode ser configurado com Ciphers none."
  reason: "Embora o RFC 4253 defina none como opcional e nao recomendado, OpenSSH corrente o trata como cipher interno e nao negociavel."
- hypothesis: "HPN-SSH com none entrega um terminal interativo plaintext rapido para este caso."
  reason: "O proprio HPN-SSH proibe NoneSwitch em shell interativo e posiciona o recurso para throughput em links de RTT alto, nao para comandos pequenos numa LAN/DRG."

## Resolution

- root_cause: "O seam Wayland apenas orienta o agente a emitir comandos SSH e nao mantem um transporte persistente. Essas invocacoes seguem sem multiplexacao automatica; os aliases lowercase caem na configuracao global SSSD/IPA, mantem GSSAPI/multiplas identities e pagam setup/autenticacao. Carga elevada no host remoto adiciona variacao. A criptografia nao e o gargalo medido."
- fix: "nao aplicado; diagnostico somente. Direcao recomendada: aliases exatos por IP DRG, identidade unica, autenticacao publickey, host key pinada, ControlMaster auto, ControlPersist limitado e ControlPath seguro; manter SSH cifrado."
- verification: "Graphify e documentos do runtime; configuracao efetiva ssh -G; ping DRG; amostras frias e multiplexadas; comparacao controlada de ciphers; RFC/OpenSSH/HPN-SSH oficiais."
- files_changed: ".planning/debug/wayland-ssh-latency.md"
