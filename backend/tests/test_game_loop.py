import os
import sys
import unittest
import json
from unittest.mock import patch

from flask import Flask


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import db  # noqa: E402
from app.engine import game_loop  # noqa: E402
from app.models.policy import get_lobbying_axes, get_lobbying_policy_definition  # noqa: E402


class FakeRedis:
    def __init__(self):
        self.values = {}
        self.lists = {}

    def get(self, key):
        return self.values.get(key)

    def set(self, key, value, ex=None):
        self.values[key] = value

    def delete(self, key):
        self.values.pop(key, None)
        self.lists.pop(key, None)

    def rpush(self, key, value):
        self.lists.setdefault(key, []).append(value)

    def ltrim(self, key, start, stop):
        items = self.lists.get(key, [])
        if not items:
            return
        normalized_stop = None if stop == -1 else stop + 1
        self.lists[key] = items[start:normalized_stop]


class FakeSocket:
    def __init__(self):
        self.background_tasks = []
        self.emits = []
        self.sleeps = []

    def emit(self, event, payload, room=None):
        self.emits.append((event, payload, room))

    def sleep(self, seconds):
        self.sleeps.append(seconds)

    def start_background_task(self, target, *args):
        self.background_tasks.append((target, args))


class GameLoopBoardMigrationTests(unittest.TestCase):
    def test_synchronize_property_metadata_prunes_newly_removed_positions(self):
        state = {
            'board_layout_version': 4,
            'current_round': 6,
            'current_turn_index': 2,
            'players': [
                {'id': 1, 'username': 'Atlas', 'balance': 500.0, 'current_position': 1},
                {'id': 2, 'username': 'Rival', 'balance': 300.0, 'current_position': 42},
            ],
            'properties': [
                {
                    'id': 11,
                    'name': 'Lagos',
                    'board_position': 1,
                    'owner_id': 1,
                    'current_value': 60.0,
                    'base_price': 60.0,
                    'property_type': 'property',
                },
                {
                    'id': 24,
                    'name': 'Paris',
                    'board_position': 23,
                    'owner_id': 2,
                    'current_value': 240.0,
                    'base_price': 240.0,
                    'property_type': 'property',
                    'group_color': '#EAB308',
                    'region': 'Western Europe',
                },
            ],
            'pending_action': {
                'type': 'buy_property',
                'property_id': 999,
                'position': 42,
            },
            'log_buffer': [],
        }

        next_state, updated = game_loop._synchronize_property_metadata(state)

        self.assertTrue(updated)
        self.assertEqual(next_state['board_layout_version'], game_loop.BOARD_LAYOUT_VERSION)
        player_by_id = {player['id']: player for player in next_state['players']}
        self.assertEqual(player_by_id[1]['current_position'], 2)
        self.assertEqual(player_by_id[2]['current_position'], 47)
        self.assertEqual(player_by_id[1]['balance'], 560.0)
        self.assertEqual([prop['board_position'] for prop in next_state['properties']], [23])
        self.assertIsNone(next_state['pending_action'])
        self.assertTrue(any('Lagos' in entry['description'] for entry in next_state['log_buffer']))


class GovernmentModeDefinitionTests(unittest.TestCase):
    def test_liberal_democracy_initialization_includes_market_mechanics(self):
        gov = game_loop.initialize_government('liberal_democracy')

        self.assertTrue(gov['bailout_enabled'])
        self.assertGreater(gov['market_confidence'], 0)
        self.assertGreater(gov['capital_yield_rate'], 0)
        self.assertGreaterEqual(gov['private_equity_bonus_multiplier'], 1.0)

    def test_capital_markets_axis_is_only_visible_under_liberal_democracy(self):
        liberal_axes = {axis['axis'] for axis in get_lobbying_axes(government_type='liberal_democracy')}
        social_axes = {axis['axis'] for axis in get_lobbying_axes(government_type='social_democracy')}

        self.assertIn('capital_markets', liberal_axes)
        self.assertIn('cash_bonus', liberal_axes)
        self.assertIn('investor_mood', liberal_axes)
        self.assertNotIn('capital_markets', social_axes)
        self.assertNotIn('cash_bonus', social_axes)
        self.assertNotIn('investor_mood', social_axes)
        self.assertIsNone(
            get_lobbying_policy_definition(
                target='market_deregulation',
                government_type='social_democracy',
            )
        )
        self.assertIsNone(
            get_lobbying_policy_definition(
                target='cash_bonus_increase',
                government_type='social_democracy',
            )
        )
        self.assertIsNone(
            get_lobbying_policy_definition(
                target='investor_mood_increase',
                government_type='social_democracy',
            )
        )


