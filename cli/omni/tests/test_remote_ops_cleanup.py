"""Regression tests for the Podman-only fleet cleanup policy."""

from omni import remote_ops


def test_storage_audit_is_podman_only():
    script = remote_ops._storage_audit_script()

    assert "podman system df" in script
    assert "docker" not in script.lower()
    assert "/var/lib/rancher/k3s" not in script


def test_autoclean_is_podman_only_and_preserves_tagged_images():
    script = remote_ops._autoclean_script(dry_run=False, include_volumes=False)

    assert "podman image prune -f" in script
    assert "podman image prune -af" not in script
    assert "podman volume prune -f" in script
    assert 'INCLUDE_VOLUMES=0' in script
    assert "docker" not in script.lower()
    assert "crictl" not in script
    assert "k3s ctr" not in script
    assert "/var/lib/rancher/k3s" not in script


def test_autoclean_requires_explicit_volume_opt_in():
    default_script = remote_ops._autoclean_script(
        dry_run=False, include_volumes=False
    )
    opted_in_script = remote_ops._autoclean_script(
        dry_run=False, include_volumes=True
    )

    assert 'INCLUDE_VOLUMES=0' in default_script
    assert 'INCLUDE_VOLUMES=1' in opted_in_script
