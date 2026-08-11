from machinery.errors import ActiveWorkspaceRequiredError, MachineryError


def test_active_workspace_required_error_has_stable_contract() -> None:
    error = ActiveWorkspaceRequiredError()

    assert isinstance(error, MachineryError)
    assert not isinstance(error, ValueError)
    assert error.error_code == "active_workspace_required"
    assert error.message == "Admission did not resolve an active workspace."
    assert str(error) == error.message
    assert error.details == ()
    assert not hasattr(error, "code")
