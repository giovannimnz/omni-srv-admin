# Runbook: Fleet Google Drive Storage Mount & Governance (/mnt/gdrive)

## 1. Visão Geral e Arquitetura

Este documento estabelece o padrão canônico para montagem e operação do armazenamento em nuvem Google Drive em toda a frota ATIUS (`atius-srv-1`, `atius-srv-2`, `atius-srv-3`, `atius-srv-4`, `horistic-srv` e futuros nós).

### Diretrizes Centrais
- **Ponto de Montagem Canônico:** `/mnt/gdrive` (owner `ubuntu:ubuntu`, mode `0755`, `--allow-other`).
- **Isolamento de Segredos (Zero-Disk Secrets):** As credenciais OAuth 2.0 residem exclusivamente no **HashiCorp Vault** (`kv/atius/omni-fleet/storage`). O arquivo `rclone.conf` é hidratado dinamicamente em **tmpfs volátil** (`/run/rclone/rclone.conf`, mode `0600`) no disparo do serviço e apagado imediatamente após a desmontagem (`ExecStopPost`).
- **Governança de Disco e Quotas VFS:** Para impedir saturação do disco local (especialmente no `atius-srv-1`, que opera com ~11GB livres), cada servidor possui limite estrito de cache VFS (`--vfs-cache-max-size` e `--vfs-cache-max-age`).
- **Governança de CPU e IO:** O serviço executa com `Nice=10`, `IOSchedulingClass=best-effort`, `IOSchedulingPriority=7`, `--transfers=2` e `--checkers=4`, garantindo conformidade com o teto de 20% de CPU total do host.

---

## 2. Quotas de Cache VFS por Servidor

| Host | Quota Máxima VFS (`--vfs-cache-max-size`) | Retenção Máxima (`--vfs-cache-max-age`) | Justificativa |
| :--- | :--- | :--- | :--- |
| **`atius-srv-1`** | **3 GB** | **6 horas** | Disco raiz com ~11 GB livres; prioridade para banco e web |
| **`atius-srv-2`** | **10 GB** | **24 horas** | Host de suporte e serviços com folga de armazenamento |
| **`atius-srv-3`** | **5 GB** | **12 horas** | Host central de governança (Vault, Landscape, DNS) |
| **`atius-srv-4`** | **30 GB** | **48 horas** | Maior volume disponível (~85 GB livres) para builds/datasets |
| **`horistic-srv`** | **10 GB** | **24 horas** | Servidor de automações e scraping |
| **Default / Novos**| **4 GB** | **12 horas** | Baseline seguro para nós recém-provisionados |

---

## 3. Gestão de Segredos no HashiCorp Vault

### Localização Canônica
- **Vault Server:** `https://10.13.1.13:8202` (via OCI DRG direta).
- **Caminho KV:** `kv/atius/omni-fleet/storage`
- **Profile:** `omni-storage` (alias aceito: `gdrive`).

### Chaves Armazenadas:
1. `GDRIVE_CLIENT_ID`: OAuth 2.0 Client ID dedicado da ATIUS (Desktop Application).
2. `GDRIVE_CLIENT_SECRET`: OAuth 2.0 Client Secret correspondente.
3. `GDRIVE_REFRESH_TOKEN`: Refresh token emitido offline para o Client ID da ATIUS.

### Hidratação em Runtime (`/usr/local/bin/gdrive-vault-hydrate`)
O helper é invocado pelo systemd (`ExecStartPre=/usr/local/bin/gdrive-vault-hydrate`):
1. Cria `/run/rclone` com permissões `0700`.
2. Executa `atius-vault-env omni-storage`.
3. Valida a presença de `GDRIVE_CLIENT_ID`, `GDRIVE_CLIENT_SECRET` e `GDRIVE_REFRESH_TOKEN`.
4. Monta o arquivo `/run/rclone/rclone.conf` com permissão estrita `0600`.
5. Valida a sintaxe local sem chamar a rede.
6. Em caso de qualquer inconsistência, remove o arquivo e encerra com código de erro (fail-closed).

---

## 4. Onboarding de Novos Servidores (`atius-srv-X`)

Quando um novo servidor for adicionado à frota ATIUS, a configuração do `/mnt/gdrive` faz parte do processo de bootstrap obrigatório:

### Passo 1: Permitir Perfil no Helper Local do Host
No novo host, garanta que `/home/ubuntu/.local/bin/atius-vault-env` aceite o perfil `omni-storage` na allowlist (ou use o padrão wildcard alfanumérico).

### Passo 2: Registrar no Inventário do Omni
Adicionar `inventory/hosts/atius-srv-X.yaml` com o respectivo IP privado DRG (`10.1X.1.1X`).

### Passo 3: Executar Rollout via Landscape Control-Plane
Executar a partir da máquina de gerenciamento ou servidor central:
```bash
omni landscape run gdrive-fleet-setup --hosts atius-srv-X --wait --yes
```

O Landscape Control-Plane irá automaticamente:
1. Instalar `fuse3` e `rclone` se ausentes.
2. Ativar `user_allow_other` em `/etc/fuse.conf`.
3. Criar `/mnt/gdrive` e `/var/cache/rclone-gdrive`.
4. Desativar quaisquer montagens ou services legados de usuário.
5. Instalar `/usr/local/bin/gdrive-vault-hydrate`.
6. Configurar `/etc/systemd/system/rclone-gdrive.service` com a quota calculada para o host.
7. Iniciar o serviço e executar smoke-test de leitura.

### Passo 4: Validação
```bash
omni gdrive status --host atius-srv-X
omni gdrive health --host atius-srv-X
```

---

## 5. Operação via CLI (`omni gdrive`)

O comando unificado `omni gdrive` fornece controle rápido:

```bash
# Consultar tabela de quotas de cache da frota
omni gdrive quotas

# Verificar status da unit e montagem em todos os servidores (ou em um específico)
omni gdrive status
omni gdrive status --host atius-srv-1

# Iniciar ou reiniciar montagem
omni gdrive mount --host atius-srv-2

# Desmontar com segurança
omni gdrive unmount --host atius-srv-2

# Teste de integridade e leitura de arquivos
omni gdrive health
```
