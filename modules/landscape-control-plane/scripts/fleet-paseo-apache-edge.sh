#!/usr/bin/env bash
# omni::fleet-paseo-apache-edge v1.1.0
# Configuracao do Atius Admin Edge SSO (:8210) e Apache Edge Gateway no atius-srv-1 para o Paseo Hub (10.14.1.14:37845)
# Modelo PM2 Canônico: Same-Host App-Local Login Shell em https://paseo.atius.io/login e https://paseo.atius.com.br/login
set -euo pipefail

HOST=$(hostname 2>/dev/null || cat /etc/hostname)
if [[ ! "$HOST" =~ srv-1 ]]; then
  echo "SKIP: fleet-paseo-apache-edge roda exclusivamente no atius-srv-1 (atual: $HOST)"
  exit 0
fi

echo "== [configuring atius admin edge sso for paseo] =="

# 1. Atualizar /etc/atius/atius-admin-edge-gateway.json
EDGE_CONFIG="/etc/atius/atius-admin-edge-gateway.json"
if [ -f "$EDGE_CONFIG" ]; then
  node -e '
  const fs = require("fs");
  const cfgPath = process.argv[1];
  const cfg = JSON.parse(fs.readFileSync(cfgPath, "utf8"));
  cfg.sites = cfg.sites || {};
  cfg.sites["paseo.atius.com.br"] = {
    publicOrigin: "https://paseo.atius.com.br",
    appName: "Paseo",
    authMode: "none",
    preserveHost: true,
    upstream: "http://10.14.1.14:37845",
    allowedEmails: [
      "giovannimunizds@gmail.com"
    ],
    requireAdmin: true
  };
  cfg.sites["paseo.atius.io"] = {
    aliasOf: "paseo.atius.com.br",
    publicOrigin: "https://paseo.atius.io",
    appName: "Paseo",
    allowedEmails: [
      "giovannimunizds@gmail.com"
    ],
    requireAdmin: true
  };
  fs.writeFileSync(cfgPath, JSON.stringify(cfg, null, 2), "utf8");
  console.log("Updated " + cfgPath + " for Paseo Hub at 10.14.1.14:37845");
  ' "$EDGE_CONFIG"
else
  echo "WARN: $EDGE_CONFIG not found on $HOST"
fi

# 2. Atualizar binario /opt/atius/atius-admin-edge-gateway.js se houver no repo local
REPO_GATEWAY="/home/ubuntu/GitHub/omni-srv-admin/modules/atius-admin-edge-sso/scripts/atius-admin-edge-gateway.js"
if [ -f "$REPO_GATEWAY" ]; then
  cp -f "$REPO_GATEWAY" /opt/atius/atius-admin-edge-gateway.js
  chmod 755 /opt/atius/atius-admin-edge-gateway.js
fi

# 3. Reiniciar o servico do Edge Gateway se ativo
if systemctl is-enabled atius-admin-edge-gateway >/dev/null 2>&1; then
  systemctl restart atius-admin-edge-gateway
  sleep 1
  echo "atius-admin-edge-gateway status: $(systemctl is-active atius-admin-edge-gateway)"
fi

echo "== [configuring apache reverse proxy to edge gateway :8210] =="

# 3. Habilitar modulos necessarios do Apache
a2enmod proxy proxy_http proxy_wstunnel rewrite headers ssl >/dev/null 2>&1 || true

# 4. VHost paseo.atius.io (Proxy para Edge Gateway :8210)
cat << 'EOF' > /etc/apache2/sites-available/paseo.atius.io.conf
<VirtualHost *:80>
    ServerName paseo.atius.io
    RewriteEngine On
    RewriteRule ^ https://%{HTTP_HOST}%{REQUEST_URI} [R=301,L]
</VirtualHost>

<IfModule mod_ssl.c>
<VirtualHost *:443>
    ServerName paseo.atius.io

    SSLEngine on
    SSLCertificateFile /etc/ssl/cloudflare/atius.io.pem
    SSLCertificateKeyFile /etc/ssl/cloudflare/atius.io.key

    ProxyPreserveHost On
    ProxyRequests Off
    RequestHeader set X-Forwarded-Proto "https"
    RequestHeader set X-Forwarded-Port "443"
    RequestHeader set X-Forwarded-Ssl "on"
    RequestHeader set X-Forwarded-For %{REMOTE_ADDR}s

    # WebSocket Upgrade para o Atius Admin Edge Gateway
    RewriteEngine On
    RewriteCond %{HTTP:Upgrade} =websocket [NC]
    RewriteCond %{HTTP:Connection} upgrade [NC]
    RewriteRule ^/(.*) ws://127.0.0.1:8210/$1 [P,L]

    # HTTP Reverse Proxy para o Atius Admin Edge Gateway
    ProxyPass / http://127.0.0.1:8210/ retry=0 timeout=120
    ProxyPassReverse / http://127.0.0.1:8210/

    ErrorLog ${APACHE_LOG_DIR}/paseo-io-error.log
    CustomLog ${APACHE_LOG_DIR}/paseo-io-access.log combined
</VirtualHost>
</IfModule>
EOF

# 5. VHost paseo.atius.com.br (Proxy para Edge Gateway :8210)
cat << 'EOF' > /etc/apache2/sites-available/paseo.atius.com.br.conf
<VirtualHost *:80>
    ServerName paseo.atius.com.br
    RewriteEngine On
    RewriteRule ^ https://%{HTTP_HOST}%{REQUEST_URI} [R=301,L]
</VirtualHost>

<IfModule mod_ssl.c>
<VirtualHost *:443>
    ServerName paseo.atius.com.br

    SSLEngine on
    SSLCertificateFile /etc/ssl/cloudflare/atius.com.br.pem
    SSLCertificateKeyFile /etc/ssl/cloudflare/atius.com.br.key

    ProxyPreserveHost On
    ProxyRequests Off
    RequestHeader set X-Forwarded-Proto "https"
    RequestHeader set X-Forwarded-Port "443"
    RequestHeader set X-Forwarded-Ssl "on"
    RequestHeader set X-Forwarded-For %{REMOTE_ADDR}s

    # WebSocket Upgrade para o Atius Admin Edge Gateway
    RewriteEngine On
    RewriteCond %{HTTP:Upgrade} =websocket [NC]
    RewriteCond %{HTTP:Connection} upgrade [NC]
    RewriteRule ^/(.*) ws://127.0.0.1:8210/$1 [P,L]

    # HTTP Reverse Proxy para o Atius Admin Edge Gateway
    ProxyPass / http://127.0.0.1:8210/ retry=0 timeout=120
    ProxyPassReverse / http://127.0.0.1:8210/

    ErrorLog ${APACHE_LOG_DIR}/paseo-combr-error.log
    CustomLog ${APACHE_LOG_DIR}/paseo-combr-access.log combined
</VirtualHost>
</IfModule>
EOF

# 6. Habilitar vhosts
a2ensite paseo.atius.io.conf paseo.atius.com.br.conf >/dev/null 2>&1

# 7. Validar sintaxe Apache
apachectl configtest

# 8. Recarregar Apache com seguranca
systemctl reload apache2

echo "== [verification] =="
echo "apache_status=$(systemctl is-active apache2)"
echo "edge_gateway_status=$(systemctl is-active atius-admin-edge-gateway 2>/dev/null || echo 'not-systemd')"
echo "RESULT: OK - Atius SSO e Apache Edge Gateway configurados para Paseo"
