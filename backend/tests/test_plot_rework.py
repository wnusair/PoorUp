import os
import sys
import unittest


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.engine.debt import credit_player_with_debt_settlement  # noqa: E402
from app.engine.economy import ensure_regime_economy_state  # noqa: E402
from app.engine.plot import (  # noqa: E402
    COMMUNIST_PLOT_OWNER_ID,
    refresh_plot_snapshot,
    resolve_end_of_round_plot_state,
    submit_plot_join,
)


def make_player(player_id, username, *, balance=100.0, is_bot=False):
    return {
        'id': player_id,
        'username': username,
        'balance': balance,
        'current_position': 2,
        'team_id': None,
        'is_bot': is_bot,
        'is_bankrupt': False,
        'is_connected': True,
        'is_jailed': False,
        'has_jail_card': False,
        'jail_turns_remaining': 0,
    }


def make_property(property_id, owner_id, *, board_position, name=None, region='Africa', base_price=120.0):
    return {
        'id': property_id,
        'name': name or f'Property {property_id}',
        'region': region,
        'group_color': '#8B4513',
        'base_price': base_price,
        'current_value': base_price,
        'owner_id': owner_id,
        'board_position': board_position,
        'property_type': 'property',
        'dev_level': 0,
        'is_mortgaged': False,
    }


def make_state(*, players, properties, current_round=5, social=None, treasury_balance=800.0):
    return {
        'match_id': 77,
        'current_round': current_round,
        'players': players,
        'properties': properties,
        'pending_debts': [],
        'free_parking_pot': 0.0,
        'settings': {
            'government_type': 'liberal_democracy',
            'game_mode': 'standard',
            'lobbying_enabled': True,
            'trading_enabled': True,
            'auction_enabled': True,
        },
        'econ': ensure_regime_economy_state(
            {
                'gov_type': 'liberal_democracy',
                'government_type': 'liberal_democracy',
                'stability': 0.62,
                'inflation_rate': 0.03,
                'tax_multiplier': 0.22,
                'welfare_payout': 18.0,
                'treasury_balance': treasury_balance,
                'bailout_enabled': False,
            },
            {'government_type': 'liberal_democracy', 'go_salary': 200},
        ),
        'social': social or {},
    }


