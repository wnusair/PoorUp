import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.engine.trading import apply_trade_acceptance, validate_trade_proposal  # noqa: E402


def make_state():
    return {
        'players': [
            {'id': 1, 'username': 'Atlas', 'balance': 500.0, 'is_bankrupt': False},
            {'id': 2, 'username': 'Rival', 'balance': 350.0, 'is_bankrupt': False},
        ],
        'properties': [],
        'settings': {
            'trading_enabled': True,
            'lobbying_enabled': True,
            'deals_enabled': True,
        },
        'econ': {
            'gov_type': 'liberal_democracy',
        },
    }


class TradingEngineTests(unittest.TestCase):
    def test_validate_trade_proposal_rejects_government_unavailable_lobby_pledges(self):
        state = make_state()
        state['econ']['gov_type'] = 'social_democracy'
        state['settings']['government_type'] = 'social_democracy'
        payload = {
            'receiver_id': 2,
            'offered_money': 0.0,
            'requested_money': 0.0,
            'offered_props': [],
            'requested_props': [],
            'offered_lobby_pledges': [{'target': 'money_supply_expand', 'amount': 50.0}],
            'requested_lobby_pledges': [],
            'included_deal_drafts': [],
        }

        error = validate_trade_proposal(state, 1, payload)

        self.assertEqual(
            error,
            'This trade includes lobbying pledges that are not available under the current government.',
        )

    def test_validate_trade_proposal_counts_bundled_deal_escrows(self):
        state = make_state()
        payload = {
            'receiver_id': 2,
            'offered_money': 425.0,
            'requested_money': 0.0,
            'offered_props': [],
            'requested_props': [],
            'offered_lobby_pledges': [],
            'requested_lobby_pledges': [],
            'included_deal_drafts': [
                {
                    'title': 'Revenue Shield',
                    'counterparty_id': 2,
                    'clauses': [
                        {
                            'type': 'development_investment',
                            'grantor_id': 1,
                            'beneficiary_id': 2,
                            'scope': {'mode': 'all_grantor_properties'},
                            'config': {
                                'escrow_amount': 100.0,
                                'profit_share_percent': 0.35,
                                'max_payout': 150.0,
                            },
                            'deadline': {'metric': 'beneficiary_turns', 'initial': 2},
                        },
                    ],
                },
            ],
        }

        error = validate_trade_proposal(state, 1, payload)

        self.assertEqual(
            error,
            'Your offered cash, lobbying pledges, and bundled deal escrows exceed your balance.',
        )

    def test_apply_trade_acceptance_normalizes_bundled_deals_after_cash_moves(self):
        state = make_state()
        normalized_draft = {
            'title': 'Revenue Shield',
            'counterparty_id': 2,
            'clauses': [
                {
                    'type': 'development_investment',
                    'grantor_id': 1,
                    'beneficiary_id': 2,
                    'scope': {'mode': 'all_grantor_properties'},
                    'config': {
                        'escrow_amount': 300.0,
                        'profit_share_percent': 0.35,
                        'max_payout': 450.0,
                    },
                    'deadline': {'metric': 'beneficiary_turns', 'initial': 2},
                },
            ],
        }
        trade = SimpleNamespace(
            initiator_id=1,
            receiver_id=2,
            offered_money=100.0,
            requested_money=0.0,
            offered_props=[],
            requested_props=[],
            offered_lobby_pledges=[],
            requested_lobby_pledges=[],
            included_deal_drafts=[normalized_draft],
        )
        bundled_deal = SimpleNamespace(
            id=44,
            match_id=77,
            proposer_id=1,
            counterparty_id=2,
            status='proposed',
            title='Revenue Shield',
            created_at=None,
            responded_at=None,
            accepted_at=None,
            cancelled_at=None,
            last_updated_at=None,
            proposal_version=1,
            counter_of_deal_id=None,
            clauses=[],
        )

        def fake_normalize(_match_id, _proposer_id, game_state, _draft_payload):
            player_by_id = {player['id']: player for player in game_state['players']}
            self.assertEqual(player_by_id[1]['balance'], 400.0)
            self.assertEqual(player_by_id[2]['balance'], 450.0)
            return normalized_draft, None

        def fake_accept(_deal, game_state, *, commit=True):
            self.assertFalse(commit)
            updated_players = []
            for player in game_state['players']:
                next_player = dict(player)
                if next_player['id'] == 1:
                    next_player['balance'] = 100.0
                updated_players.append(next_player)
            return {**game_state, 'players': updated_players}, None

        with patch('app.engine.trading.normalize_deal_request_payload', side_effect=fake_normalize) as normalize_draft, patch(
            'app.engine.trading.create_deal',
            return_value=bundled_deal,
        ) as create_deal, patch(
            'app.engine.trading.accept_deal',
            side_effect=fake_accept,
        ) as accept_deal, patch(
            'app.engine.trading.serialize_deal',
            return_value={'id': 44, 'title': 'Revenue Shield', 'status': 'accepted'},
        ) as serialize_deal:
            next_state, pledge_results, created_deals, error = apply_trade_acceptance(state, trade, 77)

        self.assertIsNone(error)
        self.assertEqual(pledge_results, {'initiator': [], 'receiver': []})
        self.assertEqual(created_deals, [{'id': 44, 'title': 'Revenue Shield', 'status': 'accepted'}])
        normalize_draft.assert_called_once()
        create_deal.assert_called_once_with(77, 1, normalized_draft, commit=False)
        accept_args, accept_kwargs = accept_deal.call_args
        self.assertIs(accept_args[0], bundled_deal)
        self.assertEqual({player['id']: player['balance'] for player in accept_args[1]['players']}, {1: 400.0, 2: 450.0})
        self.assertEqual(accept_kwargs, {'commit': False})
        serialize_deal.assert_called_once()

        player_by_id = {player['id']: player for player in next_state['players']}
        self.assertEqual(player_by_id[1]['balance'], 100.0)
        self.assertEqual(player_by_id[2]['balance'], 450.0)

    def test_apply_trade_acceptance_rejects_stale_unavailable_lobby_pledges(self):
        state = make_state()
        state['econ']['gov_type'] = 'social_democracy'
        state['settings']['government_type'] = 'social_democracy'
        trade = SimpleNamespace(
            initiator_id=1,
            receiver_id=2,
            offered_money=0.0,
            requested_money=0.0,
            offered_props=[],
            requested_props=[],
            offered_lobby_pledges=[{'target': 'money_supply_expand', 'amount': 50.0}],
            requested_lobby_pledges=[],
            included_deal_drafts=[],
        )

        next_state, pledge_results, created_deals, error = apply_trade_acceptance(state, trade, 77)

        self.assertEqual(next_state, state)
        self.assertIsNone(pledge_results)
        self.assertEqual(created_deals, [])
        self.assertEqual(
            error,
            'This trade includes lobbying pledges that are not available under the current government.',
        )


if __name__ == '__main__':
    unittest.main()
