# /etc/gitlab/gitlab.rb
# Configuração Governada do GitLab CE em atius-srv-4 (ARM64)
# Reverse Proxy: Apache Gateway atius-srv-1 (https://gitlab.atius.com.br e https://gitlab.atius.io)

external_url 'https://gitlab.atius.com.br'

# 1. Configuração de Nginx Interno (Proxy reverso local)
nginx['enable'] = true
nginx['listen_port'] = 8929
nginx['listen_https'] = false
letsencrypt['enable'] = false
nginx['proxy_set_headers'] = {
  "X-Forwarded-Proto" => "https",
  "X-Forwarded-Ssl" => "on",
  "Host" => "$http_host"
}
gitlab_rails['trusted_proxies'] = ['10.11.1.11', '127.0.0.1', '10.14.1.14', '137.131.190.161']

# 2. Otimização de Recursos & CPU Guardrail (<20%)
puma['worker_processes'] = 2
puma['min_threads'] = 1
puma['max_threads'] = 4
puma['per_worker_max_memory_mb'] = 1024
sidekiq['concurrency'] = 10
postgresql['shared_buffers'] = "256MB"
postgresql['max_connections'] = 100
prometheus_monitoring['enable'] = false
alertmanager['enable'] = false
node_exporter['enable'] = false
redis_exporter['enable'] = false
postgres_exporter['enable'] = false
gitlab_exporter['enable'] = false

# 3. Integração com SSO Atius / Keycloak OIDC
gitlab_rails['omniauth_enabled'] = true
gitlab_rails['omniauth_allow_single_sign_on'] = ['openid_connect']
gitlab_rails['omniauth_block_auto_created_users'] = false
gitlab_rails['omniauth_auto_link_user'] = ['openid_connect']
gitlab_rails['omniauth_providers'] = [
  {
    name: "openid_connect",
    label: "Atius SSO",
    args: {
      name: "openid_connect",
      scope: ["openid", "profile", "email"],
      response_type: "code",
      issuer: "https://auth.atius.com.br/realms/atius",
      discovery: true,
      client_auth_method: "basic",
      uid_field: "preferred_username",
      send_scope_to_token_endpoint: "false",
      client_options: {
        identifier: "gitlab",
        secret: "AtiusGitLabSecret2026!",
        redirect_uri: "https://gitlab.atius.com.br/users/auth/openid_connect/callback"
      }
    }
  }
]