class JailReleaseTests(unittest.TestCase):
    def test_release_player_from_jail_makes_release_effective_immediately(self):
        state = {
            'current_player_id': 1,
            'dice_rolled_this_turn': True,
            'awaiting_end_turn_player_id': 1,
            'players': [
                {
                    'id': 1,
                    'username': 'Atlas',
                    'balance': 400.0,
                    'is_jailed': True,
                    'jail_turns_remaining': 2,
                    'has_jail_card': True,
                },
                {
                    'id': 2,
                    'username': 'Rival',
                    'balance': 500.0,
                    'is_jailed': False,
                    'jail_turns_remaining': 0,
                    'has_jail_card': False,
                },
            ],
            'econ': {
                'treasury_balance': 300.0,
            },
        }

        next_state, released_player = game_loop.release_player_from_jail(state, 1, bail_amount=50.0)

        self.assertIsNotNone(released_player)
        self.assertFalse(released_player['is_jailed'])
        self.assertEqual(released_player['jail_turns_remaining'], 0)
        self.assertEqual(released_player['balance'], 350.0)
        self.assertFalse(next_state['dice_rolled_this_turn'])
        self.assertIsNone(next_state['awaiting_end_turn_player_id'])
        self.assertEqual(next_state['econ']['treasury_balance'], 350.0)


class GameLoopTurnTimeoutTests(unittest.TestCase):
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

    def test_schedule_turn_timeout_does_not_restart_same_turn_marker(self):
        redis_client = FakeRedis()
        socket = FakeSocket()
        state = {
            'status': 'active',
            'current_round': 4,
            'current_turn_index': 1,
            'current_player_id': 7,
            'settings': {
                'turn_timer_enabled': True,
                'turn_time_limit_seconds': 45,
            },
        }

        game_loop.schedule_turn_timeout(state, 19, redis_client, socket)
        first_token = redis_client.get(game_loop._turn_timeout_token_key(19))
        game_loop.schedule_turn_timeout(dict(state), 19, redis_client, socket)

        self.assertEqual(len(socket.background_tasks), 1)
        self.assertEqual(redis_client.get(game_loop._turn_timeout_token_key(19)), first_token)

    def test_resolve_turn_timeout_declines_pending_property_before_ending_turn(self):
        redis_client = FakeRedis()
        socket = FakeSocket()
        state = {
            'status': 'active',
            'current_round': 2,
            'current_turn_index': 0,
            'current_player_id': 1,
            'players': [
                {'id': 1, 'username': 'Atlas', 'balance': 900.0},
                {'id': 2, 'username': 'Rival', 'balance': 900.0},
            ],
            'properties': [
                {'id': 11, 'name': 'Cairo', 'owner_id': None, 'board_position': 4},
            ],
            'pending_action': {
                'type': 'buy_property',
                'player_id': 1,
                'property_id': 11,
                'property': {'id': 11, 'name': 'Cairo', 'owner_id': None, 'board_position': 4},
            },
            'pending_turn_context': {'player_id': 1, 'dice_result': {'is_doubles': False}},
            'pending_debts': [],
            'econ': {},
            'settings': {'auction_enabled': True, 'turn_timer_enabled': True, 'turn_time_limit_seconds': 45},
            'log_buffer': [],
        }

        def fake_end_turn(game_state, *_args, **_kwargs):
            return {
                **game_state,
                'current_player_id': 2,
                'current_turn_index': 1,
            }

        with patch.object(game_loop, 'start_auction') as start_auction, patch.object(
            game_loop,
            'check_bankruptcy',
            side_effect=lambda game_state, *_args, **_kwargs: game_state,
        ), patch.object(game_loop, 'end_turn', side_effect=fake_end_turn):
            next_state = game_loop._resolve_turn_timeout(state, 1, 55, redis_client, socket)

        start_auction.assert_called_once()
        self.assertIsNone(next_state.get('pending_action'))
        self.assertIsNone(next_state.get('pending_turn_context'))
        self.assertTrue(any(
            event == 'log_entry' and 'Cairo was declined' in payload.get('description', '')
            for event, payload, _room in socket.emits
        ))


