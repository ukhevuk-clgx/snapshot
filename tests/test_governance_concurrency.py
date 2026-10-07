import unittest
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import Mock, patch

import requests

from collectors.governance_dependencies import GovernanceDependenciesCollector
from utils.jira_client import JiraClient


class GovernanceConcurrencyTests(unittest.TestCase):
    def test_parallel_collection_preserves_order_and_skips_archived(self):
        barrier = Barrier(4)
        client = Mock()

        def get_optional(endpoint):
            if endpoint.endswith("/permissionscheme"):
                barrier.wait(timeout=5)
            return {"id": endpoint, "name": endpoint}

        client.get_optional.side_effect = get_optional
        projects = [{"id": str(i), "key": f"P{i}"} for i in range(4)]
        projects.insert(1, {"id": "99", "key": "ARC", "archived": True})
        mappings = GovernanceDependenciesCollector(client, max_workers=4).collect(projects)

        for rows in mappings:
            self.assertEqual([row["projectKey"] for row in rows], ["P0", "P1", "P2", "P3"])
        self.assertEqual(client.get_optional.call_count, 12)
        self.assertFalse(any("ARC" in call.args[0] for call in client.get_optional.call_args_list))

    def test_http_errors_are_not_hidden(self):
        client = Mock()
        response = Mock(status_code=403)
        client.get_optional.side_effect = requests.HTTPError(response=response)
        with self.assertRaises(requests.HTTPError):
            GovernanceDependenciesCollector(client).collect([{"key": "LIVE"}])

    def test_optional_missing_schemes_remain_absent(self):
        client = Mock()
        client.get_optional.return_value = None
        result = GovernanceDependenciesCollector(client, max_workers=1).collect([{"key": "LIVE"}])
        self.assertEqual(result, ([], [], []))
        self.assertEqual(client.get_optional.call_count, 3)

    def test_invalid_worker_count(self):
        for count in (0, -1, "4", 1.5):
            with self.subTest(count=count), self.assertRaises(ValueError):
                GovernanceDependenciesCollector(Mock(), max_workers=count)


class JiraClientConcurrencyTests(unittest.TestCase):
    def test_sessions_are_thread_local_reused_and_closed(self):
        sessions = []
        barrier = Barrier(4)

        def create_session():
            session = Mock()
            response = Mock(status_code=200, content=b"{}")
            response.json.return_value = {}
            session.get.return_value = response
            sessions.append(session)
            return session

        def collect(client):
            first = client._get_session()
            barrier.wait(timeout=5)
            client.get("/test")
            client.get("/test")
            return first, client._get_session()

        with patch("utils.jira_client.requests.Session", side_effect=create_session):
            with JiraClient() as client:
                with ThreadPoolExecutor(max_workers=4) as executor:
                    results = list(executor.map(collect, [client] * 4))
                self.assertEqual(len(sessions), 5)
                self.assertEqual(len({id(first) for first, _ in results}), 4)
                for first, second in results:
                    self.assertIs(first, second)
                    self.assertEqual(first.get.call_count, 2)
                    self.assertIsNot(first, client.session)
                for session in sessions:
                    session.close.assert_not_called()
            for session in sessions:
                session.close.assert_called_once()

    def test_rate_limit_retry_is_preserved(self):
        limited = Mock(status_code=429, headers={"Retry-After": "0"}, url="https://example.test/test")
        success = Mock(status_code=200, content=b"{}")
        success.json.return_value = {"id": 1}
        with patch("utils.jira_client.requests.Session") as factory, patch("utils.jira_client.time.sleep") as sleep:
            factory.return_value.get.side_effect = [limited, success]
            with JiraClient() as client:
                self.assertEqual(client.get("/test"), {"id": 1})
            self.assertEqual(factory.return_value.get.call_count, 2)
            sleep.assert_called_once_with(0)


if __name__ == "__main__":
    unittest.main()
