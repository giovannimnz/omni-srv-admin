# Estudo de Viabilidade Arquitetural: Frontend de Storage Remoto da Frota

**Cenário:** Disponibilização de interface web para visualização, upload, download e gestão de arquivos do armazenamento corporativo Google Drive (`/mnt/gdrive`) da frota ATIUS.
**Opções Avaliadas:**
- **Opção A:** Subdomínio Dedicado: `storage.atius.io` (e espelho `storage.atius.com.br`)
- **Opção B:** Subcaminho Integrado no Portal Omni: `https://omni.atius.io/storage`

---

## 1. Matriz Comparativa Técnica

| Dimensão Técnica | Opção A: `storage.atius.io` (Subdomínio) | Opção B: `omni.atius.io/storage` (Subcaminho) | Vencedor |
| :--- | :--- | :--- | :--- |
| **Compatibilidade com Motores Web (Filebrowser, Nextcloud, Rclone RC)** | **Nativa (100%):** Aplicações esperam rodar na raiz `/`. Zero problemas com `/static/`, `/api/` ou websockets. | **Frágil:** Exige reescrita de URLs, flags de base-path ou proxies reversos complexos com risco de quebra de assets. | **Opção A** |
| **Isolamento de Segurança e Cookies** | **Excelente:** Origem web independente (`Same-Origin Policy`). Cookies e tokens não colidem com o portal administrativo. | **Médio:** Cookies de sessão e localStorage compartilhados no domínio `omni.atius.io`. | **Opção A** |
| **Governança de Autenticação e Acesso** | **Flexível:** Política própria no Cloudflare Access / ATS SSO (ex: timeout de sessão maior para downloads longos). | **Amarrada:** Obrigada a seguir a mesma política estrita e curta de timeout de sessão do Omni Admin. | **Opção A** |
| **Desempenho e I/O de Rede** | **Isolado:** Uploads/downloads grandes (chunked HTTP/WebSockets) não disputam buffers com chamadas do Omni. | **Compartilhado:** Conexões de transferência longa podem consumir threads do proxy reverso do Omni. | **Opção A** |
| **Experiência do Usuário (UX)** | Acesso direto e limpo via URL dedicada ou atalho no launcher ATIUS. | Integrado visualmente na barra de navegação do painel central. | **Empate** |
| **Esforço de Provisionamento** | Baixo: 1 registro CNAME no Cloudflare + vhost Apache/Caddy com ATS SSO Edge Gateway. | Médio/Alto: Reconfiguração de rotas de proxy reverso e rewrites no Omni. | **Opção A** |

---

## 2. Tecnologias de Frontend Recomendadas

1. **Filebrowser (filebrowser/filebrowser):**
   - Binário Go único, ultra-leve (<30MB RAM, zero overhead de CPU).
   - Suporta usuários locais, autenticação por header (`X-Forwarded-User` do ATS SSO), busca indexada, visualizador de PDFs/vídeos/imagens, e links de compartilhamento com expiração.
   - Aponta diretamente para `/mnt/gdrive`.
2. **Rclone Web GUI (Nativo):**
   - Disponível nativamente no próprio `rclone rcd --rc-web-gui`.
   - Excelente para visualização técnica e estatísticas de transferência, porém interface menos voltada ao usuário final.

---

## 3. Arquitetura Canônica Proposta (Solução Híbrida Vencedora)

A solução recomendada é a **Arquitetura Desacoplada com Enlace Unificado no Portal Omni**:

1. **Backend / Serviço Web:**
   - Container rootless Podman `container-filebrowser-storage` executando em `atius-srv-3` (ou nó com menor pressão de disco).
   - Volume montado em read-write apontando para `/mnt/gdrive` (com lock de contenção de CPU governado).
2. **Borda e Acesso Externo:**
   - Host `storage.atius.io` (com espelho `storage.atius.com.br` conforme diretriz `atius-dual-domain`).
   - Terminação TLS na Cloudflare + Edge SSO Gateway com ATS SSO para autenticação corporativa automática.
3. **Integração no Portal Omni (`omni.atius.io`):**
   - Adicionar menu "Storage / Drive" na barra lateral do Omni Admin.
   - O item de menu redireciona de forma transparente para `https://storage.atius.io` (ou carrega via iframe seguro com headers `Content-Security-Policy: frame-ancestors 'self' https://omni.atius.io https://omni.atius.com.br`).

Desta forma, garantimos estabilidade total de assets e websockets sem abrir mão da centralização da experiência de uso.
