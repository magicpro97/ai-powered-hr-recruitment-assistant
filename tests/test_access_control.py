# Third-party imports
import pytest

# Local application imports
from backend.access_control import Viewer, can_view_resource, require_viewable


def test_public_resource_is_viewable_by_anonymous_viewer():
    assert can_view_resource(Viewer(), {"owner_user_id": "owner", "is_public": True})


def test_private_resource_is_viewable_only_by_owner_or_admin():
    resource = {"owner_user_id": "owner", "is_public": False}

    assert can_view_resource(Viewer(user_id="owner"), resource)
    assert can_view_resource(Viewer(user_id="admin", is_admin=True), resource)
    assert not can_view_resource(Viewer(user_id="other"), resource)


def test_missing_owner_metadata_fails_closed():
    assert not can_view_resource(Viewer(is_admin=True), {"is_public": False})
    with pytest.raises(PermissionError):
        require_viewable(Viewer(user_id="owner"), {"is_public": False})


def test_system_owned_private_resource_is_not_implicit_public_access():
    resource = {"owner_user_id": "system", "is_public": False}

    assert not can_view_resource(Viewer(), resource)
    assert not can_view_resource(Viewer(user_id="other"), resource)
    assert can_view_resource(Viewer(user_id="system"), resource)
    assert can_view_resource(Viewer(is_admin=True), resource)
