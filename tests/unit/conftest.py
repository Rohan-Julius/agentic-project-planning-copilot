"""Unit test configuration (overrides root conftest to avoid app imports)."""
import pytest

# Unit tests for agents don't need the full app fixture
# They only use mocks and fixtures defined here
