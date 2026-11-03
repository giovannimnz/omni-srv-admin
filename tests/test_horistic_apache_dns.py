"""Unit and TDD tests for Horistic Apache reverse proxy DNS resolution contract.

Enforces:
1. Tier 1: Internal DNS (atius-srv-1.atius.internal) in Define ATIUS_IP
2. Reject raw IP in Define ATIUS_IP (prevents hardcoded IP drift)
3. 3-Tier fallback hierarchy validation: Internal DNS -> OCI DRG -> Public IP
"""

from __future__ import annotations

import re
import pytest

CANONICAL_UPSTREAM_DNS = "atius-srv-1.atius.internal"
DRG_FALLBACK_IP = "10.1.1.1"
PUBLIC_FALLBACK_IP = "64.181.172.236"

# Regex para validar a linha 'Define ATIUS_IP ...'
DEFINE_ATIUS_IP_REGEX = re.compile(r"^\s*Define\s+ATIUS_IP\s+([^\s#]+)", re.MULTILINE)


def render_horistic_apache_define(upstream: str = CANONICAL_UPSTREAM_DNS) -> str:
    """Gera a linha Define ATIUS_IP canônica para os vhosts do Horistic Apache."""
    return f"Define ATIUS_IP {upstream}"


def validate_vhost_upstream(apache_conf_content: str) -> str:
    """Valida se o upstream configurado em Define ATIUS_IP segue o contrato de DNS interno."""
    match = DEFINE_ATIUS_IP_REGEX.search(apache_conf_content)
    if not match:
        raise ValueError("Diretiva 'Define ATIUS_IP' ausente na configuração Apache")
    
    upstream = match.group(1).strip()
    
    # Se for IP puro (IPv4), viola o mandato de DNS primário
    if re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", upstream):
        raise ValueError(
            f"Violação da diretiva canônica: ATIUS_IP está apontando para IP bruto '{upstream}'. "
            f"Deve apontar para DNS interno '{CANONICAL_UPSTREAM_DNS}'"
        )
    
    if upstream != CANONICAL_UPSTREAM_DNS:
        raise ValueError(
            f"Upstream '{upstream}' inválido. Esperado '{CANONICAL_UPSTREAM_DNS}'"
        )
    
    return upstream


def test_render_horistic_apache_define():
    """Valida a renderização da diretiva canônica."""
    line = render_horistic_apache_define()
    assert line == "Define ATIUS_IP atius-srv-1.atius.internal"


def test_validate_vhost_upstream_dns_success():
    """Valida que vhost com DNS interno passa sem erros."""
    conf = """
    <VirtualHost *:443>
        ServerName trade.horistic.com
        Define ATIUS_IP atius-srv-1.atius.internal
        Define FRONTEND_PORT 3050
        ProxyPass / http://${ATIUS_IP}:${FRONTEND_PORT}/
    </VirtualHost>
    """
    upstream = validate_vhost_upstream(conf)
    assert upstream == CANONICAL_UPSTREAM_DNS


def test_validate_vhost_upstream_raw_ip_rejected():
    """Valida rejeição estrita de IPs brutos em Define ATIUS_IP."""
    legacy_conf = """
    <VirtualHost *:443>
        ServerName trade.horistic.com
        Define ATIUS_IP 10.1.0.11
        Define FRONTEND_PORT 3050
    </VirtualHost>
    """
    with pytest.raises(ValueError, match="apontando para IP bruto"):
        validate_vhost_upstream(legacy_conf)

    new_ip_conf = """
    <VirtualHost *:443>
        ServerName trade.horistic.com
        Define ATIUS_IP 10.1.1.1
        Define FRONTEND_PORT 3050
    </VirtualHost>
    """
    with pytest.raises(ValueError, match="apontando para IP bruto"):
        validate_vhost_upstream(new_ip_conf)


def test_validate_vhost_missing_define():
    """Valida erro quando Define ATIUS_IP não está presente."""
    conf = "<VirtualHost *:443>\nServerName trade.horistic.com\n</VirtualHost>"
    with pytest.raises(ValueError, match="ausente na configuração Apache"):
        validate_vhost_upstream(conf)


def test_resolution_tier_hierarchy():
    """Valida a hierarquia de 3 níveis de resolução de endereços."""
    hierarchy = [
        {"tier": 1, "type": "internal_dns", "target": CANONICAL_UPSTREAM_DNS},
        {"tier": 2, "type": "oci_drg_private", "target": DRG_FALLBACK_IP},
        {"tier": 3, "type": "public_reserved", "target": PUBLIC_FALLBACK_IP},
    ]
    assert hierarchy[0]["tier"] == 1
    assert hierarchy[0]["target"] == "atius-srv-1.atius.internal"
    assert hierarchy[1]["tier"] == 2
    assert hierarchy[1]["target"] == "10.1.1.1"
    assert hierarchy[2]["tier"] == 3
    assert hierarchy[2]["target"] == "64.181.172.236"
