"""Board planning regressions: no GitHub access or board writes."""

import unittest
from typing import Any
from unittest.mock import patch

import gh_board_sync as sync


def issue(*, state: str = "OPEN") -> dict[str, Any]:
    return {
        "number": 165,
        "state": state,
        "label_names": {"agent", "P1"},
        "milestone": "Пилот 5 тестеров",
    }


class IterationPlanningTests(unittest.TestCase):
    def test_no_active_iteration_preserves_iteration_and_syncs_other_fields(self) -> None:
        self.assertIsNone(sync.CURRENT_ITERATION_PREFIX)
        for previous in (None, "SFR-6 — завершена", "SFR-7 — план"):
            with self.subTest(previous=previous):
                plan = sync.plan_for(
                    issue(),
                    {"status": "Backlog", "priority": "P2", "iteration": previous},
                )
                self.assertEqual(plan, {"Status": ("Backlog", "Todo"), "Priority": ("P2", "P1")})

    def test_no_active_iteration_does_not_assign_new_item(self) -> None:
        with patch.object(sync, "CURRENT_ITERATION_PREFIX", None):
            self.assertEqual(
                sync.plan_for(issue(), None),
                {"Status": (None, "Todo"), "Priority": (None, "P1")},
            )

    def test_closed_issue_keeps_its_iteration_when_next_iteration_is_opened(self) -> None:
        with patch.object(sync, "CURRENT_ITERATION_PREFIX", "SFR-7"):
            self.assertEqual(
                sync.plan_for(
                    issue(state="CLOSED"),
                    {"status": "In Progress", "priority": "P2", "iteration": "SFR-6"},
                ),
                {"Status": ("In Progress", "Done"), "Priority": ("P2", "P1")},
            )

    def test_approved_iteration_still_requires_open_agent_issue_and_milestone(self) -> None:
        with patch.object(sync, "CURRENT_ITERATION_PREFIX", "SFR-7"):
            self.assertEqual(sync.target_iteration(issue()), "SFR-7")
            for change in (
                {"label_names": {"human", "P1"}},
                {"milestone": "Будущий этап"},
                {"state": "CLOSED"},
            ):
                with self.subTest(change=change):
                    self.assertIsNone(sync.target_iteration(issue() | change))


if __name__ == "__main__":
    unittest.main()
