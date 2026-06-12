"""Tests for list_project_trackers tool."""

import pytest
from unittest.mock import Mock, patch

from redmine_mcp_server.redmine_handler import list_project_trackers


class TestListProjectTrackers:
    @pytest.fixture
    def mock_redmine(self):
        with patch("redmine_mcp_server.redmine_handler.redmine") as mock:
            yield mock

    def _make_tracker(self, tracker_id, name):
        t = Mock()
        t.id = tracker_id
        t.name = name
        return t

    def _make_project(self, trackers):
        project = Mock()
        project.trackers = trackers
        return project

    @pytest.mark.asyncio
    async def test_returns_trackers_for_project(self, mock_redmine):
        trackers = [
            self._make_tracker(1, "Bug"),
            self._make_tracker(2, "Feature"),
            self._make_tracker(3, "Support"),
        ]
        mock_redmine.project.get.return_value = self._make_project(trackers)

        result = await list_project_trackers("my-project")

        assert result == [
            {"id": 1, "name": "Bug"},
            {"id": 2, "name": "Feature"},
            {"id": 3, "name": "Support"},
        ]

    @pytest.mark.asyncio
    async def test_fetches_project_with_trackers_include(self, mock_redmine):
        mock_redmine.project.get.return_value = self._make_project([])

        await list_project_trackers("my-project")

        mock_redmine.project.get.assert_called_once_with("my-project", include="trackers")

    @pytest.mark.asyncio
    async def test_accepts_integer_project_id(self, mock_redmine):
        mock_redmine.project.get.return_value = self._make_project(
            [self._make_tracker(1, "Bug")]
        )

        result = await list_project_trackers(42)

        mock_redmine.project.get.assert_called_once_with(42, include="trackers")
        assert result[0]["id"] == 1

    @pytest.mark.asyncio
    async def test_empty_trackers_returns_empty_list(self, mock_redmine):
        mock_redmine.project.get.return_value = self._make_project([])

        result = await list_project_trackers("empty-project")

        assert result == []

    @pytest.mark.asyncio
    async def test_missing_trackers_attribute_returns_empty_list(self, mock_redmine):
        project = Mock(spec=[])  # no attributes at all
        mock_redmine.project.get.return_value = project

        result = await list_project_trackers("some-project")

        assert result == []

    @pytest.mark.asyncio
    async def test_each_tracker_has_id_and_name(self, mock_redmine):
        trackers = [self._make_tracker(5, "Task")]
        mock_redmine.project.get.return_value = self._make_project(trackers)

        result = await list_project_trackers("proj")

        assert set(result[0].keys()) == {"id", "name"}

    @pytest.mark.asyncio
    async def test_returns_error_on_project_not_found(self, mock_redmine):
        from redminelib.exceptions import ResourceNotFoundError

        mock_redmine.project.get.side_effect = ResourceNotFoundError()

        result = await list_project_trackers("nonexistent")

        assert isinstance(result, list)
        assert len(result) == 1
        assert "error" in result[0]
        assert "nonexistent" in result[0]["error"]

    @pytest.mark.asyncio
    async def test_returns_error_on_auth_failure(self, mock_redmine):
        from redminelib.exceptions import AuthError

        mock_redmine.project.get.side_effect = AuthError()

        result = await list_project_trackers("proj")

        assert isinstance(result, list)
        assert "error" in result[0]

    @pytest.mark.asyncio
    async def test_returns_error_on_connection_error(self, mock_redmine):
        from requests.exceptions import ConnectionError as RequestsConnectionError

        mock_redmine.project.get.side_effect = RequestsConnectionError()

        result = await list_project_trackers("proj")

        assert isinstance(result, list)
        assert "error" in result[0]
