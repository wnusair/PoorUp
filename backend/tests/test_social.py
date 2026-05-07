import os
import sys
import random
import unittest


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from flask import Flask  # noqa: E402

from app import db  # noqa: E402
from app.engine import bots, events  # noqa: E402
from app.engine.game_loop import check_bankruptcy  # noqa: E402
from app.engine.plot import (  # noqa: E402
    COMMUNIST_PLOT_OWNER_ID,
    seed_debug_communist_plot_state,
    start_communist_plot,
    submit_plot_action,
    submit_plot_counter_action,
    submit_plot_join,
    submit_plot_leave,
)
from app.engine.social import (  # noqa: E402
    MODE_PROFILE,
    PROLETARIAT_UNION_ID,
    _apply_protest_concession,
    _macro_metrics,
    _state_from_entry,
    _start_revolution,
    ensure_social_state,
    resolve_end_of_round_social_state,
    submit_negotiation_contribution,
)


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
        'current_position': 2,
        'team_id': None,
        'is_bot': is_bot,
        'is_bankrupt': False,
        'is_connected': True,
        'is_jailed': False,
        'has_jail_card': False,
        'jail_turns_remaining': 0,
    }


def make_property(property_id, owner_id, *, board_position=2, group_color='#8B4513', base_price=100, dev_level=0):
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

    def test_jailed_owner_collects_no_rent_when_prison_rent_is_disabled(self):
        payer = make_player(1, 'Atlas', 500)
        owner = make_player(2, 'Rival', 600)
        owner['is_jailed'] = True
        state = make_state(
            [payer, owner],
            [make_property(1, 2, dev_level=2)],
        )
        state['settings']['collect_rent_while_jailed'] = False

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
        self.assertEqual(updated_state['players'][1]['balance'], 600)
        self.assertEqual(updated_econ['treasury_balance'], 400.0)
        self.assertTrue(any('does not collect rent' in entry['description'] for entry in logs))

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
            make_property(1, 1, board_position=2, base_price=180),
            make_property(2, 1, board_position=4, base_price=200),
            make_property(3, 2, board_position=9, base_price=220),
            {**make_property(4, 1, board_position=10, base_price=190), 'region': 'South Asia'},
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

    def test_concentrated_oligarchy_escalates_beyond_strikes_under_social_democracy(self):
        wealthy_owner = make_player(1, 'Atlas', 2600)
        pressured_rival = make_player(2, 'Rival', 40)
        middle_player = make_player(3, 'Broker', 70)
        properties = [
            make_property(1, 1, board_position=2, base_price=180, dev_level=4),
            make_property(2, 1, board_position=4, base_price=200, dev_level=4),
            {**make_property(3, 1, board_position=9, base_price=220, dev_level=5), 'region': 'South Asia', 'group_color': '#EC4899'},
            {**make_property(4, 1, board_position=10, base_price=240, dev_level=5), 'region': 'South Asia', 'group_color': '#EC4899'},
            {**make_property(5, 1, board_position=12, base_price=260, dev_level=4), 'region': 'Middle East', 'group_color': '#8B5CF6'},
            {**make_property(6, 2, board_position=13, base_price=140, dev_level=0), 'region': 'Middle East', 'group_color': '#8B5CF6'},
        ]
        state = make_state([wealthy_owner, pressured_rival, middle_player], properties)
        state['econ'].update({
            'stability': 0.28,
            'inflation_rate': 0.60,
            'welfare_payout': 8.0,
            'bailout_enabled': False,
        })
        state['lobbying_stats'] = {
            'player_totals': {},
            'resolved_history': [],
            'policy_pools': {
                'welfare_decrease': {
                    'target': 'welfare_decrease',
                    'policy_name': 'Welfare Cuts',
                    'target_stat': 'welfare_decrease',
                    'cost_hint': 250,
                    'pool_total': 250,
                    'contributors': [{'player_id': 1, 'username': 'Atlas', 'contribution': 250}],
                },
                'bailout_disable': {
                    'target': 'bailout_disable',
                    'policy_name': 'Disable Bailouts',
                    'target_stat': 'bailout_disable',
                    'cost_hint': 250,
                    'pool_total': 250,
                    'contributors': [{'player_id': 1, 'username': 'Atlas', 'contribution': 250}],
                },
            },
        }

        pressured_state = ensure_social_state(state)
        hotspot = pressured_state['social']['properties']['1']

        self.assertGreaterEqual(hotspot['tension'], 80.0)
        self.assertIn(hotspot['next_state'], {'uprising', 'revolution'})

        resolved_state = resolve_end_of_round_social_state(pressured_state)
        active_types = {entry['incident_type'] for entry in resolved_state['social']['active_incidents']}
        self.assertTrue(active_types.intersection({'uprising', 'revolution'}))

    def test_liberal_democracy_shareholder_pressure_drives_market_discontent(self):
        wealthy_owner = make_player(1, 'Atlas', 2800)
        pressured_rival = make_player(2, 'Rival', 80)
        middle_player = make_player(3, 'Broker', 120)
        properties = [
            make_property(1, 1, board_position=2, base_price=240, dev_level=4),
            make_property(2, 1, board_position=4, base_price=260, dev_level=4),
            {**make_property(3, 1, board_position=9, base_price=300, dev_level=5), 'region': 'South Asia', 'group_color': '#EC4899'},
            {**make_property(4, 2, board_position=10, base_price=140, dev_level=0), 'region': 'South Asia', 'group_color': '#EC4899'},
        ]
        state = make_state([wealthy_owner, pressured_rival, middle_player], properties)
        state['econ'].update({
            'stability': 0.46,
            'inflation_rate': 0.05,
            'welfare_payout': 12.0,
            'tax_multiplier': 0.21,
            'market_confidence': 88.0,
            'capital_yield_rate': 0.024,
            'private_equity_bonus_multiplier': 1.18,
        })
        state['lobbying_stats'] = {
            'player_totals': {},
            'resolved_history': [],
            'policy_pools': {
                'money_supply_expand': {
                    'target': 'money_supply_expand',
                    'policy_name': 'Expand Money Supply',
                    'target_stat': 'money_supply_expand',
                    'cost_hint': 280,
                    'pool_total': 280,
                    'contributors': [{'player_id': 1, 'username': 'Atlas', 'contribution': 280}],
                },
            },
        }

        pressured_state = ensure_social_state(state)
        hotspot = pressured_state['social']['properties']['1']

        self.assertGreaterEqual(hotspot['tension'], 70.0)
        self.assertEqual(hotspot['dominant_grievance'], 'shareholder_pressure')
        self.assertIn('money_supply_contract', hotspot['recommended_lobby_targets'])
        self.assertTrue(any(target['target'] == 'money_supply_expand' for target in hotspot['hostile_lobby_targets']))

    def test_minarchism_overdevelopment_stays_local_and_avoids_mass_revolution(self):
        owner = make_player(1, 'Atlas', 1800)
        rival = make_player(2, 'Rival', 90)
        broker = make_player(3, 'Broker', 120)
        properties = [
            make_property(1, 1, board_position=2, base_price=180, dev_level=6),
            make_property(2, 1, board_position=4, base_price=200, dev_level=1),
            {**make_property(3, 2, board_position=9, base_price=120, dev_level=0), 'region': 'South Asia', 'group_color': '#EC4899'},
            {**make_property(4, None, board_position=10, base_price=140, dev_level=0), 'region': 'South Asia', 'group_color': '#EC4899'},
            {**make_property(5, None, board_position=12, base_price=220, dev_level=0), 'region': 'Middle East', 'group_color': '#8B5CF6'},
        ]
        state = make_state([owner, rival, broker], properties)
        state['settings']['government_type'] = 'minarchism'
        state['econ'].update({
            'gov_type': 'minarchism',
            'government_type': 'minarchism',
            'stability': 0.26,
            'inflation_rate': 0.34,
            'welfare_payout': 0.0,
            'bailout_enabled': False,
        })

        minarchist_state = ensure_social_state(state)
        hotspot = minarchist_state['social']['properties']['1']

        self.assertGreaterEqual(hotspot['tension'], 65.0)
        self.assertIn(hotspot['next_state'], {'strike', 'uprising', 'revolution'})

        minarchist_state['social']['overall_rage'] = 96.0
        minarchist_state['social']['stability_percent'] = 24
        minarchist_state['social']['properties']['1'].update({
            'tension': 96.0,
            'watch_state': 'active_incident',
            'territory_instability': 88.0,
            'government_type': 'minarchism',
            'owner_board_share': 0.40,
            'rival_property_poverty_ratio': 1.0,
            'owner_development_pressure': 1.0,
            'mass_revolution_pressure': 1.0,
        })
        minarchist_state['social']['properties']['2'].update({
            'tension': 94.0,
            'watch_state': 'critical_watch',
            'territory_instability': 88.0,
            'government_type': 'minarchism',
            'owner_board_share': 0.40,
            'rival_property_poverty_ratio': 1.0,
            'owner_development_pressure': 1.0,
            'mass_revolution_pressure': 1.0,
        })

        next_state, seized_ids = _start_revolution(minarchist_state, source_property_id=1)

        self.assertEqual(set(seized_ids), {1})
        seized_property = next(prop for prop in next_state['properties'] if prop['id'] == 1)
        untouched_property = next(prop for prop in next_state['properties'] if prop['id'] == 2)
        self.assertEqual(seized_property['owner_id'], PROLETARIAT_UNION_ID)
        self.assertEqual(untouched_property['owner_id'], 1)

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
        state['econ']['treasury_balance'] = 800.0

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

    def test_low_treasury_negotiation_costs_more_for_less_relief(self):
        player = make_player(1, 'Atlas', 500)
        rival = make_player(2, 'Rival', 600)
        state = make_state(
            [player, rival],
            [make_property(1, 1, dev_level=1, base_price=180)],
            social={
                'properties': {
                    '1': {
                        'incident_type': 'protest',
                        'remaining_rounds': 2,
                        'negotiation_target': 100.0,
                        'negotiation_committed': 0.0,
                        'dominant_grievance': 'fiscal_backlash',
                    },
                },
            },
        )
        state['settings']['government_type'] = 'social_democracy'
        state['econ'].update({
            'gov_type': 'social_democracy',
            'government_type': 'social_democracy',
            'treasury_balance': 350.0,
        })

        next_state, result = submit_negotiation_contribution(
            state,
            property_id=1,
            player_id=1,
            amount=40.0,
        )

        updated_player = next(player for player in next_state['players'] if player['id'] == 1)

        self.assertTrue(result['treasury_penalized'])
        self.assertGreater(result['total_cost'], 40.0)
        self.assertLess(result['effective_contribution'], 40.0)
        self.assertEqual(updated_player['balance'], round(500.0 - result['total_cost'], 2))

    def test_treasury_loss_backlash_activates_stage_boost(self):
        owner = make_player(1, 'Atlas', 900)
        rival = make_player(2, 'Rival', 120)
        state = make_state([owner, rival], [make_property(1, 1, dev_level=2, base_price=180)])
        state['current_round'] = 6
        state['settings']['government_type'] = 'social_democracy'
        state['econ'].update({
            'gov_type': 'social_democracy',
            'government_type': 'social_democracy',
            'treasury_balance': 420.0,
            'inflation_rate': 0.18,
            'welfare_payout': 72.0,
            'bailout_enabled': True,
        })
        state['tax_stats'] = {
            'player_totals': {},
            'totals': {},
            'last_welfare_distribution': {},
            'budget_history': [
                {'round': 1, 'treasury_balance': 1500.0},
                {'round': 2, 'treasury_balance': 1120.0},
                {'round': 3, 'treasury_balance': 860.0},
                {'round': 4, 'treasury_balance': 610.0},
                {'round': 5, 'treasury_balance': 420.0},
            ],
        }

        macro = _macro_metrics(state, state['econ'], state['settings'])

        self.assertEqual(macro['systemic_stage_boost'], 1)
        self.assertIn('treasury_loss_streak', macro['systemic_stage_boost_reasons'])
        self.assertGreater(macro['macro_points']['fiscal_backlash'], 0)

    def test_repeated_bailouts_trigger_stage_boost(self):
        owner = make_player(1, 'Atlas', 900)
        rival = make_player(2, 'Rival', 120)
        state = make_state([owner, rival], [make_property(1, 1, dev_level=1, base_price=180)])
        state['current_round'] = 6
        state['settings']['government_type'] = 'social_democracy'
        state['econ'].update({
            'gov_type': 'social_democracy',
            'government_type': 'social_democracy',
            'treasury_balance': 900.0,
            'inflation_rate': 0.14,
            'welfare_payout': 68.0,
            'bailout_enabled': True,
        })
        state['social'] = {
            'bailout_history': [
                {'round': 2, 'player_id': 1, 'amount': 250.0},
                {'round': 3, 'player_id': 1, 'amount': 240.0},
                {'round': 4, 'player_id': 1, 'amount': 230.0},
                {'round': 6, 'player_id': 1, 'amount': 220.0},
            ],
        }

        macro = _macro_metrics(state, state['econ'], state['settings'])

        self.assertEqual(macro['systemic_stage_boost'], 1)
        self.assertIn('bailout_abuse', macro['systemic_stage_boost_reasons'])
        self.assertGreater(macro['bailout_backlash']['max_recent_bailouts'], 3)

    def test_systemic_stage_boost_avoids_auto_revolution(self):
        protest_entry = {
            'tension': 52.0,
            'territory_instability': 58.0,
            'government_type': 'social_democracy',
            'systemic_stage_boost': 1,
        }
        uprising_entry = {
            'tension': 84.0,
            'territory_instability': 72.0,
            'government_type': 'social_democracy',
            'systemic_stage_boost': 1,
        }

        self.assertEqual(_state_from_entry(protest_entry, 72.0, 42.0, MODE_PROFILE['standard']), 'strike')
        self.assertEqual(_state_from_entry(uprising_entry, 78.0, 38.0, MODE_PROFILE['standard']), 'uprising')

    def test_inflation_stage_floors_apply_across_all_modes(self):
        for mode in ('standard', 'speed', 'chaos', 'cooperative'):
            profile = MODE_PROFILE[mode]
            base_entry = {
                'tension': 36.0,
                'territory_instability': 42.0,
                'government_type': 'liberal_democracy',
            }

            self.assertEqual(
                _state_from_entry({**base_entry, 'inflation_rate': 0.40}, 44.0, 58.0, profile),
                'strike',
            )
            self.assertEqual(
                _state_from_entry({**base_entry, 'inflation_rate': 0.60}, 44.0, 58.0, profile),
                'uprising',
            )
            self.assertEqual(
                _state_from_entry({**base_entry, 'inflation_rate': 1.00}, 44.0, 58.0, profile),
                'revolution',
            )

    def test_hyperinflation_fast_forwards_active_incidents(self):
        wealthy_owner = make_player(1, 'Atlas', 2600)
        pressured_rival = make_player(2, 'Rival', 60)
        middle_player = make_player(3, 'Broker', 120)
        properties = [
            make_property(1, 1, board_position=2, base_price=220, dev_level=4),
            make_property(2, 1, board_position=4, base_price=240, dev_level=4),
            {**make_property(3, 1, board_position=9, base_price=280, dev_level=5), 'region': 'South Asia', 'group_color': '#EC4899'},
            {**make_property(4, 2, board_position=10, base_price=140, dev_level=0), 'region': 'South Asia', 'group_color': '#EC4899'},
        ]
        state = make_state([wealthy_owner, pressured_rival, middle_player], properties)
        state['econ'].update({
            'stability': 0.42,
            'inflation_rate': 1.05,
            'welfare_payout': 10.0,
            'market_confidence': 84.0,
            'capital_yield_rate': 0.022,
            'private_equity_bonus_multiplier': 1.16,
        })

        prepared_state = ensure_social_state(state)
        prepared_state['social']['properties']['1'].update({
            'incident_type': 'protest',
            'remaining_rounds': 2,
        })

        resolved_state = resolve_end_of_round_social_state(prepared_state)
        resolved_entry = resolved_state['social']['properties']['1']

        self.assertEqual(resolved_entry['incident_type'], 'revolution')
        self.assertEqual(next(prop for prop in resolved_state['properties'] if prop['id'] == 1)['owner_id'], PROLETARIAT_UNION_ID)

    def test_unrest_can_force_owner_taxes_welfare_cuts_and_bailout_shutdown(self):
        owner = make_player(1, 'Atlas', 900)
        rival = make_player(2, 'Rival', 600)
        state = make_state([owner, rival], [make_property(1, 1, dev_level=2, base_price=180)])
        state['settings']['government_type'] = 'social_democracy'
        state['econ'].update({
            'gov_type': 'social_democracy',
            'government_type': 'social_democracy',
            'welfare_payout': 66.0,
            'treasury_balance': 420.0,
            'bailout_enabled': True,
        })

        prepared_state = ensure_social_state(state)
        updated_state = _apply_protest_concession(prepared_state, 1, 'uprising')
        updated_owner = next(player for player in updated_state['players'] if player['id'] == 1)

        self.assertLess(updated_owner['balance'], owner['balance'])
        self.assertLess(updated_state['econ']['welfare_payout'], prepared_state['econ']['welfare_payout'])
        self.assertFalse(updated_state['econ']['bailout_enabled'])
        self.assertTrue(any('out of fear' in entry['description'].lower() for entry in updated_state.get('log_buffer', [])))

    def test_hardship_eligible_player_can_found_communist_plot(self):
        founder = make_player(1, 'Atlas', 90)
        rival = make_player(2, 'Rival', 900)
        broker = make_player(3, 'Broker', 1100)
        properties = [
            make_property(1, 1, board_position=2, base_price=100, dev_level=0),
            make_property(2, 2, board_position=4, base_price=180, dev_level=2),
            make_property(3, 3, board_position=9, base_price=220, dev_level=2),
        ]
        state = make_state([founder, rival, broker], properties)
        state['current_round'] = 5
        state['pending_debts'] = [
            {
                'debtor_id': 1,
                'creditor_id': 2,
                'amount_due': 120.0,
                'original_amount': 120.0,
            },
        ]

        prepared_state = ensure_social_state(state)
        prepared_founder = next(player for player in prepared_state['players'] if player['id'] == 1)

        self.assertTrue(prepared_founder['plot_can_found'])
        self.assertGreaterEqual(prepared_founder['plot_hardship_trigger_count'], 2)

        founded_state, result = start_communist_plot(prepared_state, player_id=1)

        plot = founded_state['social']['plot']
        updated_founder = next(player for player in founded_state['players'] if player['id'] == 1)

        self.assertTrue(plot['exists'])
        self.assertEqual(plot['founder_id'], 1)
        self.assertEqual(plot['stage'], 1)
        self.assertEqual(plot['support'], min(8, 4 + prepared_founder['plot_hardship_score']))
        self.assertIn(1, plot['member_ids'])
        self.assertEqual(updated_founder['plot_role'], 'founder')
        self.assertIn('founded the communist plot', result['summary'].lower())

    def test_plot_founder_is_locked_to_poverty_and_surplus_moves_to_savings(self):
        founder = make_player(1, 'Atlas', 90)
        rival = make_player(2, 'Rival', 900)
        broker = make_player(3, 'Broker', 1100)
        state = make_state(
            [founder, rival, broker],
            [
                make_property(1, 1, board_position=2, base_price=100, dev_level=0),
                make_property(2, 2, board_position=4, base_price=180, dev_level=2),
                make_property(3, 3, board_position=9, base_price=220, dev_level=2),
            ],
        )
        state['current_round'] = 5
        state['pending_debts'] = [{
            'debtor_id': 1,
            'creditor_id': 2,
            'amount_due': 120.0,
            'original_amount': 120.0,
        }]

        founded_state, _ = start_communist_plot(ensure_social_state(state), player_id=1)
        founder_after_start = next(player for player in founded_state['players'] if player['id'] == 1)
        self.assertTrue(founder_after_start['plot_locked_poverty'])
        self.assertEqual(founder_after_start['plot_max_development_level'], 3)

        enriched_state = dict(founded_state)
        enriched_state['players'] = [
            {**player, 'balance': 320.0} if player['id'] == 1 else dict(player)
            for player in founded_state['players']
        ]
        normalized_state = ensure_social_state(enriched_state)
        normalized_founder = next(player for player in normalized_state['players'] if player['id'] == 1)

        self.assertEqual(normalized_founder['balance'], 150.0)
        self.assertEqual(normalized_founder['plot_savings_balance'], 170.0)

    def test_plot_founder_savings_rescue_prevents_bankruptcy(self):
        founder = make_player(1, 'Atlas', 90)
        rival = make_player(2, 'Rival', 900)
        broker = make_player(3, 'Broker', 1100)
        state = make_state(
            [founder, rival, broker],
            [
                make_property(1, 1, board_position=2, base_price=100, dev_level=0),
                make_property(2, 2, board_position=4, base_price=180, dev_level=2),
                make_property(3, 3, board_position=9, base_price=220, dev_level=2),
            ],
        )
        state['current_round'] = 5
        founded_state, _ = start_communist_plot(ensure_social_state(state), player_id=1)
        distressed_state = dict(founded_state)
        distressed_state['players'] = [
            {**player, 'balance': -60.0, 'plot_savings_balance': 140.0} if player['id'] == 1 else dict(player)
            for player in founded_state['players']
        ]

        rescued_state = check_bankruptcy(distressed_state, 12, FakeRedis(), FakeSocket(), player_id=1)
        rescued_founder = next(player for player in rescued_state['players'] if player['id'] == 1)

        self.assertFalse(rescued_founder['is_bankrupt'])
        self.assertEqual(rescued_founder['balance'], 0.0)
        self.assertEqual(rescued_founder['plot_savings_balance'], 80.0)

    def test_plot_cannot_be_founded_after_building_out_a_monopoly(self):
        founder = make_player(1, 'Atlas', 70)
        rival = make_player(2, 'Rival', 900)
        broker = make_player(3, 'Broker', 1100)
        state = make_state(
            [founder, rival, broker],
            [
                make_property(1, 1, board_position=2, base_price=180, dev_level=4, group_color='#8B4513'),
                make_property(2, 1, board_position=4, base_price=200, dev_level=3, group_color='#8B4513'),
                make_property(3, 2, board_position=9, base_price=220, dev_level=1, group_color='#EC4899'),
                make_property(4, 3, board_position=10, base_price=240, dev_level=1, group_color='#EC4899'),
            ],
        )
        state['current_round'] = 5
        state['pending_debts'] = [{
            'debtor_id': 1,
            'creditor_id': 2,
            'amount_due': 140.0,
            'original_amount': 140.0,
        }]

        prepared_state = ensure_social_state(state)
        prepared_founder = next(player for player in prepared_state['players'] if player['id'] == 1)

        self.assertGreaterEqual(prepared_founder['plot_hardship_trigger_count'], 2)
        self.assertFalse(prepared_founder['plot_can_found'])
        with self.assertRaisesRegex(ValueError, 'built-out monopoly|development cap|heavily developed'):
            start_communist_plot(prepared_state, player_id=1)

    def test_plot_leave_releases_founder_poverty_lock_and_saved_cash(self):
        founder = make_player(1, 'Atlas', 320)
        rival = make_player(2, 'Rival', 900)
        broker = make_player(3, 'Broker', 1100)
        state = make_state(
            [founder, rival, broker],
            [
                make_property(1, 1, board_position=2, base_price=100, dev_level=0),
                make_property(2, 2, board_position=4, base_price=180, dev_level=2),
                make_property(3, 3, board_position=9, base_price=220, dev_level=2),
            ],
        )
        state['current_round'] = 5
        founded_state, _ = start_communist_plot(ensure_social_state(state), player_id=1)

        left_state, result = submit_plot_leave(founded_state, player_id=1)
        founder_after_leave = next(player for player in left_state['players'] if player['id'] == 1)

        self.assertTrue(result['success'])
        self.assertFalse(founder_after_leave['plot_locked_poverty'])
        self.assertEqual(founder_after_leave['plot_savings_balance'], 0.0)
        self.assertEqual(founder_after_leave['balance'], 320.0)
        self.assertIsNone(founder_after_leave['plot_role'])

    def test_plot_leave_applies_refounding_cooldown(self):
        founder = make_player(1, 'Atlas', 320)
        rival = make_player(2, 'Rival', 900)
        broker = make_player(3, 'Broker', 1100)
        state = make_state(
            [founder, rival, broker],
            [
                make_property(1, 1, board_position=2, base_price=100, dev_level=0),
                make_property(2, 2, board_position=4, base_price=180, dev_level=2),
                make_property(3, 3, board_position=9, base_price=220, dev_level=2),
            ],
        )
        state['current_round'] = 5

        founded_state, _ = start_communist_plot(ensure_social_state(state), player_id=1)
        left_state, _ = submit_plot_leave(founded_state, player_id=1)
        cooled_state = ensure_social_state(left_state)
        founder_after_leave = next(player for player in cooled_state['players'] if player['id'] == 1)

        self.assertGreater(founder_after_leave['plot_defection_cooldown_until'], cooled_state['current_round'])
        self.assertFalse(founder_after_leave['plot_can_found'])

    def test_plot_member_can_request_join_and_commander_can_accept(self):
        founder = make_player(1, 'Atlas', 90)
        applicant = make_player(2, 'Rival', 400)
        broker = make_player(3, 'Broker', 1100)
        state = make_state(
            [founder, applicant, broker],
            [
                make_property(1, 1, board_position=2, base_price=100, dev_level=0),
                make_property(2, 3, board_position=4, base_price=180, dev_level=2),
                make_property(3, 3, board_position=9, base_price=220, dev_level=2),
            ],
        )
        state['current_round'] = 5
        state['pending_debts'] = [{
            'debtor_id': 1,
            'creditor_id': 3,
            'amount_due': 120.0,
            'original_amount': 120.0,
        }]

        founded_state, _ = start_communist_plot(ensure_social_state(state), player_id=1)
        requested_state, request_result = submit_plot_join(founded_state, player_id=2, payload={'intent': 'request'})
        self.assertTrue(request_result['success'])
        self.assertIn('requested to join', request_result['summary'].lower())
        self.assertIn('2', requested_state['social']['plot']['join_requests'])

        accepted_state, accept_result = submit_plot_join(
            requested_state,
            player_id=1,
            payload={'intent': 'accept_request', 'target_player_id': 2},
        )
        accepted_applicant = next(player for player in accepted_state['players'] if player['id'] == 2)

        self.assertTrue(accept_result['success'])
        self.assertEqual(accepted_applicant['plot_role'], 'sympathizer')
        self.assertEqual(accepted_applicant['balance'], 250.0)
        self.assertNotIn('2', accepted_state['social']['plot']['join_requests'])

    def test_plot_succession_uses_rank_then_contribution(self):
        founder = make_player(1, 'Atlas', 90)
        organizer_a = make_player(2, 'Rival', 450)
        organizer_b = make_player(3, 'Broker', 450)
        state = make_state([founder, organizer_a, organizer_b], [make_property(1, 1, board_position=2)])
        state['current_round'] = 7
        state['social'] = {
            'plot': {
                'exists': True,
                'founder_id': 1,
                'stage': 3,
                'created_round': 5,
                'public': True,
                'support': 16.0,
                'supply': 9.0,
                'heat': 18.0,
                'support_generated_total': 20.0,
                'commander_id': 1,
                'members': {
                    '1': {
                        'player_id': 1,
                        'role': 'founder',
                        'is_founder': True,
                        'active': True,
                        'joined_round': 5,
                        'cash_contributed': 50.0,
                    },
                    '2': {
                        'player_id': 2,
                        'role': 'committed_member',
                        'active': True,
                        'joined_round': 5,
                        'cash_contributed': 125.0,
                    },
                    '3': {
                        'player_id': 3,
                        'role': 'committed_member',
                        'active': True,
                        'joined_round': 4,
                        'cash_contributed': 80.0,
                    },
                },
            },
        }
        state['players'][0]['is_bankrupt'] = True

        refreshed_state = ensure_social_state(state)
        plot = refreshed_state['social']['plot']

        self.assertEqual(plot['commander']['player_id'], 2)
        self.assertEqual(plot['command_chain'][0]['player_id'], 2)
        self.assertEqual(plot['command_chain'][1]['player_id'], 3)

    def test_plot_snapshot_includes_next_stage_and_promotion_progress(self):
        founder = make_player(1, 'Atlas', 120)
        recruit = make_player(2, 'Rival', 240)
        state = make_state([founder, recruit], [make_property(1, 1, board_position=2, base_price=100, dev_level=0)])
        state['current_round'] = 5
        state['social'] = {
            'plot': {
                'exists': True,
                'founder_id': 1,
                'commander_id': 1,
                'stage': 2,
                'created_round': 3,
                'public': False,
                'support': 4.0,
                'supply': 2.0,
                'heat': 25.0,
                'support_generated_total': 8.0,
                'members': {
                    '1': {
                        'player_id': 1,
                        'role': 'founder',
                        'is_founder': True,
                        'active': True,
                        'joined_round': 3,
                        'contribution_rounds': [3],
                        'required_contribution_rounds': 1,
                        'required_successful_actions': 1,
                        'successful_actions_supported': 1,
                    },
                    '2': {
                        'player_id': 2,
                        'role': 'sympathizer',
                        'active': True,
                        'joined_round': 4,
                        'contribution_rounds': [4],
                        'required_contribution_rounds': 2,
                        'required_successful_actions': 1,
                        'successful_actions_supported': 0,
                    },
                },
            },
        }

        refreshed_state = ensure_social_state(state)
        plot = refreshed_state['social']['plot']
        recruit_entry = next(entry for entry in plot['command_chain'] if entry['player_id'] == 2)

        self.assertEqual(plot['next_stage']['stage'], 3)
        self.assertEqual(plot['next_stage']['stage_name'], 'Open Seizure')
        self.assertTrue(any(entry['label'] == 'Support 4/6' for entry in plot['next_stage']['requirements']))
        self.assertEqual(recruit_entry['next_role'], 'organizer')
        self.assertEqual(recruit_entry['contribution_round_count'], 1)
        self.assertEqual(recruit_entry['required_contribution_rounds'], 2)
        self.assertFalse(recruit_entry['promotion_ready'])

    def test_plot_reintegration_requires_more_than_two_pushes_on_entrenched_property(self):
        founder = make_player(1, 'Atlas', 850)
        former_owner = make_player(2, 'Rival', 1000)
        coalition_partner = make_player(3, 'Broker', 1000)
        state = make_state(
            [founder, former_owner, coalition_partner],
            [
                make_property(1, 2, board_position=2, base_price=220, dev_level=1),
                make_property(2, 1, board_position=4, base_price=100, dev_level=0),
                make_property(3, 3, board_position=9, base_price=120, dev_level=0),
            ],
        )
        state['current_round'] = 6
        state['social'] = {
            'plot': {
                'exists': True,
                'founder_id': 1,
                'stage': 3,
                'created_round': 4,
                'public': True,
                'support': 20.0,
                'supply': 10.0,
                'heat': 10.0,
                'support_generated_total': 20.0,
                'members': {
                    '1': {
                        'player_id': 1,
                        'role': 'committed_member',
                        'is_founder': True,
                        'active': True,
                        'joined_round': 4,
                        'successful_actions_supported': 2,
                        'contribution_rounds': [4, 5],
                        'required_contribution_rounds': 2,
                        'required_successful_actions': 1,
                    },
                },
                'regions': {
                    'Africa': {
                        'seeded_cells': 1,
                    },
                },
            },
            'properties': {
                '1': {
                    'plot_agitation': 3,
                },
            },
        }

        seized_state, _ = submit_plot_action(state, player_id=1, action_type='attempt_seizure', payload={'property_id': 1})
        fortified_state, _ = submit_plot_action(seized_state, player_id=1, action_type='fortify_property', payload={'property_id': 1})
        coalition_state, _ = submit_plot_counter_action(fortified_state, player_id=2, action_type='join_coalition')
        coalition_state, _ = submit_plot_counter_action(coalition_state, player_id=3, action_type='join_coalition')

        first_push_state, _ = submit_plot_counter_action(
            coalition_state,
            player_id=2,
            action_type='reintegration_campaign',
            payload={'property_id': 1, 'supporter_ids': [2]},
        )
        second_push_state, second_push = submit_plot_counter_action(
            first_push_state,
            player_id=3,
            action_type='reintegration_campaign',
            payload={'property_id': 1, 'supporter_ids': [3]},
        )

        second_entry = second_push_state['social']['properties']['1']
        self.assertTrue(second_push['success'])
        self.assertIn('pushed reintegration forward', second_push['summary'].lower())
        self.assertTrue(second_entry['plot_seized'])
        self.assertLess(second_entry['plot_reintegration_progress'], 100)

    def test_reintegration_waives_supporter_requirement_when_no_cosponsor_exists(self):
        founder = make_player(1, 'Atlas', 850)
        former_owner = make_player(2, 'Rival', 1000)
        state = make_state(
            [founder, former_owner],
            [
                make_property(1, 2, board_position=2, base_price=220, dev_level=1),
                make_property(2, 1, board_position=4, base_price=100, dev_level=0),
            ],
        )
        state['current_round'] = 6
        state['social'] = {
            'plot': {
                'exists': True,
                'founder_id': 1,
                'stage': 3,
                'created_round': 4,
                'public': True,
                'support': 20.0,
                'supply': 10.0,
                'heat': 10.0,
                'support_generated_total': 20.0,
                'members': {
                    '1': {
                        'player_id': 1,
                        'role': 'committed_member',
                        'is_founder': True,
                        'active': True,
                        'joined_round': 4,
                        'successful_actions_supported': 2,
                        'contribution_rounds': [4, 5],
                        'required_contribution_rounds': 2,
                        'required_successful_actions': 1,
                    },
                },
                'regions': {
                    'Africa': {
                        'seeded_cells': 1,
                    },
                },
            },
            'properties': {
                '1': {
                    'plot_agitation': 3,
                },
            },
        }

        seized_state, _ = submit_plot_action(state, player_id=1, action_type='attempt_seizure', payload={'property_id': 1})
        coalition_state, _ = submit_plot_counter_action(seized_state, player_id=2, action_type='join_coalition')
        reintegration_state, result = submit_plot_counter_action(
            coalition_state,
            player_id=2,
            action_type='reintegration_campaign',
            payload={'property_id': 1},
        )

        self.assertTrue(result['success'])
        self.assertIn('pushed reintegration forward', result['summary'].lower())
        self.assertTrue(reintegration_state['social']['properties']['1']['plot_seized'])

    def test_plot_seizure_can_be_reintegrated_by_coalition(self):
        founder = make_player(1, 'Atlas', 850)
        former_owner = make_player(2, 'Rival', 1000)
        coalition_partner = make_player(3, 'Broker', 1000)
        properties = [
            make_property(1, 2, board_position=2, base_price=220, dev_level=1),
            make_property(2, 1, board_position=4, base_price=100, dev_level=0),
            make_property(3, 3, board_position=9, base_price=120, dev_level=0),
        ]
        state = make_state([founder, former_owner, coalition_partner], properties)
        state['current_round'] = 6
        state['social'] = {
            'plot': {
                'exists': True,
                'founder_id': 1,
                'stage': 3,
                'created_round': 4,
                'public': True,
                'support': 20.0,
                'supply': 10.0,
                'heat': 10.0,
                'support_generated_total': 20.0,
                'members': {
                    '1': {
                        'player_id': 1,
                        'role': 'committed_member',
                        'is_founder': True,
                        'active': True,
                        'joined_round': 4,
                        'successful_actions_supported': 2,
                        'contribution_rounds': [4, 5],
                        'required_contribution_rounds': 2,
                        'required_successful_actions': 1,
                    },
                },
                'regions': {
                    'Africa': {
                        'seeded_cells': 1,
                    },
                },
            },
            'properties': {
                '1': {
                    'plot_agitation': 3,
                },
            },
        }

        seized_state, seizure_result = submit_plot_action(
            state,
            player_id=1,
            action_type='attempt_seizure',
            payload={'property_id': 1},
        )

        self.assertTrue(seizure_result['success'])
        self.assertEqual(next(prop for prop in seized_state['properties'] if prop['id'] == 1)['owner_id'], COMMUNIST_PLOT_OWNER_ID)

        coalition_state, _ = submit_plot_counter_action(
            seized_state,
            player_id=2,
            action_type='join_coalition',
        )
        coalition_state, _ = submit_plot_counter_action(
            coalition_state,
            player_id=3,
            action_type='join_coalition',
        )

        first_push_state, first_push = submit_plot_counter_action(
            coalition_state,
            player_id=2,
            action_type='reintegration_campaign',
            payload={
                'property_id': 1,
                'supporter_ids': [2],
            },
        )
        first_push_state = {**first_push_state, 'current_round': 7}
        second_push_state, second_push = submit_plot_counter_action(
            first_push_state,
            player_id=3,
            action_type='reintegration_campaign',
            payload={
                'property_id': 1,
                'supporter_ids': [3],
            },
        )
        second_push_state = {**second_push_state, 'current_round': 8}

        final_state, third_push = submit_plot_counter_action(
            second_push_state,
            player_id=2,
            action_type='reintegration_campaign',
            payload={
                'property_id': 1,
                'supporter_ids': [2],
            },
        )

        restored_property = next(prop for prop in final_state['properties'] if prop['id'] == 1)
        restored_entry = final_state['social']['properties']['1']

        self.assertIn('pushed reintegration forward', first_push['summary'].lower())
        self.assertTrue(second_push['success'])
        self.assertIn('pushed reintegration forward', second_push['summary'].lower())
        self.assertIn('reintegrated', third_push['summary'].lower())
        self.assertEqual(restored_property['owner_id'], 2)
        self.assertFalse(restored_entry['plot_seized'])
        self.assertCountEqual(final_state['social']['plot']['coalition_member_ids'], [2, 3])

    def test_debug_plot_seed_makes_human_player_the_committed_revolutionary(self):
        human = make_player(1, 'Atlas', 1200)
        rival = make_player(2, 'Rival', 900)
        broker = make_player(3, 'Broker', 950)
        properties = [
            make_property(1, 2, board_position=23, base_price=240, dev_level=2),
            make_property(2, 2, board_position=24, base_price=260, dev_level=1),
            make_property(3, 3, board_position=26, base_price=260, dev_level=1),
            make_property(4, 1, board_position=2, base_price=60, dev_level=0),
        ]
        state = make_state([human, rival, broker], properties)
        state['current_round'] = 4

        debug_state, result = seed_debug_communist_plot_state(state, revolutionary_player_id=1)

        plot = debug_state['social']['plot']
        founder = next(player for player in debug_state['players'] if player['id'] == 1)
        seized_positions = sorted(
            prop['board_position']
            for prop in debug_state['properties']
            if prop['owner_id'] == COMMUNIST_PLOT_OWNER_ID
        )

        self.assertTrue(plot['exists'])
        self.assertTrue(plot['public'])
        self.assertEqual(plot['founder_id'], 1)
        self.assertEqual(founder['plot_role'], 'committed_member')
        self.assertEqual(debug_state['current_player_id'], 1)
        self.assertGreaterEqual(len(seized_positions), 1)
        self.assertIn('Atlas', result['summary'])
        self.assertGreaterEqual(plot['support'], 10)

    def test_debug_plot_seed_can_use_unowned_properties(self):
        human = make_player(1, 'Atlas', 1200)
        rival = make_player(2, 'Rival', 900)
        broker = make_player(3, 'Broker', 950)
        properties = [
            make_property(1, None, board_position=23, base_price=240, dev_level=2),
            make_property(2, None, board_position=24, base_price=260, dev_level=1),
            make_property(3, None, board_position=26, base_price=260, dev_level=1),
            make_property(4, 1, board_position=2, base_price=60, dev_level=0),
        ]
        state = make_state([human, rival, broker], properties)

        debug_state, _ = seed_debug_communist_plot_state(state, revolutionary_player_id=1)

        seized_entries = [
            debug_state['social']['properties'][str(prop['id'])]
            for prop in debug_state['properties']
            if prop['owner_id'] == COMMUNIST_PLOT_OWNER_ID
        ]
        self.assertTrue(seized_entries)
        self.assertTrue(all(entry['plot_former_owner_id'] in {2, 3} for entry in seized_entries))

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
            make_property(1, 1, board_position=2, group_color='#8B4513', base_price=60),
            make_property(2, 1, board_position=4, group_color='#8B4513', base_price=60),
            make_property(3, 1, board_position=9, group_color='#8B4513', base_price=100),
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