class GameStateSnapshotPreparationTests(unittest.TestCase):
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

    def test_broadcast_reuses_prepared_snapshot_from_persist(self):
        redis_client = FakeRedis()
        socket = FakeSocket()
        state = {
            'players': [],
            'properties': [],
            'econ': {},
            'settings': {},
            'social': {},
            'log_buffer': [],
        }
        call_counts = {
            'ensure_regime_economy_state': 0,
            'ensure_tax_stats': 0,
            'ensure_lobbying_stats': 0,
            'record_player_finance_snapshot': 0,
            'ensure_social_state': 0,
            'attach_deals_snapshot': 0,
        }

        def mark(name, result_builder):
            def wrapper(*args, **kwargs):
                call_counts[name] += 1
                return result_builder(*args, **kwargs)
            return wrapper

        with patch.object(
            game_loop,
            'ensure_regime_economy_state',
            side_effect=mark('ensure_regime_economy_state', lambda econ, _settings: {**econ, 'prepared': True}),
        ), patch.object(
            game_loop,
            'ensure_tax_stats',
            side_effect=mark('ensure_tax_stats', lambda snapshot: {**snapshot, 'tax_stats': {'prepared': True}}),
        ), patch.object(
            game_loop,
            'ensure_lobbying_stats',
            side_effect=mark('ensure_lobbying_stats', lambda snapshot: {**snapshot, 'lobbying_stats': {'prepared': True}}),
        ), patch.object(
            game_loop,
            'record_player_finance_snapshot',
            side_effect=mark('record_player_finance_snapshot', lambda snapshot: {**snapshot, 'player_finance_history': {'last_fingerprint': 'prepared'}}),
        ), patch.object(
            game_loop,
            'ensure_social_state',
            side_effect=mark('ensure_social_state', lambda snapshot: {**snapshot, 'social': {**snapshot.get('social', {}), 'prepared': True}}),
        ), patch.object(
            game_loop,
            'attach_deals_snapshot',
            side_effect=mark('attach_deals_snapshot', lambda snapshot, _match_id: {**snapshot, 'deals': []}),
        ), patch('app.engine.bots.queue_bot_state_evaluation') as queue_bot_state_evaluation:
            game_loop.persist_game_state(state, 77, redis_client)
            game_loop.broadcast_game_state_snapshot(socket, 77, state)

        self.assertEqual(call_counts['ensure_regime_economy_state'], 1)
        self.assertEqual(call_counts['ensure_tax_stats'], 1)
        self.assertEqual(call_counts['ensure_lobbying_stats'], 1)
        self.assertEqual(call_counts['record_player_finance_snapshot'], 1)
        self.assertEqual(call_counts['ensure_social_state'], 1)
        self.assertEqual(call_counts['attach_deals_snapshot'], 1)
        self.assertEqual(state.get('_runtime_snapshot_prepared_for_match_id'), 77)
        emitted_state = socket.emits[0][1]['state']
        self.assertNotIn('_runtime_snapshot_prepared_for_match_id', emitted_state)
        persisted_state = json.loads(redis_client.get('game:77:state'))
        self.assertNotIn('_runtime_snapshot_prepared_for_match_id', persisted_state)
        queue_bot_state_evaluation.assert_called_once()

    def test_turn_timeout_task_logs_and_ends_turn(self):
        redis_client = FakeRedis()
        socket = FakeSocket()
        state = {
            'status': 'active',
            'current_round': 3,
            'current_turn_index': 0,
            'current_player_id': 1,
            'players': [
                {'id': 1, 'username': 'Atlas', 'balance': 1100.0},
                {'id': 2, 'username': 'Rival', 'balance': 1100.0},
            ],
            'properties': [],
            'pending_debts': [],
            'econ': {},
            'settings': {'turn_timer_enabled': True, 'turn_time_limit_seconds': 30},
            'log_buffer': [],
        }
        turn_marker = game_loop._turn_timeout_marker(state)
        redis_client.set(game_loop._turn_timeout_token_key(77), 'token-1')
        redis_client.set(game_loop._turn_timeout_marker_key(77), turn_marker)

        persisted = {}

        def fake_end_turn(game_state, *_args, **_kwargs):
            return {
                **game_state,
                'current_player_id': 2,
                'current_turn_index': 1,
            }

        def fake_persist(game_state, *_args, **_kwargs):
            persisted['state'] = dict(game_state)

        with patch.object(game_loop, 'load_game_state', return_value=dict(state)), patch.object(
            game_loop,
            'check_bankruptcy',
            side_effect=lambda game_state, *_args, **_kwargs: game_state,
        ), patch.object(game_loop, 'end_turn', side_effect=fake_end_turn) as end_turn, patch.object(
            game_loop,
            'persist_game_state',
            side_effect=fake_persist,
        ) as persist_game_state, patch.object(game_loop, 'broadcast_game_state_snapshot') as broadcast_snapshot:
            game_loop._turn_timeout_task(self.app, 77, 1, turn_marker, 'token-1', 30, redis_client, socket)

        self.assertEqual(socket.sleeps, [30])
        end_turn.assert_called_once()
        persist_game_state.assert_called_once()
        broadcast_snapshot.assert_called_once()
        self.assertEqual(persisted['state']['current_player_id'], 2)
        self.assertTrue(any(
            event == 'log_entry' and payload.get('event_type') == 'turn_timeout'
            for event, payload, _room in socket.emits
        ))


