import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from flask import Flask


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.routes.admin import admin_bp  # noqa: E402
from app.routes.auth import auth_bp  # noqa: E402
from app.routes.game import game_bp  # noqa: E402
from app.routes.lobby import lobby_bp  # noqa: E402
from app.routes import game as game_routes  # noqa: E402


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


if __name__ == '__main__':
    unittest.main()