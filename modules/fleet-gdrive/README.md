# Fleet Google Drive Storage Automation (`/mnt/gdrive`)

Módulo de provisionamento, governança, monitoramento e operação unificada do ponto de montagem compartilhado do Google Drive (`/mnt/gdrive`) em todos os servidores da frota ATIUS (`atius-srv-1`, `atius-srv-2`, `atius-srv-3`, `atius-srv-4` e `horistic-srv`).

---

## 1. Visão Geral e Arquitetura

O módulo integra o **Rclone FUSE** ao **HashiCorp Vault** e ao **Landscape Control-Plane**, fornecendo um filesystem distribuído de alta disponibilidade e zero pegada estática de disco para dados sensíveis.

```text
  [ HashiCorp Vault (atius-srv-3) ]
           │
           │ OCI DRG (10.13.1.13:8202) - Profile: omni-storage
           ▼
  [ /usr/local/bin/gdrive-vault-hydrate ]
           │
           │ Materialização efêmera em RAM (mode 0600)
           ▼
  [ /run/rclone/rclone.conf (tmpfs) ]
           │
           ▼
  [ gdrive-mount.service (systemd) ] ───► /mnt/gdrive (FUSE Mount)
           │                                    │
           │ Rate Pacing (--tpslimit 4)         ├── Full VFS Cache (/var/cache/rclone-gdrive)
           │ CPU Quota (<= 20% do Host)         └── Lazy Unmount (/bin/fusermount -u -z)
           ▼
  [ Google Workspace API ]
```

---

## 2. Tabela Canônica de Quotas VFS por Host

Para prevenir o esgotamento do disco raiz (ext4/Block Volume) — lição aprendida no incidente histórico de 2026-06-07 —, cada nó da frota possui limites estritos de retenção de cache VFS (`--vfs-cache-max-size` e `--vfs-cache-max-age`):

| Host | Função Principal | Quota Máxima (`max-size`) | Idade Máxima (`max-age`) | Justificativa / Capacidade |
|---|---|---|---|---|
| **`atius-srv-1`** | Bancos de Dados (PostgreSQL, Plane, Router AI) | **`3G`** | **`6h`** | Partição de sistema crítica (~70% ocupada). Cache restrito para evitar parada de banco. |
| **`atius-srv-2`** | Servidor de Correio e Relays (Mailcow) | **`10G`** | **`24h`** | Headroom moderado; retém mensagens e logs de transição. |
| **`atius-srv-3`** | Vault & Landscape Control-Plane | **`5G`** | **`12h`** | Servidor de infraestrutura e LXD containers. |
| **`atius-srv-4`** | K3s Cluster, GitLab Runner, GitHub Actions | **`30G`** | **`48h`** | Grande headroom de armazenamento (> 130 GiB livres); absorve artefatos de build de CI/CD. |
| **`horistic-srv`** | Servidor de Operações Auxiliar | **`10G`** | **`24h`** | Carga balanceada com retenção padrão de 24 horas. |
| **`default`** | Hosts não catalogados ou transitórios | **`4G`** | **`12h`** | Fallback conservador seguro para preservar o host. |

---

## 3. Segurança e Zero-Disk Footprint (Tmpfs 0600)

1. **Fonte Única da Verdade**: As credenciais OAuth do Google Drive residem exclusivamente no **HashiCorp Vault** em `kv/atius/omni-fleet/storage` (profile `omni-storage`).
2. **Materialização Efêmera**: Antes da inicialização do daemon, o script `/usr/local/bin/gdrive-vault-hydrate` cria `/run/rclone/` (garantidamente em `tmpfs`) com permissão `0700` e grava `/run/rclone/rclone.conf` com permissão estrita `0600`.
3. **Purga Automática**: No momento do desmonte ou parada do serviço (`ExecStopPost`), o arquivo `/run/rclone/rclone.conf` é removido imediatamente.
4. **Proteção contra Vazamento**: Nenhum segredo ou token OAuth jamais toca o disco magnético ou SSD persistente, prevenindo vazamentos através de snapshots OCI, dumps de backup ou inspeção forense de blocos.