class GameLoopTaxLandingRegressionTests(unittest.TestCase):
    def _build_state(self, start_position):
        return {
            'match_id': 1,
            'status': 'active',
            'current_round': 3,
            'current_turn_index': 0,
            'turn_order': [1, 2],
            'current_player_id': 1,
            'players': [
                {
                    'id': 1,
                    'username': 'Atlas',
                    'balance': 1000.0,
                    'current_position': start_position,
                    'is_jailed': False,
                    'jail_turns_remaining': 0,
                    'consecutive_doubles': 0,
                    'is_bankrupt': False,
                    'is_connected': True,
                },
                {
                    'id': 2,
                    'username': 'Rival',
                    'balance': 1000.0,
                    'current_position': 0,
                    'is_jailed': False,
                    'jail_turns_remaining': 0,
                    'consecutive_doubles': 0,
                    'is_bankrupt': False,
                    'is_connected': True,
                },
            ],
            'properties': [],
            'econ': {
                'tax_multiplier': 0.15,
                'treasury_balance': 5000.0,
                'stability': 0.7,
                'inflation_rate': 0.02,
                'government_type': 'liberal_democracy',
                'gov_type': 'liberal_democracy',
            },
            'settings': {
                'income_tax_on_pass_go': True,
                'go_salary': 200,
                'double_on_go': False,
                'tax_every_turn': False,
                'property_tax_every_n_rounds': 5,
                'hyper_inflation_trigger': False,
                'free_parking_pot_enabled': False,
            },
            'tax_stats': {
                'player_totals': {},
                'totals': {},
                'last_welfare_distribution': None,
                'budget_history': [],
            },
            'pending_debts': [],
            'log_buffer': [],
        }

    def test_run_turn_records_sparse_board_tax_tiles_without_crashing(self):
        cases = [
            {'start': 38, 'destination': 39, 'tax_key': 'luxury_tax'},
            {'start': 40, 'destination': 47, 'tax_key': 'super_tax'},
        ]

        for case in cases:
            with self.subTest(destination=case['destination']):
                redis_client = FakeRedis()
                socket = FakeSocket()
                state = self._build_state(case['start'])
                dice_result = {'die1': 1, 'die2': 0, 'total': 1, 'is_doubles': False}

                with patch.object(game_loop, 'load_game_state', return_value=state), patch.object(
                    game_loop,
                    'persist_game_state',
                    side_effect=lambda game_state, *_args, **_kwargs: None,
                ), patch.object(
                    game_loop,
                    'broadcast_game_state_snapshot',
                    side_effect=lambda *_args, **_kwargs: None,
                ), patch.object(
                    game_loop,
                    'schedule_turn_timeout',
                    side_effect=lambda *_args, **_kwargs: None,
                ), patch.object(
                    game_loop,
                    'check_bankruptcy',
                    side_effect=lambda game_state, *_args, **_kwargs: game_state,
                ), patch.object(
                    game_loop,
                    'check_win_condition',
                    return_value=None,
                ), patch.object(
                    game_loop,
                    'attach_deals_snapshot',
                    side_effect=lambda game_state, *_args, **_kwargs: game_state,
                ), patch.object(
                    game_loop,
                    'ensure_social_state',
                    side_effect=lambda game_state, *_args, **_kwargs: game_state,
                ), patch.object(
                    game_loop,
                    'record_player_finance_snapshot',
                    side_effect=lambda game_state, *_args, **_kwargs: game_state,
                ), patch.object(
                    game_loop,
                    'drift_economy',
                    side_effect=lambda econ, *_args, **_kwargs: econ,
                ), patch.object(
                    game_loop,
                    'apply_hyper_inflation',
                    side_effect=lambda econ, props, *_args, **_kwargs: (econ, props),
                ):
                    result = game_loop.run_turn(1, 1, dice_result, redis_client, socket)

                player = next(player for player in result['players'] if player['id'] == 1)

                self.assertEqual(player['current_position'], case['destination'])
                self.assertEqual(result.get('awaiting_end_turn_player_id'), 1)
                self.assertTrue(result.get('dice_rolled_this_turn'))
                self.assertGreater(result['tax_stats']['totals'].get(case['tax_key'], 0), 0)
                self.assertTrue(any(event == 'player_moved' for event, _payload, _room in socket.emits))


