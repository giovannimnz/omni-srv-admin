# MT5 remote SSO auth

This module moves `https://remote.atius.com.br/mt5/<id>/` from Apache Basic Auth to the canonical ATS SSO cookie.

## Runtime contract

- Public host: `remote.atius.com.br`
- Auth cookie: `auth-token` on `.atius.com.br`
- Session verifier: `http://127.0.0.1:8015/v1/auth/me`
- SSO login: `https://sso.atius.com.br/login?return_to=<remote-url>`
- Local proxy: `http://127.0.0.1:8095`
- First route: `/mt5/1 -> http://10.1.1.3:6081`
- Required ATS permission: `can_access_trade`; `is_admin` also passes.

The proxy serves the existing noVNC static files from `/var/www/remote-mt5` after SSO validation and proxies `websockify`/fallback traffic to the configured upstream. It never forwards `Cookie` or `Authorization` to the MT5/noVNC container.

## Install

```bash
bash modules/mt5-remote-auth/scripts/install-mt5-remote-auth.sh
```

That installs and starts only the local service. It does not change Apache.

To cut over Apache after `sso.atius.com.br` is live and validated:

```bash
bash modules/mt5-remote-auth/scripts/install-mt5-remote-auth.sh --apply-apache
```

The Apache mode backs up `/etc/apache2/sites-available/remote.atius.com.br.conf`, runs `apache2ctl configtest`, and reloads Apache only after syntax passes.

## Add the next MT5 route

Add a route to `/etc/atius/mt5-remote-auth-proxy.json`:

```json
"2": {
  "basePath": "/mt5/2",
  "upstream": "http://10.1.1.4:6081",
  "requiredPermission": "can_access_trade",
  "staticRoot": "/var/www/remote-mt5"
}
```

Then restart:

```bash
sudo systemctl restart mt5-remote-auth-proxy.service
```

No new Apache Basic Auth block is needed for additional `/mt5/<id>` routes.