class PlotReworkTests(unittest.TestCase):
    def test_positive_income_diverts_to_joint_account_before_crediting_member(self):
        state = make_state(
            players=[make_player(1, 'Atlas', balance=100.0)],
            properties=[],
            social={
                'plot': {
                    'exists': True,
                    'joint_account_balance': 0.0,
                    'joint_account_contribution_rate': 0.4,
                    'members': {
                        '1': {'player_id': 1, 'role': 'founder', 'active': True, 'cash_contributed': 0.0},
                    },
                },
            },
        )

        next_state, result = credit_player_with_debt_settlement(state, 1, 100.0)
        player = next_state['players'][0]
        plot = next_state['social']['plot']

        self.assertEqual(result['credited_amount'], 100.0)
        self.assertEqual(player['balance'], 160.0)
        self.assertEqual(plot['joint_account_balance'], 40.0)
        self.assertEqual(plot['joint_account_contributions']['1'], 40.0)
        self.assertEqual(plot['members']['1']['cash_contributed'], 40.0)

    def test_member_contributions_spend_from_the_joint_account_pool(self):
        state = make_state(
            players=[make_player(1, 'Atlas', balance=80.0)],
            properties=[],
            social={
                'plot': {
                    'exists': True,
                    'founder_id': 1,
                    'commander_id': 1,
                    'public': True,
                    'stage': 3,
                    'support': 2.0,
                    'supply': 0.0,
                    'joint_account_balance': 120.0,
                    'members': {
                        '1': {
                            'player_id': 1,
                            'role': 'founder',
                            'is_founder': True,
                            'joined_round': 4,
                            'contribution_rounds': [4],
                            'required_contribution_rounds': 1,
                            'required_successful_actions': 1,
                            'successful_actions_supported': 1,
                            'support_contributed': 0.0,
                            'supply_contributed': 0.0,
                            'cash_contributed': 0.0,
                            'active': True,
                        },
                    },
                    'regions': {'Africa': {'seeded_cells': 1}},
                },
            },
        )

        next_state, result = submit_plot_join(state, player_id=1, payload={'intent': 'contribute', 'amount': 100.0})
        plot = next_state['social']['plot']
        member = plot['members']['1']

        self.assertTrue(result['success'])
        self.assertEqual(plot['joint_account_balance'], 20.0)
        self.assertEqual(plot['support'], 3.0)
        self.assertEqual(plot['supply'], 1.0)
        self.assertEqual(member['cash_contributed'], 100.0)
        self.assertEqual(member['support_contributed'], 1.0)

    def test_seized_property_support_growth_uses_the_exact_three_plus_two_rule(self):
        properties = [
            make_property(1, COMMUNIST_PLOT_OWNER_ID, board_position=2),
            make_property(2, COMMUNIST_PLOT_OWNER_ID, board_position=4),
            make_property(3, COMMUNIST_PLOT_OWNER_ID, board_position=9),
            make_property(4, COMMUNIST_PLOT_OWNER_ID, board_position=10),
            make_property(5, COMMUNIST_PLOT_OWNER_ID, board_position=12),
        ]
        state = make_state(
            players=[make_player(1, 'Atlas', balance=120.0)],
            properties=properties,
            social={
                'plot': {
                    'exists': True,
                    'founder_id': 1,
                    'commander_id': 1,
                    'stage': 4,
                    'support': 0.0,
                    'supply': 0.0,
                    'public': True,
                    'first_seizure_round': 4,
                    'last_round_resolved': 0,
                    'last_mutual_aid_round': 5,
                    'last_recruitment_round': 5,
                    'last_aggression_round': 5,
                    'last_stockpile_round': 5,
                    'members': {
                        '1': {'player_id': 1, 'role': 'founder', 'active': True},
                    },
                },
                'properties': {},
            },
            treasury_balance=900.0,
        )

        next_state = resolve_end_of_round_plot_state(state)
        plot = next_state['social']['plot']

        self.assertEqual(plot['support'], 2.0)
        self.assertTrue(any('2 Support across 5 seized properties' in entry['summary'] for entry in plot['action_history']))

    def test_bot_commander_goal_is_exposed_in_plain_language(self):
        state = make_state(
            current_round=6,
            players=[
                make_player(1, 'Atlas Bot', balance=120.0, is_bot=True),
                make_player(2, 'Rival', balance=900.0),
            ],
            properties=[
                make_property(11, 2, board_position=2, name='Cairo', base_price=180.0),
            ],
            social={
                'properties': {
                    '11': {'plot_agitation': 3},
                },
                'plot': {
                    'exists': True,
                    'founder_id': 1,
                    'commander_id': 1,
                    'stage': 3,
                    'support': 6.0,
                    'supply': 4.0,
                    'support_generated_total': 14.0,
                    'public': True,
                    'members': {
                        '1': {
                            'player_id': 1,
                            'role': 'founder',
                            'is_founder': True,
                            'joined_round': 4,
                            'contribution_rounds': [4, 5],
                            'required_contribution_rounds': 1,
                            'required_successful_actions': 1,
                            'successful_actions_supported': 1,
                            'active': True,
                        },
                    },
                    'regions': {'Africa': {'seeded_cells': 1}},
                },
            },
        )

        next_state = refresh_plot_snapshot(state)
        plot = next_state['social']['plot']

        self.assertEqual(plot['strategic_goal'], 'seize_property')
        self.assertEqual(plot['goal_target_property_id'], 11)
        self.assertIn('Seize Cairo next.', plot['strategic_goal_text'])


if __name__ == '__main__':
    unittest.main()
