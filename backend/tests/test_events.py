import json
import os
import sys


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from flask import Flask, current_app  # noqa: E402
from unittest.mock import patch  # noqa: E402

import unittest

from app import db  # noqa: E402
from app.engine import events  # noqa: E402
from app.engine import game_loop  # noqa: E402


class FakeRedis:
    def __init__(self):
        self.values = {}
        self.lists = {}

    def get(self, key):
        return self.values.get(key)

    def set(self, key, value, ex=None):
        self.values[key] = value

    def lindex(self, key, index):
        items = self.lists.get(key, [])
        if 0 <= index < len(items):
            return items[index]
        return None

    def lpop(self, key):
        items = self.lists.get(key, [])
        if items:
            return items.pop(0)
        return None

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
        self.emits = []
        self.sleeps = []

    def emit(self, event, payload, room=None):
        self.emits.append((event, payload, room))

    def sleep(self, seconds):
        self.sleeps.append(seconds)


class EventEngineTests(unittest.TestCase):
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

    def test_advance_to_position_can_draw_nested_chance_card(self):
        redis_client = FakeRedis()
        socket = FakeSocket()
        nested_card = {
            'card_text': 'Collect 50',
            'effect_type': 'collect',
            'effect_value': 50,
        }
        redis_client.lists['game:77:chance_deck'] = [json.dumps(nested_card)]

        player = {
            'id': 1,
            'username': 'Atlas',
            'balance': 1000,
            'current_position': 8,
            'team_id': None,
        }
        game_state = {
            'players': [dict(player)],
            'properties': [],
            'pending_debts': [],
            'free_parking_pot': 0.0,
        }
        card = {
            'card_text': 'Advance to Chance',
            'effect_type': 'advance_to_position',
            'effect_value': 22,
        }

        updated_player, updated_state, _, logs = events.apply_card_effect(
            card,
            player,
            game_state,
            {'treasury_balance': 0, 'welfare_payout': 0},
            {'chance_cards_enabled': True, 'go_salary': 200, 'double_on_go': False},
            socket,
            77,
            redis_client,
        )

        self.assertEqual(updated_player['current_position'], 22)
        self.assertEqual(updated_player['balance'], 1050)
        self.assertEqual(updated_state['players'][0]['balance'], 1050)
        self.assertTrue(any(entry['event_type'] == 'chance_card' for entry in logs))
        self.assertTrue(any(event == 'card_drawn' for event, _, _ in socket.emits))

    def test_auction_auto_close_runs_with_app_context(self):
        redis_client = FakeRedis()
        socket = FakeSocket()
        redis_client.set('game:45:auction:9:active', '1')
        redis_client.set('game:45:auction:9:close_token', 'token-1')

        observed = {}

        def fake_resolve_auction(prop_id, game_state, econ, _redis_client, _socket, match_id):
            observed['resolve_app_name'] = current_app.name
            return game_state, econ, []

        def fake_broadcast(_socket, match_id, game_state):
            observed['broadcast_app_name'] = current_app.name

        with patch('app.engine.game_loop.load_game_state', return_value={'econ': {}, 'players': [], 'properties': []}), patch(
            'app.engine.events.resolve_auction',
            side_effect=fake_resolve_auction,
        ), patch('app.engine.game_loop.persist_game_state'), patch(
            'app.engine.game_loop.broadcast_game_state_snapshot',
            side_effect=fake_broadcast,
        ):
            events._auction_auto_close_task(self.app, 45, 9, 'token-1', redis_client, socket)

        self.assertEqual(observed['resolve_app_name'], self.app.name)
        self.assertEqual(observed['broadcast_app_name'], self.app.name)

    def test_income_tax_feeds_treasury_and_free_parking_claim(self):
        redis_client = FakeRedis()
        socket = FakeSocket()
        player = {
            'id': 1,
            'username': 'Atlas',
            'balance': 1000,
            'current_position': 5,
        }
        game_state = {
            'players': [dict(player)],
            'properties': [],
            'pending_debts': [],
            'free_parking_pot': 0.0,
        }
        econ = {'treasury_balance': 300.0, 'welfare_payout': 0.0, 'tax_multiplier': 0.15}
        settings = {'free_parking_pot_enabled': True, 'go_salary': 200}

        taxed_player, taxed_state, taxed_econ, _ = events.resolve_space(
            player,
            game_state,
            econ,
            settings,
            redis_client,
            socket,
            88,
        )

        self.assertEqual(taxed_state['free_parking_pot'], 200.0)
        self.assertEqual(taxed_econ['treasury_balance'], 500.0)
        self.assertEqual(taxed_player['balance'], 800.0)

        taxed_state = {
            **taxed_state,
            'players': [dict(taxed_player)],
        }
        free_space_player = {**taxed_player, 'current_position': 20}
        collected_player, collected_state, collected_econ, _ = events.resolve_space(
            free_space_player,
            taxed_state,
            taxed_econ,
            settings,
            redis_client,
            socket,
            88,
        )

        self.assertEqual(collected_state['free_parking_pot'], 0.0)
        self.assertEqual(collected_econ['treasury_balance'], 300.0)
        self.assertEqual(collected_player['balance'], 1000.0)

    def test_bankruptcy_bailout_requires_bailout_policy_to_be_enabled(self):
        redis_client = FakeRedis()
        socket = FakeSocket()
        base_state = {
            'players': [
                {
                    'id': 1,
                    'username': 'Atlas',
                    'balance': -50.0,
                    'is_bankrupt': False,
                },
            ],
            'properties': [],
            'pending_debts': [],
            'econ': {
                'gov_type': 'social_democracy',
                'bailout_enabled': False,
                'treasury_balance': 1000.0,
            },
            'settings': {
                'government_type': 'social_democracy',
            },
        }

        next_state, outcome = game_loop.declare_player_bankruptcy(
            dict(base_state),
            1,
            91,
            redis_client,
            socket,
        )

        self.assertFalse(outcome['bailed_out'])
        self.assertTrue(outcome['bankrupt'])
        self.assertTrue(next_state['players'][0]['is_bankrupt'])

        bailout_state = {
            **base_state,
            'players': [dict(base_state['players'][0])],
            'econ': {
                'gov_type': 'social_democracy',
                'bailout_enabled': True,
                'treasury_balance': 1000.0,
            },
        }

        rescued_state, rescued_outcome = game_loop.declare_player_bankruptcy(
            bailout_state,
            1,
            92,
            redis_client,
            socket,
        )

        self.assertTrue(rescued_outcome['bailed_out'])
        self.assertFalse(rescued_outcome['bankrupt'])
        self.assertFalse(rescued_state['players'][0].get('is_bankrupt', False))
        self.assertEqual(rescued_state['econ']['treasury_balance'], 750.0)

    def test_check_bankruptcy_auto_bails_out_eligible_active_player(self):
        redis_client = FakeRedis()
        socket = FakeSocket()
        state = {
            'players': [
                {
                    'id': 1,
                    'username': 'Atlas',
                    'balance': -19.0,
                    'is_bankrupt': False,
                },
            ],
            'properties': [],
            'pending_debts': [],
            'econ': {
                'gov_type': 'social_democracy',
                'bailout_enabled': True,
                'treasury_balance': 5000.0,
            },
            'settings': {
                'government_type': 'social_democracy',
            },
        }

        rescued_state = game_loop.check_bankruptcy(
            state,
            93,
            redis_client,
            socket,
            player_id=1,
        )

        self.assertEqual(rescued_state['players'][0]['balance'], 200.0)
        self.assertEqual(rescued_state['econ']['treasury_balance'], 4781.0)
        self.assertFalse(rescued_state['players'][0].get('is_bankrupt', False))
        self.assertTrue(any(event == 'player_bailed_out' for event, _, _ in socket.emits))


if __name__ == '__main__':
    unittest.main()