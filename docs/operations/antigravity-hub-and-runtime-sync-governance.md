# Antigravity 2.0 & AI Runtime Auto-Sync Governance

**Data:** 2026-10-02  
**Status:** ATIVO E EM PRODUÇÃO  
**Automação:** Landscape Control Plane (`omni::antigravity-hub-install`, `omni::sync-agent-instructions`), Systemd Timers (Linux) e Scheduled Task Zero-UI (Windows 11).

---

## 1. Contexto e Objetivos

1. **Antigravity 2.0 (Hub):** Instalar e padronizar o Antigravity 2.0 (tarball oficial do Hub) em todos os nós da frota Linux (`atius-srv-1`, `atius-srv-2`, `atius-srv-3`, `atius-srv-4`, `horistic-srv`), registrando o binário no PATH como `antigravity` (reservando `antigravity-ide` para a IDE clássica via PPA) e publicando o atalho desktop `Antigravity 2.0` na categoria Development.
2. **Auto-Atualização Autônoma Contínua:** Estabelecer sincronização automática periódica de `skills/` (315 skills canônicas), `AGENTS.md` e `GEMINI.md` em toda a frota Linux e no Windows 11 (`giovanni-w11-pc`), sem depender de disparos manuais.
3. **Controle de Versão Unificado:** Garantir que o repositório central `omni-srv-admin` (`~/GitHub/omni-srv-admin`) esteja presente e no mesmo commit Git em todos os servidores e estações de trabalho.

---

## 2. Antigravity 2.0: Instalação e Governança

### 2.1 Especificação de Binários e Caminhos

| Componente | Caminho / Valor |
|---|---|
| **Versão Canônica** | `2.19.1-6046815158665216` |
| **Tarball ARM64** | `https://storage.googleapis.com/antigravity-public/antigravity-hub/2.19.1-6046815158665216/linux-arm/Antigravity.tar.gz` |
| **Tarball x86_64** | `https://storage.googleapis.com/antigravity-public/antigravity-hub/2.19.1-6046815158665216/linux-x64/Antigravity.tar.gz` |
| **Diretório Base** | `/opt/antigravity-hub/2.19.1-6046815158665216/` |
| **Symlink PATH** | `/usr/local/bin/antigravity` |
| **IDE PPA Clássica** | `/usr/local/bin/antigravity-ide` |
| **Atalho Desktop** | `/usr/share/applications/antigravity-hub.desktop` |
| **Categoria Desktop** | `Categories=Development;IDE;` |
| **Nome no Menu** | `Name=Antigravity 2.0` |

### 2.2 Script de Distribuição Landscape

Versionado em `modules/landscape-control-plane/scripts/antigravity-hub-install.sh`:
- Detecta arquitetura (`aarch64` vs `x86_64`).
- Idempotente: se a versão já estiver instalada em `/opt/antigravity-hub/<version>` e symlink válido, sai imediatamente com código 0.
- Extrai ícone em alta resolução diretamente de `resources/app.asar` usando script Python integrado.
- Cria `/usr/share/applications/antigravity-hub.desktop` e propaga para `~/.local/share/applications/` de todos os usuários com XRDP.
- Configura permissões root e SUID em `chrome-sandbox`.

Comando de execução simultânea em toda a frota:
```bash
omni landscape run antigravity-hub-install --hosts all --wait --yes
```

---

## 3. Mecanismo Autônomo de Auto-Atualização

### 3.1 Arquitetura do Manifesto Remoto (`runtime-manifest.json`)

Para evitar chamadas complexas com pipes ou parsing de texto frágil entre plataformas (Linux vs Windows PowerShell), o host principal (`atius-srv-1`) publica um manifesto leve e determinístico gerado por `generate-runtime-manifest.sh`:

Localização: `/home/ubuntu/.gemini/config/runtime-manifest.json`
```json
{
  "version": "2026-10-02T17:12:06Z",
  "agents_md5": "4cce248dd2c0f29349e462dd9a4e0da1",
  "skills_count": 315,
  "skills_tar_md5": "824bbc5045e6d322e53de6bca59dbcda"
}
```

Qualquer nó (Linux ou Windows) compara seu hash local do `AGENTS.md` e contagem de skills com o manifesto. Caso haja divergência, o nó baixa os artefatos atualizados e restaura a paridade.

