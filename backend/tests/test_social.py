import os
import sys
import random
import unittest


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from flask import Flask  # noqa: E402

from app import db  # noqa: E402
from app.engine import bots, events  # noqa: E402
from app.engine.social import PROLETARIAT_UNION_ID, _start_revolution, ensure_social_state, submit_negotiation_contribution  # noqa: E402


class FakeRedis:
    def __init__(self):
        self.values = {}

    def get(self, key):
        return self.values.get(key)

    def set(self, key, value, ex=None):
        self.values[key] = value


class FakeSocket:
    def __init__(self):
        self.emits = []

    def emit(self, event, payload, room=None):
        self.emits.append((event, payload, room))


def make_player(player_id, username, balance, *, is_bot=False):
    return {
        'id': player_id,
        'username': username,
        'balance': balance,
        'current_position': 1,
        'team_id': None,
        'is_bot': is_bot,
        'is_bankrupt': False,
        'is_connected': True,
        'is_jailed': False,
        'has_jail_card': False,
        'jail_turns_remaining': 0,
    }


def make_property(property_id, owner_id, *, board_position=1, group_color='#8B4513', base_price=100, dev_level=0):
    return {
        'id': property_id,
        'name': f'Property {property_id}',
        'region': 'Africa',
        'group_color': group_color,
        'base_price': base_price,
        'current_value': base_price,
        'owner_id': owner_id,
        'board_position': board_position,
        'property_type': 'property',
        'dev_level': dev_level,
        'is_mortgaged': False,
    }


def make_state(players, properties, social=None):
    return {
        'match_id': 12,
        'current_round': 3,
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
        'econ': {
            'gov_type': 'liberal_democracy',
            'government_type': 'liberal_democracy',
            'stability': 0.62,
            'inflation_rate': 0.03,
            'tax_multiplier': 0.22,
            'welfare_payout': 18.0,
            'treasury_balance': 400.0,
            'bailout_enabled': False,
        },
        'social': social or {},
    }


class SocialEngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = Flask(__name__)
        cls.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite://'
        cls.app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        cls.app.config['SECRET_KEY'] = 'test'
        db.init_app(cls.app)

    def setUp(self):
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.addCleanup(self.app_context.pop)

        self.redis = FakeRedis()
        self.socket = FakeSocket()

    def profile(self):
        return bots.build_bot_profile(
            {'government_type': 'liberal_democracy', 'game_mode': 'standard'},
            difficulty='normal',
            persona=None,
            rng=random.Random(11),
            seat_index=0,
        )

    def test_strike_property_collects_no_rent(self):
        payer = make_player(1, 'Atlas', 500)
        owner = make_player(2, 'Rival', 600)
        state = make_state(
            [payer, owner],
            [make_property(1, 2, dev_level=2)],
            social={'properties': {'1': {'incident_type': 'strike'}}},
        )

        updated_player, updated_state, updated_econ, logs = events.resolve_space(
            payer,
            state,
            state['econ'],
            state['settings'],
            self.redis,
            self.socket,
            12,
        )

        self.assertEqual(updated_player['balance'], 500)
        self.assertEqual(updated_state['players'][0]['balance'], 500)
        self.assertEqual(updated_econ['treasury_balance'], 400.0)
        self.assertTrue(any(entry['event_type'] == 'rent_suspended' for entry in logs))

    def test_unionized_property_removes_bloc_fee_from_circulation(self):
        payer = make_player(1, 'Atlas', 500)
        former_owner = make_player(2, 'Rival', 600)
        state = make_state(
            [payer, former_owner],
            [make_property(1, PROLETARIAT_UNION_ID, dev_level=1)],
            social={'properties': {'1': {'incident_type': 'revolution', 'former_owner_id': 2, 'union_development_level': 1}}},
        )

        updated_player, _, updated_econ, logs = events.resolve_space(
            payer,
            state,
            state['econ'],
            state['settings'],
            self.redis,
            self.socket,
            12,
        )

        self.assertLess(updated_player['balance'], 500)
        self.assertEqual(updated_econ['treasury_balance'], 400.0)
        self.assertTrue(any(entry['event_type'] == 'union_charge_collected' for entry in logs))
        self.assertTrue(any(event == 'rent_collected' for event, _, _ in self.socket.emits))

    def test_revolution_only_seizes_high_risk_properties_in_same_owner_region_territory(self):
        player_one = make_player(1, 'Atlas', 800)
        player_two = make_player(2, 'Rival', 900)
        properties = [
            make_property(1, 1, board_position=1, base_price=180),
            make_property(2, 1, board_position=2, base_price=200),
            make_property(3, 2, board_position=3, base_price=220),
            {**make_property(4, 1, board_position=4, base_price=190), 'region': 'South Asia'},
        ]
        state = make_state(
            [player_one, player_two],
            properties,
            social={
                'overall_rage': 92.0,
                'stability_percent': 28,
                'properties': {
                    '1': {'property_id': 1, 'region': 'Africa', 'tension': 94.0, 'watch_state': 'active_incident'},
                    '2': {'property_id': 2, 'region': 'Africa', 'tension': 88.0, 'watch_state': 'critical_watch'},
                    '3': {'property_id': 3, 'region': 'Africa', 'tension': 93.0, 'watch_state': 'critical_watch'},
                    '4': {'property_id': 4, 'region': 'South Asia', 'tension': 91.0, 'watch_state': 'critical_watch'},
                },
            },
        )

        next_state, seized_ids = _start_revolution(state, source_property_id=1)

        self.assertEqual(set(seized_ids), {1, 2})
        seized_one = next(prop for prop in next_state['properties'] if prop['id'] == 1)
        seized_two = next(prop for prop in next_state['properties'] if prop['id'] == 2)
        untouched_other_owner = next(prop for prop in next_state['properties'] if prop['id'] == 3)
        untouched_other_region = next(prop for prop in next_state['properties'] if prop['id'] == 4)

        self.assertEqual(seized_one['owner_id'], PROLETARIAT_UNION_ID)
        self.assertEqual(seized_two['owner_id'], PROLETARIAT_UNION_ID)
        self.assertEqual(untouched_other_owner['owner_id'], 2)
        self.assertEqual(untouched_other_region['owner_id'], 1)

    def test_negotiation_contribution_updates_social_commitment(self):
        player = make_player(1, 'Atlas', 500)
        rival = make_player(2, 'Rival', 600)
        state = make_state(
            [player, rival],
            [make_property(1, 1, dev_level=1)],
            social={
                'properties': {
                    '1': {
                        'incident_type': 'protest',
                        'remaining_rounds': 2,
                        'negotiation_target': 100.0,
                        'negotiation_committed': 0.0,
                        'dominant_grievance': 'welfare_shortfall',
                    },
                },
            },
        )

        next_state, result = submit_negotiation_contribution(
            state,
            property_id=1,
            player_id=1,
            amount=40.0,
        )

        updated_player = next(player for player in next_state['players'] if player['id'] == 1)
        updated_entry = next_state['social']['properties']['1']

        self.assertEqual(result['contribution'], 40.0)
        self.assertGreaterEqual(result['negotiation_committed'], 40.0)
        self.assertGreaterEqual(updated_entry['negotiation_committed'], 40.0)
        self.assertEqual(updated_player['balance'], 460.0)

    def test_bot_prefers_negotiation_for_owned_incident(self):
        player = make_player(1, 'Atlas', 700, is_bot=True)
        rival = make_player(2, 'Rival', 900)
        state = make_state(
            [player, rival],
            [make_property(1, 1, dev_level=1)],
            social={
                'overall_rage': 72.0,
                'stability_percent': 32,
                'active_incidents': [
                    {
                        'property_id': 1,
                        'incident_type': 'strike',
                        'negotiation_target': 180.0,
                        'negotiation_committed': 0.0,
                    },
                ],
                'properties': {
                    '1': {
                        'property_id': 1,
                        'incident_type': 'strike',
                        'tension': 81.0,
                        'region': 'Africa',
                        'dominant_grievance': 'tax_pressure',
                        'negotiation_target': 180.0,
                        'negotiation_committed': 0.0,
                    },
                },
            },
        )

        action = bots.choose_management_action(player, state, self.profile())

        self.assertIsNotNone(action)
        self.assertEqual(action['type'], 'negotiate')
        self.assertEqual(action['property_id'], 1)
        self.assertGreater(action['contribution'], 0)

    def test_bot_avoids_development_into_high_tension_property(self):
        player = make_player(1, 'Atlas', 1200, is_bot=True)
        rival = make_player(2, 'Rival', 900)
        properties = [
            make_property(1, 1, board_position=1, group_color='#8B4513', base_price=60),
            make_property(2, 1, board_position=2, group_color='#8B4513', base_price=60),
            make_property(3, 1, board_position=4, group_color='#8B4513', base_price=100),
        ]
        state = make_state(
            [player, rival],
            properties,
            social={
                'overall_rage': 68.0,
                'stability_percent': 38,
                'properties': {
                    '1': {'property_id': 1, 'tension': 72.0, 'territory_instability': 80.0},
                    '2': {'property_id': 2, 'tension': 74.0, 'territory_instability': 80.0},
                    '3': {'property_id': 3, 'tension': 76.0, 'territory_instability': 80.0},
                },
            },
        )

        target = bots.choose_development_target(player, state, self.profile())

        self.assertIsNone(target)

    def test_wealth_concentrated_hostile_lobbying_increases_owner_property_tension(self):
        wealthy_owner = make_player(1, 'Atlas', 2400)
        pressured_rival = make_player(2, 'Rival', 260)
        middle_player = make_player(3, 'Broker', 520)
        owned_property = make_property(1, 1, dev_level=1, base_price=180)

        baseline_state = ensure_social_state(
            make_state([wealthy_owner, pressured_rival, middle_player], [owned_property])
        )

        lobbying_state = make_state(
            [wealthy_owner, pressured_rival, middle_player],
            [owned_property],
        )
        lobbying_state['lobbying_stats'] = {
            'player_totals': {},
            'resolved_history': [],
            'policy_pools': {
                'welfare_decrease': {
                    'target': 'welfare_decrease',
                    'policy_name': 'Welfare Cuts',
                    'target_stat': 'welfare_decrease',
                    'cost_hint': 220,
                    'pool_total': 220,
                    'contributors': [
                        {
                            'player_id': 1,
                            'username': 'Atlas',
                            'contribution': 220,
                        },
                    ],
                },
            },
        }

        pressured_state = ensure_social_state(lobbying_state)
        baseline_entry = baseline_state['social']['properties']['1']
        pressured_entry = pressured_state['social']['properties']['1']

        self.assertGreater(pressured_entry['tension'], baseline_entry['tension'])
        self.assertGreater(pressured_entry['hostile_lobbying_points'], 0)
        self.assertTrue(any(reason['key'] == 'hostile_lobbying' for reason in pressured_entry['reason_breakdown']))
        self.assertEqual(pressured_entry['hostile_lobby_targets'][0]['target'], 'welfare_decrease')


if __name__ == '__main__':
    unittest.main()