"""Local Work lacks Landlock; GitHub must exercise the real profile without skips."""

import os

import pytest

from app.intelligence.confinement import available


def require_confinement():
    if not available():
        if os.environ.get("GITHUB_ACTIONS") == "true":
            pytest.fail("CI must provide real Landlock ABI >=3 and libseccomp")
        pytest.skip("Local runtime does not provide Linux Landlock; kernel checks required in CI")