### 3.2 Linux Fleet: Systemd Timer Recorrente

Em cada host Linux (`atius-srv-1`, `atius-srv-2`, `atius-srv-3`, `atius-srv-4`, `horistic-srv`):
- **Service:** `/etc/systemd/system/omni-fleet-runtime-sync.service`
- **Timer:** `/etc/systemd/system/omni-fleet-runtime-sync.timer` (executa no boot + a cada 2 horas)
- **Script Executável:** `/usr/local/bin/omni-fleet-runtime-sync.sh`
- **Ações:**
  1. Compara hash MD5 de `~/.gemini/config/AGENTS.md` com a fonte canônica (`10.11.1.11` via OCI DRG).
  2. Atualiza symlinks canônicos (`GEMINI.md`, `CLAUDE.md`, `CODEX.md`).
  3. Verifica contagem de skills (mínimo 315). Se defasado, extrai `fleet-skills.tar.gz`.
  4. Executa `git pull --ff-only origin main` em `~/GitHub/omni-srv-admin`.
  5. Ajusta permissões dos usuários locais (`ubuntu` e `horistic`).

### 3.3 Windows 11 (`giovanni-w11-pc`): Zero-UI Scheduled Task

Em conformidade estrita com a diretriz **Windows Zero-UI Operational UX Design System**:
- **Tarefa Agendada:** `Omni-Runtime-AutoSync`
- **Launcher:** `C:\Windows\System32\wscript.exe //B //NoLogo "C:\Users\muniz\.gemini\bin\sync-runtime-launcher.vbs"`
- **Script VBS:** Executa PowerShell com `WScript.Shell.Run(..., 0, True)` (modo totalmente invisível, sem flash de janelas conhost/cmd).
- **Worker Script:** `C:\Users\muniz\.gemini\bin\sync-runtime-w11.ps1`
  - Baixa `runtime-manifest.json` via `scp.exe` nativo.
  - Compara hash MD5 com `certutil -hashfile`.
  - Baixa `AGENTS.md` e `fleet-skills.tar.gz` somente quando detectada alteração no manifesto.
  - Registra atividades em `C:\Users\muniz\.gemini\logs\runtime-sync.log`.
- **Gatilhos da Tarefa:** No Logon do usuário `muniz` + repetição a cada 2 horas indefinidamente (`RunLevel=Limited`, `MultipleInstances=IgnoreNew`, `AllowStartIfOnBatteries=True`).
- **Backup XML:** `modules/landscape-control-plane/windows-tasks/Omni-Runtime-AutoSync.xml`.

---

## 4. Paridade Git do `omni-srv-admin`

Todos os nós operacionais mantêm o repositório sincronizado no mesmo commit da branch `main`:

| Nó | Caminho Local | Status de Commit |
|---|---|---|
| `atius-srv-1` | `/home/ubuntu/GitHub/omni-srv-admin` | `origin/main` |
| `atius-srv-2` | `/home/ubuntu/GitHub/omni-srv-admin` | `origin/main` |
| `atius-srv-3` | `/home/ubuntu/GitHub/omni-srv-admin` | `origin/main` |
| `atius-srv-4` | `/home/ubuntu/GitHub/omni-srv-admin` | `origin/main` |
| `horistic-srv` | `/home/horistic/GitHub/omni-srv-admin` | `origin/main` |
| `giovanni-w11-pc` | `C:\Users\muniz\GitHub\omni-srv-admin` | `origin/main` |

---

## 5. Verificação e Diagnóstico

### Checar status do timer no Linux:
```bash
systemctl status omni-fleet-runtime-sync.timer
systemctl list-timers omni-fleet*
```

### Checar tarefa no Windows 11 via SSH:
```bash
ssh -p 8122 muniz@ssh-giovanni-w11-pc.atius.com.br "powershell -NoProfile -Command \"Get-ScheduledTask -TaskName Omni-Runtime-AutoSync; Get-Content C:\Users\muniz\.gemini\logs\runtime-sync.log -Tail 10\""
```

### Disparar sincronização manual em toda a frota Linux via Landscape:
```bash
omni landscape run sync-agent-instructions --hosts all --wait --yes
```