class GameLoopPlotVictoryTests(unittest.TestCase):
    def test_end_turn_emits_faction_game_over_after_round_end_plot_resolution(self):
        redis_client = FakeRedis()
        socket = FakeSocket()
        state = {
            'status': 'active',
            'current_round': 8,
            'current_turn_index': 1,
            'turn_order': [1, 2],
            'current_player_id': 2,
            'awaiting_end_turn_player_id': 2,
            'dice_rolled_this_turn': True,
            'players': [
                {'id': 1, 'username': 'Atlas', 'balance': 800.0, 'is_bankrupt': False},
                {'id': 2, 'username': 'Rival', 'balance': 900.0, 'is_bankrupt': False},
            ],
            'properties': [],
            'pending_debts': [],
            'econ': {},
            'settings': {
                'welfare_system_enabled': False,
                'lobbying_enabled': False,
                'policy_voting_enabled': False,
                'uprisings_enabled': True,
            },
            'social': {
                'plot': {
                    'exists': True,
                },
            },
            'log_buffer': [],
        }
        observed = {}

        def fake_resolve_end_of_round_social_state(game_state, *_args, **_kwargs):
            observed['round'] = game_state['current_round']
            return {
                **game_state,
                'social': {
                    'plot': {
                        'exists': True,
                        'victory_countdown': {'completed': True},
                        'committed_member_ids': [1],
                        'control_percent': 35.0,
                    },
                },
            }

        with patch.object(
            game_loop,
            'decrement_turn_deadlines',
            side_effect=lambda game_state, *_args, **_kwargs: game_state,
        ), patch.object(
            game_loop,
            'pay_welfare',
            side_effect=lambda players, econ, settings: (players, econ, {'successful': False, 'reason': 'disabled'}),
        ), patch.object(
            game_loop,
            'apply_capital_yield',
            side_effect=lambda players, econ, settings: (players, econ, {'successful': False}),
        ), patch.object(
            game_loop,
            'update_approval_ratings',
            side_effect=lambda players, econ: players,
        ), patch.object(
            game_loop,
            'record_budget_history_snapshot',
            side_effect=lambda game_state, *_args, **_kwargs: game_state,
        ), patch.object(
            game_loop,
            'resolve_end_of_round_social_state',
            side_effect=fake_resolve_end_of_round_social_state,
        ), patch.object(
            game_loop,
            'decrement_round_deadlines',
            side_effect=lambda game_state, *_args, **_kwargs: game_state,
        ):
            next_state = game_loop.end_turn(
                state,
                2,
                {'is_doubles': False},
                88,
                redis_client,
                socket,
                state['settings'],
                state['econ'],
                state['current_round'],
            )

        self.assertEqual(observed['round'], 9)
        self.assertEqual(next_state['status'], 'completed')
        self.assertEqual(next_state['winner']['type'], 'faction')
        self.assertEqual(next_state['winner']['committed_member_ids'], [1])
        self.assertEqual(next_state['winner']['victory_round'], 9)
        self.assertTrue(any(event == 'game_over' and payload['winner']['type'] == 'faction' for event, payload, _room in socket.emits))
        self.assertFalse(any(event == 'turn_start' for event, _payload, _room in socket.emits))


if __name__ == '__main__':
    unittest.main()