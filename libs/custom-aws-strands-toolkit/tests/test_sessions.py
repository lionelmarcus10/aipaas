"""Test SessionManager."""

import tempfile

from cast.sessions import SessionManager


def test_session_manager_list_empty():
    with tempfile.TemporaryDirectory() as d:
        sm = SessionManager(storage_dir=d)
        assert sm.list() == []


def test_session_manager_dir_creation():
    with tempfile.TemporaryDirectory() as d:
        storage = f"{d}/sessions"
        sm = SessionManager(storage_dir=storage)
        # get_manager should create the dir
        sm.get_manager("test-session")
        import os
        assert os.path.isdir(storage)
