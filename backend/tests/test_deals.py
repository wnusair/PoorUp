import os
import sys
import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.engine import deals  # noqa: E402


def make_state():
    return {
        'players': [
            {'id': 1, 'username': 'Atlas', 'balance': 500.0},
            {'id': 2, 'username': 'Rival', 'balance': 500.0},
        ],
        'deals': [],
        'settings': {'deals_enabled': True},
    }


class DealEngineTests(unittest.TestCase):
    def test_request_deal_termination_records_first_request(self):
        deal = SimpleNamespace(
            id=44,
            match_id=77,
            proposer_id=1,
            counterparty_id=2,
            status=deals.DEAL_STATUS_ACCEPTED,
            clauses=[],
            termination_requested_by_id=None,
            termination_requested_at=None,
            last_updated_at=None,
        )

        with patch.object(deals, '_safe_commit', return_value=True) as safe_commit, patch.object(
            deals,
            'attach_deals_snapshot',
            side_effect=lambda game_state, *_args: {**game_state, 'deals': [{'id': 44}]},
        ) as attach_deals_snapshot:
            next_state, termination_status, error = deals.request_deal_termination(deal, 1, make_state())

        self.assertIsNone(error)
        self.assertEqual(termination_status, 'requested')
        self.assertEqual(deal.termination_requested_by_id, 1)
        self.assertIsInstance(deal.termination_requested_at, datetime)
        self.assertEqual(next_state['deals'], [{'id': 44}])
        safe_commit.assert_called_once()
        attach_deals_snapshot.assert_called_once()

    def test_request_deal_termination_requires_second_party_confirmation(self):
        deal = SimpleNamespace(
            id=44,
            match_id=77,
            proposer_id=1,
            counterparty_id=2,
            status=deals.DEAL_STATUS_ACCEPTED,
            clauses=[],
            termination_requested_by_id=1,
            termination_requested_at=datetime.utcnow(),
            last_updated_at=None,
        )

        terminated_state = {'players': make_state()['players'], 'deals': []}
        with patch.object(deals, 'terminate_deal', return_value=terminated_state) as terminate_deal, patch.object(
            deals,
            'attach_deals_snapshot',
            side_effect=lambda game_state, *_args: game_state,
        ) as attach_deals_snapshot:
            next_state, termination_status, error = deals.request_deal_termination(deal, 2, make_state())

        self.assertIsNone(error)
        self.assertEqual(termination_status, 'terminated')
        self.assertIs(next_state, terminated_state)
        terminate_deal.assert_called_once_with(deal, unittest.mock.ANY, status=deals.DEAL_STATUS_CANCELLED)
        attach_deals_snapshot.assert_called_once_with(terminated_state, 77)

    def test_serialize_deal_includes_termination_request_fields(self):
        deal = SimpleNamespace(
            id=44,
            match_id=77,
            proposer_id=1,
            counterparty_id=2,
            status=deals.DEAL_STATUS_ACCEPTED,
            title='Revenue Shield',
            created_at=None,
            responded_at=None,
            accepted_at=None,
            cancelled_at=None,
            last_updated_at=None,
            proposal_version=1,
            counter_of_deal_id=None,
            termination_requested_by_id=2,
            termination_requested_at=datetime(2026, 4, 6, 12, 0, 0),
            clauses=[],
        )

        payload = deals.serialize_deal(
            deal,
            player_lookup={1: {'username': 'Atlas'}, 2: {'username': 'Rival'}},
        )

        self.assertEqual(payload['termination_requested_by_id'], 2)
        self.assertEqual(payload['termination_requested_by_name'], 'Rival')
        self.assertEqual(payload['termination_requested_at'], '2026-04-06T12:00:00')


if __name__ == '__main__':
    unittest.main()