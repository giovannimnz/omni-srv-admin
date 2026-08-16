# 2026-08-01 atius sso full fleet live revalidation

Status: PASS.


- evidence dir: /home/ubuntu/GitHub/omni-srv-admin/docs/evidence/atius-sso/2026-08-01-full-fleet-live-20260731-235410
- totals: sites=12, cycles=24, screenshots=96
- proof scope: hostLocalLifecycle=True, centralOidcFlow=False
- visual baseline primary: /home/ubuntu/Imagens/Prints/sso-ssh-base-model.png
- visual baseline workspace copy: /home/ubuntu/GitHub/Prints/sso-ssh-base-model.png
- visual baseline sha256: 89c12b9f0d310c541e8fa62b7cc61bfc71d94ff2b6d314e3cc09b8bf5a2ad303
- reusable visual reference pack: /home/ubuntu/GitHub/omni-srv-admin/docs/evidence/atius-sso/2026-07-31-visual-reference-v2
- async read-only triage after the run: no artifact evidence of current fleet-wide runtime failure; main residual risk is harness/browser-state debt, especially per-cycle cookie clearing.
- async ATS/VPN transcript corroboration: live VPN `/login` HTML stayed host-local (`/api/auth/login`, no `sso.atius.com.br` string in body); remaining risk from that lane is source durability in ATS SSO files, not a demonstrated runtime redirect regression.

## Per-site results
- sso: PASS; entry=https://sso.atius.com.br/ ; login=https://sso.atius.com.br/login ; auth=https://sso.atius.com.br/login ; logout=https://sso.atius.com.br/login ; screenshots=8
- ssh: PASS; entry=https://ssh.atius.com.br/ ; login=https://ssh.atius.com.br/login ; auth=https://ssh.atius.com.br/compute ; logout=https://ssh.atius.com.br/login ; screenshots=8
- rdp: PASS; entry=https://rdp.atius.com.br/ ; login=https://rdp.atius.com.br/login ; auth=https://rdp.atius.com.br/giovanni-w11-pc ; logout=https://rdp.atius.com.br/login ; screenshots=8
- oci: PASS; entry=https://oci.atius.com.br/ ; login=https://oci.atius.com.br/login ; auth=https://oci.atius.com.br/ ; logout=https://oci.atius.com.br/login ; screenshots=8
- talk: PASS; entry=https://talk.atius.com.br/ ; login=https://talk.atius.com.br/login ; auth=https://talk.atius.com.br/ ; logout=https://talk.atius.com.br/login ; screenshots=8
- admin-talk: PASS; entry=https://admin.talk.atius.com.br/ ; login=https://admin.talk.atius.com.br/login ; auth=https://admin.talk.atius.com.br/ ; logout=https://admin.talk.atius.com.br/login ; screenshots=8
- remote: PASS; entry=https://remote.atius.com.br/ ; login=https://remote.atius.com.br/login ; auth=https://remote.atius.com.br/mt5/1/ ; logout=https://remote.atius.com.br/login ; screenshots=8
- grafana: PASS; entry=https://grafana.atius.com.br/ ; login=https://grafana.atius.com.br/login ; auth=https://grafana.atius.com.br/d/vkQ0UHxik/coredns ; logout=https://grafana.atius.com.br/login ; screenshots=8
- portainer: PASS; entry=https://portainer.atius.com.br/ ; login=https://portainer.atius.com.br/login ; auth=https://portainer.atius.com.br/ ; logout=https://portainer.atius.com.br/login ; screenshots=8
- docker: PASS; entry=https://docker.atius.com.br/ ; login=https://docker.atius.com.br/login ; auth=https://docker.atius.com.br/ ; logout=https://docker.atius.com.br/login ; screenshots=8
- vpn: PASS; entry=https://vpn.atius.com.br/ ; login=https://vpn.atius.com.br/login ; auth=https://vpn.atius.com.br/ ; logout=https://vpn.atius.com.br/login ; screenshots=8
- adguard: PASS; entry=https://adguard.atius.com.br/ ; login=https://adguard.atius.com.br/login ; auth=https://adguard.atius.com.br/ ; logout=https://adguard.atius.com.br/login ; screenshots=8
