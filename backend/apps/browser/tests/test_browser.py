from unittest.mock import MagicMock

import pytest

from apps.browser import actions
from apps.browser.schemas import PageElement, PageSnapshot
from apps.common.exceptions import BrowserError

pytestmark = pytest.mark.django_db


class TestSchemas:
    def test_page_snapshot_parses_realistic_payload(self):
        raw = [
            {"element_id": "tia-0", "tag": "input", "type": "email", "name": "email",
             "label": "Email address", "placeholder": "", "href": "", "value": "", "visible": True, "options": []},
            {"element_id": "tia-1", "tag": "select", "type": "", "name": "country",
             "label": "Country", "placeholder": "", "href": "", "value": "", "visible": True,
             "options": ["US", "CA", "UK"]},
        ]
        snapshot = PageSnapshot(url="https://example.com", title="Register", elements=[PageElement(**e) for e in raw])
        assert len(snapshot.elements) == 2
        assert snapshot.elements[1].options == ["US", "CA", "UK"]


class TestActionsContract:
    """
    Verifies the calling contract against a real Playwright API surface
    (mocked, since no browser binary is available in CI-less environments
    without `playwright install`) — confirms the RIGHT Playwright methods
    get called with the RIGHT arguments, and that a stale element_id fails
    safely instead of crashing.
    """

    @pytest.fixture
    def mock_session(self):
        session = MagicMock()
        locator = MagicMock()
        locator.count.return_value = 1
        locator.first = locator
        session.page.locator.return_value = locator
        session.page.evaluate.return_value = []
        session.page.url = "https://example.com"
        session.page.title.return_value = "Example"
        return session, locator

    def test_click_calls_locator_click(self, mock_session):
        session, locator = mock_session
        result = actions.browser_click(session, "tia-0")
        assert result.success is True
        locator.click.assert_called_once()

    def test_type_calls_locator_fill_with_text(self, mock_session):
        session, locator = mock_session
        actions.browser_type(session, "tia-0", "hello@example.com")
        locator.fill.assert_called_once_with("hello@example.com")

    def test_select_calls_locator_select_option(self, mock_session):
        session, locator = mock_session
        actions.browser_select(session, "tia-1", "CA")
        locator.select_option.assert_called_once_with("CA")

    def test_stale_element_id_raises_browser_error(self, mock_session):
        session, locator = mock_session
        locator.count.return_value = 0
        with pytest.raises(BrowserError):
            actions.browser_click(session, "stale-id")
