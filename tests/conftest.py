"""Global fixtures for PVOutput Publisher integration."""
import pytest

# This plugin provides the `hass` fixture and other HA testing utilities
pytest_plugins = "pytest_homeassistant_custom_component"

@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations defined in the test dir."""
    # This forces the HA test instance to load your code from custom_components/
    yield