---

## 4. Contenção de Recursos e CPU Guardrail

Em conformidade rigorosa com a diretriz global de contenção de CPU (<= 20% do host):
- **CPUQuota**: `80%` (em hosts Ampere A1 de 4 vCPUs, 80% de um core equivale a 20% da capacidade total do processador).
- **Prioridade de Processo**: `Nice=10` e política `CPUSchedulingPolicy=other`.
- **Prioridade de I/O**: `IOSchedulingClass=best-effort` e `IOSchedulingPriority=7`.
- **Pacing de API**:
  - `--tpslimit 4` e `--tpslimit-burst 1`
  - `--drive-pacer-min-sleep 100ms` e `--drive-pacer-burst 1`
  - Limite de conexões paralelas: `--transfers 2` e `--checkers 4`.
  - Evita banimento por saturação da cota de 10 TPS do Google Drive API quando múltiplos nós operam simultaneamente.

---

## 5. Ciclo de Vida do Serviço Systemd (`gdrive-mount.service`)

Localização: `/etc/systemd/system/gdrive-mount.service`

- **Type**: `notify` (o rclone emite sinal sd_notify assim que o FUSE estiver ativo).
- **Restart**: `on-failure` com `RestartSec=10s` (não entra em loop quando parado intencionalmente).
- **Desmonte Lazy**: `ExecStop=/bin/fusermount -u -z /mnt/gdrive`. O parâmetro `-z` (lazy) desacopla imediatamente o mountpoint do namespace VFS, impedindo travamentos em D-state no kernel mesmo que processos locais mantenham descritores abertos.
- **KillMode**: `mixed` (envia SIGTERM para o processo principal e SIGKILL para eventuais filhos órfãos apenas no timeout).

---

## 6. Comandos Canônicos do CLI `omni gdrive`

Todos os comandos suportam a flag `--json` e a flag `--host [HOSTNAME]`:

| Comando | Descrição | Códigos de Saída Canônicos |
|---|---|---|
| `omni gdrive quotas [--json]` | Exibe a tabela de quotas VFS por host | `0`: Sucesso |
| `omni gdrive status [--host H] [--json]` | Inspeciona estado do serviço, FUSE e tamanho do cache | `0`: Ativo/Montado em todos<br>`1`: Erro SSH/comunicação<br>`2`: Inativo ou Desmontado |
| `omni gdrive mount [--host H] [--json]` | Executa hidratação e inicia o `gdrive-mount.service` | `0`: Montado com sucesso<br>`1`: Falha de montagem |
| `omni gdrive unmount [--host H] [--json]` | Para o serviço e executa desmonte lazy | `0`: Desmontado com sucesso<br>`1`: Falha ao desmontar |
| `omni gdrive test [--host H] [--json]` | Probe ativo de escrita, leitura e conferência de hash SHA256 | `0`: PASS<br>`1`: FAIL (erro de IO/permissão) |
| `omni gdrive doctor [--host H] [--json]` | Diagnóstico de 8 pontos de conformidade operacional | `0`: Todos os 8 PASS<br>`1`: Falha crítica<br>`2`: Avisos (degradado) |
| `omni gdrive check [--host H] [--json]` | Sonda ultrarrápida (< 1s) para monitoramento sintético | `0`: Montado e responsivo<br>`1`: Erro/Timeout<br>`2`: Não montado |
| `omni gdrive list [--host H] [--path P]` | Lista arquivos no caminho informado | `0`: Sucesso<br>`1`: Erro |

---

## 7. Componentes e Scripts do Módulo

