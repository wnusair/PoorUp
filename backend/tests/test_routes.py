import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import ANY, patch

from flask import Flask


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.routes.admin import admin_bp  # noqa: E402
from app.routes.auth import auth_bp  # noqa: E402
from app.routes.game import game_bp  # noqa: E402
from app.routes.lobby import lobby_bp  # noqa: E402
from app.routes import game as game_routes  # noqa: E402
from app.routes import lobby as lobby_routes  # noqa: E402
from app import socketio  # noqa: E402


class RouteSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app = Flask(__name__)
        app.config['SECRET_KEY'] = 'test'
        app.config['TESTING'] = True
        app.register_blueprint(auth_bp, url_prefix='/api/auth')
        app.register_blueprint(lobby_bp, url_prefix='/api/lobby')
        app.register_blueprint(game_bp, url_prefix='/api/game')
        app.register_blueprint(admin_bp, url_prefix='/api/admin')
        cls.app = app

    def setUp(self):
        self.client = self.app.test_client()

    def test_all_api_routes_are_registered(self):
        registered = {}
        for rule in self.app.url_map.iter_rules():
            if rule.endpoint == 'static':
                continue
            methods = registered.setdefault(rule.rule, set())
            methods.update(method for method in rule.methods if method not in {'HEAD', 'OPTIONS'})

        expected = {
            '/api/auth/register': {'POST'},
            '/api/auth/login': {'POST'},
            '/api/auth/logout': {'POST'},
            '/api/auth/me': {'GET'},
            '/api/lobby/create': {'POST'},
            '/api/lobby/join': {'POST'},
            '/api/lobby/<room_code>': {'GET'},
            '/api/lobby/<room_code>/color': {'PATCH'},
            '/api/lobby/<room_code>/ready': {'PATCH'},
            '/api/lobby/<room_code>/settings': {'PATCH'},
            '/api/lobby/<room_code>/start': {'POST'},
            '/api/lobby/<room_code>/bots': {'POST'},
            '/api/lobby/<room_code>/bots/<int:player_id>': {'PATCH', 'DELETE'},
            '/api/game/<int:match_id>/state': {'GET'},
            '/api/game/<int:match_id>/roll': {'POST'},
            '/api/game/<int:match_id>/buy': {'POST'},
            '/api/game/<int:match_id>/decline': {'POST'},
            '/api/game/<int:match_id>/auction/close': {'POST'},
            '/api/game/<int:match_id>/develop': {'POST'},
            '/api/game/<int:match_id>/mortgage': {'POST'},
            '/api/game/<int:match_id>/unmortgage': {'POST'},
            '/api/game/<int:match_id>/trade': {'POST'},
            '/api/game/<int:match_id>/trade/<int:trade_id>': {'PATCH'},
            '/api/game/<int:match_id>/lobby': {'POST'},
            '/api/game/<int:match_id>/negotiate': {'POST'},
            '/api/game/<int:match_id>/emergency-reform': {'POST'},
            '/api/game/<int:match_id>/deals': {'GET', 'POST'},
            '/api/game/<int:match_id>/deals/<int:deal_id>': {'PATCH', 'DELETE'},
            '/api/game/<int:match_id>/deals/<int:deal_id>/counter': {'POST'},
            '/api/game/<int:match_id>/team/create': {'POST'},
            '/api/game/<int:match_id>/team/invite': {'POST'},
            '/api/game/<int:match_id>/team/respond': {'PATCH'},
            '/api/game/<int:match_id>/team': {'DELETE'},
            '/api/game/<int:match_id>/log': {'GET'},
            '/api/game/<int:match_id>/jail/pay': {'POST'},
            '/api/game/<int:match_id>/jail/card': {'POST'},
            '/api/admin/<int:match_id>/kick': {'POST'},
            '/api/admin/<int:match_id>/end': {'POST'},
            '/api/admin/<int:match_id>/auction/resolve': {'POST'},
            '/api/admin/<int:match_id>/plot/debug-seed': {'POST'},
            '/api/admin/<int:match_id>/state': {'GET'},
        }

        self.assertEqual({path: set(methods) for path, methods in registered.items()}, expected)

    def test_game_state_endpoint_returns_state_for_authenticated_session(self):
        fake_match = SimpleNamespace(id=55)
        state = {
            'status': 'active',
            'board_layout_version': 6,
            'players': [],
            'properties': [],
        }

        with patch.object(game_routes, 'Match', SimpleNamespace(query=SimpleNamespace(get=lambda _match_id: fake_match))), patch.object(
            game_routes,
            'load_game_state',
            return_value=state,
        ), patch.object(game_routes, 'recover_bot_state_evaluation') as recover_bot_state:
            with self.client.session_transaction() as session:
                session['user_id'] = 7

            response = self.client.get('/api/game/55/state')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {'state': state})
        recover_bot_state.assert_called_once_with(55, state, reason='state_fetch')

    def test_lobby_color_endpoint_updates_player_and_returns_snapshot(self):
        fake_user = SimpleNamespace(id=7)
        fake_match = SimpleNamespace(id=91, status='lobby', room_code='ABCD')
        current_player = SimpleNamespace(id=1, user_id=7, color_hex='#2196F3')
        other_player = SimpleNamespace(id=2, user_id=8, color_hex='#E63946')
        lobby_state = {
            'match': {'id': 91, 'room_code': 'ABCD'},
            'players': [
                {'id': 1, 'user_id': 7, 'color_hex': '#4CAF50', 'is_ready': False},
                {'id': 2, 'user_id': 8, 'color_hex': '#E63946', 'is_ready': True},
            ],
            'taken_colors': ['#4CAF50', '#E63946'],
        }

        fake_match_query = SimpleNamespace(
            filter_by=lambda **kwargs: SimpleNamespace(first=lambda: fake_match)
        )
        fake_player_query = SimpleNamespace(
            filter_by=lambda **kwargs: SimpleNamespace(all=lambda: [current_player, other_player])
        )

        with patch.object(lobby_routes, '_require_auth', return_value=(fake_user, None, None)), patch.object(
            lobby_routes,
            'Match',
            SimpleNamespace(query=fake_match_query),
        ), patch.object(
            lobby_routes,
            'MatchPlayer',
            SimpleNamespace(query=fake_player_query),
        ), patch.object(lobby_routes, '_lobby_state', return_value=lobby_state), patch.object(
            lobby_routes.db.session,
            'commit',
        ) as commit, patch.object(socketio, 'emit') as emit:
            response = self.client.patch('/api/lobby/ABCD/color', json={'color_hex': '#4CAF50'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(current_player.color_hex, '#4CAF50')
        self.assertEqual(
            response.get_json(),
            {
                'message': 'Color updated.',
                'color_hex': '#4CAF50',
                'lobby': lobby_state,
            },
        )
        commit.assert_called_once_with()
        emit.assert_any_call(
            'color_taken',
            {'color_hex': '#4CAF50', 'player_id': 1},
            room='ABCD',
        )
        emit.assert_any_call('lobby_update', lobby_state, room='ABCD')

    def test_lobby_ready_endpoint_updates_player_and_returns_snapshot(self):
        fake_user = SimpleNamespace(id=7)
        fake_match = SimpleNamespace(id=91, status='lobby', room_code='ABCD')
        current_player = SimpleNamespace(id=1, user_id=7, is_ready=False)
        lobby_state = {
            'match': {'id': 91, 'room_code': 'ABCD'},
            'players': [
                {'id': 1, 'user_id': 7, 'color_hex': '#2196F3', 'is_ready': True},
            ],
            'taken_colors': ['#2196F3'],
        }

        fake_match_query = SimpleNamespace(
            filter_by=lambda **kwargs: SimpleNamespace(first=lambda: fake_match)
        )
        fake_player_query = SimpleNamespace(
            filter_by=lambda **kwargs: SimpleNamespace(first=lambda: current_player)
        )

        with patch.object(lobby_routes, '_require_auth', return_value=(fake_user, None, None)), patch.object(
            lobby_routes,
            'Match',
            SimpleNamespace(query=fake_match_query),
        ), patch.object(
            lobby_routes,
            'MatchPlayer',
            SimpleNamespace(query=fake_player_query),
        ), patch.object(lobby_routes, '_lobby_state', return_value=lobby_state), patch.object(
            lobby_routes.db.session,
            'commit',
        ) as commit, patch.object(socketio, 'emit') as emit:
            response = self.client.patch('/api/lobby/ABCD/ready', json={'ready': True})

        self.assertEqual(response.status_code, 200)
        self.assertTrue(current_player.is_ready)
        self.assertEqual(
            response.get_json(),
            {
                'message': 'Ready state updated.',
                'ready': True,
                'lobby': lobby_state,
            },
        )
        commit.assert_called_once_with()
        emit.assert_called_once_with('lobby_update', lobby_state, room='ABCD')

    def test_start_game_emits_state_in_game_start_payload(self):
        fake_user = SimpleNamespace(id=7)
        fake_match = SimpleNamespace(id=91, status='lobby', room_code='ABCD', host_user_id=7)
        fake_players = [
            SimpleNamespace(is_ready=True),
            SimpleNamespace(is_ready=True),
        ]
        game_state = {
            'match_id': 91,
            'turn_order': [1, 2],
            'current_player_id': 1,
            'status': 'active',
            'players': [],
            'properties': [],
        }

        fake_match_query = SimpleNamespace(
            filter_by=lambda **kwargs: SimpleNamespace(first=lambda: fake_match)
        )
        fake_player_query = SimpleNamespace(
            filter_by=lambda **kwargs: SimpleNamespace(all=lambda: fake_players)
        )

        with patch.object(lobby_routes, '_require_auth', return_value=(fake_user, None, None)), patch.object(
            lobby_routes,
            'Match',
            SimpleNamespace(query=fake_match_query),
        ), patch.object(
            lobby_routes,
            'MatchPlayer',
            SimpleNamespace(query=fake_player_query),
        ), patch.object(lobby_routes, 'initialize_game_state', return_value=game_state), patch.object(
                socketio,
            'emit',
        ) as emit, patch('app.engine.bots.queue_bot_state_evaluation') as queue_bot_state:
            response = self.client.post('/api/lobby/ABCD/start')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json(),
            {
                'message': 'Game started.',
                'match_id': 91,
                'state': game_state,
            },
        )
        emit.assert_any_call(
            'game_start',
            {
                'match_id': 91,
                'room_code': 'ABCD',
                'state': game_state,
                'turn_order': [1, 2],
                'first_player_id': 1,
            },
            room='ABCD',
        )
        emit.assert_any_call('game_state_snapshot', {'state': game_state}, room='91')
        queue_bot_state.assert_called_once_with(91, game_state, reason='game_start_rest')

    def test_admin_plot_debug_seed_uses_host_player_and_broadcasts_snapshot(self):
        fake_match = SimpleNamespace(id=55, status='active', host_user_id=7)
        fake_host_player = SimpleNamespace(id=3, user_id=7)
        debug_state = {
            'status': 'active',
            'current_round': 7,
            'players': [],
            'properties': [],
            'social': {'plot': {'exists': True}},
        }

        with self.client.session_transaction() as session:
            session['user_id'] = 7

        with patch('app.routes.admin.Match', SimpleNamespace(query=SimpleNamespace(get=lambda _match_id: fake_match))), patch(
            'app.routes.admin.MatchPlayer',
            SimpleNamespace(query=SimpleNamespace(filter_by=lambda **kwargs: SimpleNamespace(first=lambda: fake_host_player))),
        ), patch('app.routes.admin.load_game_state', return_value={'status': 'active'}) as load_game_state, patch(
            'app.routes.admin.seed_debug_communist_plot_state',
            return_value=(debug_state, {'summary': 'Debug communist plot seeded for Atlas.'}),
        ) as seed_debug, patch('app.routes.admin.persist_game_state') as persist_game_state, patch(
            'app.routes.admin.log_and_broadcast',
        ) as log_and_broadcast, patch('app.routes.admin.broadcast_game_state_snapshot') as broadcast_snapshot, patch.object(
            socketio,
            'emit',
        ) as emit:
            response = self.client.post('/api/admin/55/plot/debug-seed')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['message'], 'Debug communist plot seeded for Atlas.')
        load_game_state.assert_called_once()
        seed_debug.assert_called_once_with({'status': 'active'}, revolutionary_player_id=3)
        persist_game_state.assert_called_once_with(debug_state, 55, ANY)
        log_and_broadcast.assert_called_once()
        broadcast_snapshot.assert_called_once_with(socketio, 55, debug_state)
        emit.assert_called_once_with('plot_updated', {'match_id': 55, 'plot': {'exists': True}}, room='55')

    def test_admin_plot_debug_seed_returns_clean_validation_error(self):
        fake_match = SimpleNamespace(id=55, status='active', host_user_id=7)
        fake_host_player = SimpleNamespace(id=3, user_id=7)

        with self.client.session_transaction() as session:
            session['user_id'] = 7

        with patch('app.routes.admin.Match', SimpleNamespace(query=SimpleNamespace(get=lambda _match_id: fake_match))), patch(
            'app.routes.admin.MatchPlayer',
            SimpleNamespace(query=SimpleNamespace(filter_by=lambda **kwargs: SimpleNamespace(first=lambda: fake_host_player))),
        ), patch('app.routes.admin.load_game_state', return_value={'status': 'active'}), patch(
            'app.routes.admin.seed_debug_communist_plot_state',
            side_effect=ValueError('The debug communist plot scenario needs at least one rival player in the match.'),
        ), patch.object(socketio, 'emit') as emit:
            response = self.client.post('/api/admin/55/plot/debug-seed')

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.get_json(),
            {'error': 'The debug communist plot scenario needs at least one rival player in the match.'},
        )
        emit.assert_not_called()

    def test_admin_plot_debug_seed_is_blocked_when_host_debug_tools_disabled(self):
        fake_match = SimpleNamespace(id=55, status='active', host_user_id=7)

        with self.client.session_transaction() as session:
            session['user_id'] = 7

        self.app.config['ENABLE_HOST_DEBUG_TOOLS'] = False
        try:
            with patch('app.routes.admin.Match', SimpleNamespace(query=SimpleNamespace(get=lambda _match_id: fake_match))), patch(
                'app.routes.admin.load_game_state',
            ) as load_game_state, patch('app.routes.admin.seed_debug_communist_plot_state') as seed_debug:
                response = self.client.post('/api/admin/55/plot/debug-seed')
        finally:
            self.app.config['ENABLE_HOST_DEBUG_TOOLS'] = True

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json(), {'error': 'Host debug tools are disabled.'})
        load_game_state.assert_not_called()
        seed_debug.assert_not_called()


if __name__ == '__main__':
    unittest.main()