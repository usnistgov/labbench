import pytest

import labbench as lb

# %% known faults, recorded in xfail-audit.md


@pytest.mark.xfail(
    strict=True,
    reason='Host.open (_host.py:293-295) binds a local named repo, so the except clause '
    'repo.NotGitRepository evaluates the unbound local instead of the dulwich.repo module',
)
def test_host_opens_outside_a_git_repository(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    host = lb._host.Host()
    with host:
        assert host.backend['repo'] is None
        assert host.git_commit_id is None
