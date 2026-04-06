from financeops.platform.services.rbac.permission_matrix import PERMISSIONS, ROLE_ALIASES


def test_permission_keys_are_normalized() -> None:
    for permission in PERMISSIONS:
        assert permission == permission.lower()
        assert permission.count(".") >= 1


def test_permission_entries_are_complete() -> None:
    for entry in PERMISSIONS.values():
        assert entry["module"]
        assert entry["roles"]
        assert isinstance(entry["entitlement_keys"], list)
        assert "feature_flag" in entry
        assert "runtime_roles" in entry


def test_role_aliases_cover_canonical_roles() -> None:
    expected_roles = {
        "platform_owner",
        "platform_admin",
        "tenant_owner",
        "tenant_admin",
        "tenant_manager",
        "tenant_member",
        "tenant_viewer",
    }
    assert set(ROLE_ALIASES) == expected_roles