- **`scripts/install-fleet-gdrive.sh`**: Instalador local idempotente. Instala pacotes (`fuse3`, `rclone`), habilita `user_allow_other` em `/etc/fuse.conf`, higieniza montagens legadas de usuário, provisiona helpers em `/usr/local/bin`, detecta quotas do host, instala o `gdrive-mount.service` e inicia a montagem.
- **`scripts/gdrive-vault-hydrate.sh`**: Helper de tempo de execução que consulta o Vault (`atius-vault-env omni-storage`), valida integridade sintática e grava `/run/rclone/rclone.conf` (tmpfs 0600).
- **`scripts/gdrive-doctor.sh`**: Script de diagnóstico de 8 pontos:
  1. `/dev/fuse` acessível.
  2. `user_allow_other` em `/etc/fuse.conf`.
  3. Binário `rclone` instalado.
  4. Conectividade com o HashiCorp Vault.
  5. Segredos do perfil `omni-storage` presentes e íntegros.
  6. Resolução DNS e handshake HTTPS com `www.googleapis.com:443`.
  7. Headroom de disco suficiente para a cota de cache VFS.
  8. Ausência de units ou montagens conflitantes legadas.

---

## 8. Runbook de Operações e Troubleshooting

### A. Incidente: Falha ao Desmontar com `Device or resource busy` (EBUSY)
**Sintoma:** Processos locais (como `grep`, `find` ou indexadores) mantêm arquivos abertos dentro de `/mnt/gdrive`.
**Solução Imediata:**
```bash
# Executa desmonte lazy desacoplando o namespace imediatamente
fusermount -u -z /mnt/gdrive
# Identifica holders presos se necessário
lsof +D /mnt/gdrive
```

### B. Incidente: Exaustão de Quota da API Google Drive (HTTP 403 / 429)
**Sintoma:** Erros `rateLimitExceeded` ou `Queries per minute quota exceeded` nos logs do journalctl.
**Causa:** Múltiplos nós executando scans massivos ou falta de pacing.
**Solução:**
1. Verifique se as flags de pacing estão presentes no service:
   `--tpslimit 4 --drive-pacer-min-sleep 100ms`
2. Garanta que uploads de grande volume utilizem a fila serial `modules/fleet-backup/` com cooldown de 5 minutos, e nunca cópias concorrentes não governadas.

### C. Incidente: Cache VFS Ocupando Muito Disco
**Sintoma:** Alerta de disco cheio em `/var`.
**Solução:**
1. Consulte o tamanho atual do cache:
   ```bash
   du -sh /var/cache/rclone-gdrive
   ```
2. O rclone purga automaticamente itens expirados pela regra `--vfs-cache-max-age`. Para forçar liberação imediata:
   ```bash
   sudo systemctl stop gdrive-mount.service
   sudo rm -rf /var/cache/rclone-gdrive/*
   sudo systemctl start gdrive-mount.service
   ```

### D. Incidente: Falha de Hidratação do Vault
**Sintoma:** O serviço falha no `ExecStartPre` com código 1.
**Diagnóstico:**
```bash
# Executa manualmente o hydrator para inspecionar saída de erro
sudo /usr/local/bin/gdrive-vault-hydrate
# Testa conectividade com o Vault
curl -k https://10.13.1.13:8202/v1/sys/health
```
**Ação Corretiva:** Caso o token do Vault tenha expirado, renove-o com `atius-vault-env` ou verifique o serviço do Vault em `atius-srv-3`.

---

## 9. Integração com Landscape e Frontend Web

- **Landscape Control-Plane**: Execução simultânea em toda a frota:
  ```bash
  omni landscape run setup-fleet-gdrive --hosts atius-srv-1,atius-srv-2,atius-srv-3,atius-srv-4 --wait --yes
  ```
- **Web Storage Frontend**: Interface web acessível via `https://storage.atius.io` (e `storage.atius.com.br`) roteada pelo Atius Admin Edge Gateway (`127.0.0.1:8210`), autenticada corporativamente pelo ATS SSO e servida pelo Filebrowser sobre `/mnt/gdrive`.
