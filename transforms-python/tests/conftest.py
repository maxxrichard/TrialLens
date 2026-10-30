from __future__ import annotations

import pytest


@pytest.fixture(scope="session")
def spark():
    from triallens.local.spark import get_local_spark

    session = get_local_spark("triallens-tests")
    yield session
    session.stop()


SALT = "unit-test-salt"
