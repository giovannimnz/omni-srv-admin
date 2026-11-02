#!/usr/bin/env bash
# omni::fleet-paseo-apache-edge v1.0.0
# Configuracao do Edge Gateway Apache no atius-srv-1 para o Paseo Hub (10.14.1.14:37845)
# Dual-Domain: paseo.atius.io e paseo.atius.com.br com WebSocket Upgrade
set -euo pipefail

HOST=$(hostname 2>/dev/null || cat /etc/hostname)
if [[ ! "$HOST" =~ srv-1 ]]; then
  echo "SKIP: fleet-paseo-apache-edge roda exclusivamente no atius-srv-1 (atual: $HOST)"
  exit 0
fi

echo "== [configuring apache edge gateway for paseo] =="

# 1. Habilitar modulos necessarios
a2enmod proxy proxy_http proxy_wstunnel rewrite headers ssl >/dev/null 2>&1 || true

# 2. VHost paseo.atius.io
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
    RequestHeader set X-Forwarded-Proto "https"
    RequestHeader set X-Forwarded-Port "443"
    RequestHeader set X-Forwarded-Ssl "on"
    RequestHeader set X-Forwarded-For %{REMOTE_ADDR}s
    RequestHeader set Origin "paseo://app"

    # WebSocket Upgrade
    RewriteEngine On
    RewriteCond %{HTTP:Upgrade} =websocket [NC]
    RewriteRule ^/(.*) ws://10.14.1.14:37845/$1 [P,L]

    # HTTP Reverse Proxy para o Hub Central
    ProxyPass / http://10.14.1.14:37845/ retry=0 timeout=120
    ProxyPassReverse / http://10.14.1.14:37845/

    ErrorLog ${APACHE_LOG_DIR}/paseo-io-error.log
    CustomLog ${APACHE_LOG_DIR}/paseo-io-access.log combined
</VirtualHost>
</IfModule>
EOF

# 3. VHost paseo.atius.com.br
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
    RequestHeader set X-Forwarded-Proto "https"
    RequestHeader set X-Forwarded-Port "443"
    RequestHeader set X-Forwarded-Ssl "on"
    RequestHeader set X-Forwarded-For %{REMOTE_ADDR}s
    RequestHeader set Origin "paseo://app"

    # WebSocket Upgrade
    RewriteEngine On
    RewriteCond %{HTTP:Upgrade} =websocket [NC]
    RewriteRule ^/(.*) ws://10.14.1.14:37845/$1 [P,L]

    # HTTP Reverse Proxy para o Hub Central
    ProxyPass / http://10.14.1.14:37845/ retry=0 timeout=120
    ProxyPassReverse / http://10.14.1.14:37845/

    ErrorLog ${APACHE_LOG_DIR}/paseo-combr-error.log
    CustomLog ${APACHE_LOG_DIR}/paseo-combr-access.log combined
</VirtualHost>
</IfModule>
EOF

# 4. Habilitar vhosts
a2ensite paseo.atius.io.conf paseo.atius.com.br.conf >/dev/null 2>&1

# 5. Validar sintaxe
apachectl configtest

# 6. Recarregar Apache com seguranca
systemctl reload apache2

echo "== [verification] =="
echo "apache_status=$(systemctl is-active apache2)"
echo "RESULT: OK - Apache Edge Gateway provisionado para Paseo"
