import os
import sys
from fnmatch import fnmatch


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import db  # noqa: E402
from app.engine import bots  # noqa: E402
from app.engine.game_loop import CHANCE_CARDS, COMMUNITY_CHEST_CARDS  # noqa: E402
from app.models.policy import resolve_lobbying_target  # noqa: E402
from app.utils.bot_registry import get_public_personality_options, validate_bot_configuration  # noqa: E402
from flask import Flask  # noqa: E402

import random
import unittest
from types import SimpleNamespace
from unittest.mock import patch


class FakeRedis:
    def __init__(self):
        self.store = {}

    def get(self, key):
        return self.store.get(key)

    def set(self, key, value, ex=None):
        self.store[key] = str(value)

    def delete(self, key):
        self.store.pop(key, None)

    def keys(self, pattern):
        return [key for key in self.store if fnmatch(key, pattern)]


class StaticQuery:
    def __init__(self, items=None, count_value=0):
        self.items = list(items or [])
        self.count_value = count_value

    def filter_by(self, **kwargs):
        return self

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def all(self):
        return list(self.items)

    def count(self):
        return self.count_value


def make_player(
    player_id,
    username,
    balance,
    *,
    is_bot=True,
    is_bankrupt=False,
    is_jailed=False,
    has_jail_card=False,
    jail_turns_remaining=0,
):
    return {
        'id': player_id,
        'username': username,
        'balance': balance,
        'current_position': 0,
        'team_id': None,
        'is_bot': is_bot,
        'is_bankrupt': is_bankrupt,
        'is_jailed': is_jailed,
        'has_jail_card': has_jail_card,
        'jail_turns_remaining': jail_turns_remaining,
    }


def make_property(
    property_id,
    name,
    group_color,
    base_price,
    owner_id=None,
    *,
    board_position=0,
    property_type='property',
    dev_level=0,
    is_mortgaged=False,
):
    return {
        'id': property_id,
        'name': name,
        'group_color': group_color,
        'base_price': base_price,
        'current_value': base_price,
        'owner_id': owner_id,
        'board_position': board_position,
        'property_type': property_type,
        'dev_level': dev_level,
        'is_mortgaged': is_mortgaged,
    }


def make_state(players, properties, *, government_type='liberal_democracy', welfare=25.0, tax=0.2, stability=0.7, round_number=4):
    return {
        'match_id': 77,
        'current_round': round_number,
        'settings': {
            'government_type': government_type,
            'game_mode': 'standard',
            'trading_enabled': True,
            'lobbying_enabled': True,
            'auction_enabled': True,
        },
        'econ': {
            'gov_type': government_type,
            'government_type': government_type,
            'welfare_payout': welfare,
            'tax_multiplier': tax,
            'stability': stability,
            'inflation_rate': 0.03,
            'treasury_balance': 1200,
        },
        'players': players,
        'properties': properties,
    }


class BotStrategyTests(unittest.TestCase):
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
        self.fake_redis = FakeRedis()
        self.redis_patcher = patch.object(bots, 'redis_client', self.fake_redis)
        self.redis_patcher.start()
        self.addCleanup(self.redis_patcher.stop)
        self.addCleanup(self.app_context.pop)

    def profile(self, settings=None, seat_index=0, difficulty='normal', persona=None):
        return bots.build_bot_profile(
            settings or {'government_type': 'liberal_democracy', 'game_mode': 'standard'},
            difficulty=difficulty,
            persona=persona,
            rng=random.Random(7),
            seat_index=seat_index,
        )

    def test_profile_contains_large_parameter_map(self):
        profile = self.profile({'government_type': 'social_democracy', 'game_mode': 'chaos'}, difficulty='hard', persona='policy_shaper')
        top_level_sections = {
            'core',
            'timing',
            'liquidity',
            'acquisition',
            'development',
            'auction',
            'trade',
            'lobbying',
            'jail',
            'bankruptcy',
        }
        self.assertTrue(top_level_sections.issubset(profile.keys()))
        flattened_count = sum(len(section) for key, section in profile.items() if isinstance(section, dict))
        self.assertGreaterEqual(flattened_count, 55)
        self.assertEqual(profile['government_type'], 'social_democracy')
        self.assertEqual(profile['economic_mode'], 'chaos')
        self.assertEqual(profile['difficulty'], 'hard')
        self.assertEqual(profile['persona'], 'policy_shaper')
        self.assertIn('skill', profile)
        self.assertIn('regime_bias', profile)
        self.assertIn('difficulty_capabilities', profile)

    def test_illegal_personality_pair_is_rejected(self):
        with self.assertRaises(ValueError):
            validate_bot_configuration('easy', 'expansionist')

    def test_personality_options_are_filtered_by_difficulty(self):
        easy_options = {entry['key'] for entry in get_public_personality_options(difficulty='easy')}
        hard_options = {entry['key'] for entry in get_public_personality_options(difficulty='hard')}

        self.assertIn('steady_collector', easy_options)
        self.assertNotIn('expansionist', easy_options)
        self.assertIn('expansionist', hard_options)
        self.assertNotIn('leverage_architect', hard_options)

    def test_regime_summary_respects_difficulty_capability_split(self):
        player = make_player(1, 'Atlas', 140)
        rival = make_player(2, 'Rival', 900, is_bot=False)
        state = make_state([player, rival], [], government_type='social_democracy', welfare=42.0, tax=0.22)
        state['econ']['bailout_enabled'] = True
        state['econ']['treasury_balance'] = 2400

        easy_summary = bots.build_regime_summary(player, state, self.profile(state['settings'], difficulty='easy', persona='steady_collector'))
        normal_summary = bots.build_regime_summary(player, state, self.profile(state['settings'], difficulty='normal', persona='welfare_optimizer'))
        hard_summary = bots.build_regime_summary(player, state, self.profile(state['settings'], difficulty='hard', persona='expansionist'))

        self.assertEqual(easy_summary['welfare_reliance_score'], 0.0)
        self.assertEqual(easy_summary['bailout_reliance_score'], 0.0)
        self.assertEqual(easy_summary['allowed_negative_exposure'], 0.0)
        self.assertGreater(normal_summary['welfare_reliance_score'], 0.0)
        self.assertEqual(normal_summary['bailout_reliance_score'], 0.0)
        self.assertEqual(normal_summary['allowed_negative_exposure'], 0.0)
        self.assertGreater(hard_summary['welfare_reliance_score'], 0.0)
        self.assertGreater(hard_summary['bailout_reliance_score'], 0.0)
        self.assertGreater(hard_summary['allowed_negative_exposure'], 0.0)

    def test_property_purchase_buys_monopoly_completion(self):
        player = make_player(1, 'Atlas', 1500)
        other = make_player(2, 'Rival', 1500, is_bot=False)
        properties = [
            make_property(1, 'Lagos', '#8B4513', 60, owner_id=1, board_position=1),
            make_property(2, 'Nairobi', '#8B4513', 60, owner_id=1, board_position=2),
            make_property(3, 'Cairo', '#8B4513', 100, owner_id=None, board_position=4),
        ]
        state = make_state([player, other], properties)
        decision = bots.choose_property_purchase(player, properties[2], state, self.profile())
        self.assertEqual(decision['decision'], 'buy')
        self.assertEqual(decision['reason'], 'monopoly_completion')

    def test_property_purchase_declines_when_it_breaks_reserve(self):
        player = make_player(1, 'Atlas', 210)
        other = make_player(2, 'Rival', 1500, is_bot=False)
        prop = make_property(3, 'Cairo', '#8B4513', 100, owner_id=None, board_position=4)
        state = make_state([player, other], [prop])
        decision = bots.choose_property_purchase(player, prop, state, self.profile())
        self.assertEqual(decision['decision'], 'decline')

    def test_auction_bid_respects_value_and_liquidity(self):
        player = make_player(1, 'Atlas', 900)
        other = make_player(2, 'Rival', 1500, is_bot=False)
        transit = make_property(6, 'Mumbai Airport', '#6B7280', 200, owner_id=None, board_position=6, property_type='transit')
        state = make_state([player, other], [transit])
        profile = self.profile()
        bid = bots.choose_auction_bid_amount(player, transit, 40, state, profile)
        self.assertIsNotNone(bid)
        self.assertGreater(bid, 40)
        too_high = bots.choose_auction_bid_amount(player, transit, 700, state, profile)
        self.assertIsNone(too_high)

    def test_liquidation_prefers_house_sale_then_mortgage_then_bankruptcy(self):
        player = make_player(1, 'Atlas', -120)
        other = make_player(2, 'Rival', 1000, is_bot=False)
        developed = make_property(7, 'Delhi', '#EC4899', 100, owner_id=1, board_position=7, dev_level=2)
        reserve = make_property(8, 'Karachi', '#EC4899', 120, owner_id=1, board_position=9)
        state = make_state([player, other], [developed, reserve])
        profile = self.profile()

        action = bots.choose_liquidation_action(player, state, profile)
        self.assertEqual(action['type'], 'sell_house')

        developed['dev_level'] = 0
        action = bots.choose_liquidation_action(player, state, profile)
        self.assertEqual(action['type'], 'mortgage')

        developed['is_mortgaged'] = True
        reserve['is_mortgaged'] = True
        action = bots.choose_liquidation_action(player, state, profile)
        self.assertEqual(action['type'], 'bankruptcy')

    def test_lobbying_targets_welfare_cut_at_fifty_percent_or_better(self):
        player = make_player(1, 'Atlas', 2600)
        opponent = make_player(2, 'Worker', 450, is_bot=False)
        state = make_state([player, opponent], [], welfare=70.0, tax=0.22, government_type='social_democracy')
        policy = SimpleNamespace(id=5, target_stat='welfare_decrease', policy_name='Welfare Cuts')

        with patch.object(bots, 'ensure_match_lobbying_policy', return_value=policy), patch.object(bots.LobbyContribution, 'query', new=StaticQuery(items=[])):
            move = bots.choose_lobbying_move(player, state, self.profile({'government_type': 'social_democracy', 'game_mode': 'standard'}))

        self.assertIsNotNone(move)
        self.assertEqual(move['target'], 'welfare_decrease')
        self.assertGreaterEqual(move['success_chance'], 0.5)
        self.assertGreater(move['contribution'], 0)

    def test_wealthy_bots_can_push_tax_hikes_when_treasury_is_thin(self):
        player = make_player(1, 'Atlas', 2600)
        opponent = make_player(2, 'Worker', 900, is_bot=False)
        state = make_state([player, opponent], [], welfare=10.0, tax=0.18, government_type='social_democracy')
        state['econ']['treasury_balance'] = 350
        state['econ']['bailout_enabled'] = True
        policy = SimpleNamespace(id=8, target_stat='tax_multiplier_increase', policy_name='Tax Hike')

        with patch.object(bots, 'ensure_match_lobbying_policy', return_value=policy), patch.object(bots.LobbyContribution, 'query', new=StaticQuery(items=[])):
            move = bots.choose_lobbying_move(player, state, self.profile({'government_type': 'social_democracy', 'game_mode': 'standard'}, difficulty='expert', persona='treasury_predator'))

        self.assertIsNotNone(move)
        self.assertEqual(move['target'], 'tax_multiplier_increase')
        self.assertEqual(move['axis'], 'tax_multiplier')
        self.assertEqual(move['direction'], 'increase')
        self.assertGreater(move['contribution'], 0)

    def test_social_democracy_leverage_pushes_bailout_enable_first(self):
        player = make_player(1, 'Atlas', 2500)
        rival = make_player(2, 'Rival', 800, is_bot=False)
        state = make_state([player, rival], [], welfare=18.0, tax=0.22, government_type='social_democracy')
        state['econ']['bailout_enabled'] = False
        state['econ']['treasury_balance'] = 1800
        policy = SimpleNamespace(id=9, target_stat='bailout_enable', policy_name='Enable Bailouts')

        with patch.object(bots, 'ensure_match_lobbying_policy', return_value=policy), patch.object(bots.LobbyContribution, 'query', new=StaticQuery(items=[])):
            move = bots.choose_lobbying_move(player, state, self.profile(state['settings'], difficulty='hard', persona='policy_shaper'))

        self.assertIsNotNone(move)
        self.assertEqual(move['target'], 'bailout_enable')
        self.assertEqual(move['axis'], 'bailouts')
        self.assertEqual(move['direction'], 'enable')
        self.assertEqual(move['reason'], 'unlock_safety_net')

    def test_development_target_builds_when_bot_has_monopoly_and_large_surplus(self):
        player = make_player(1, 'Atlas', 2600)
        rival = make_player(2, 'Rival', 700, is_bot=False)
        properties = [
            make_property(11, 'Bronze One', '#8B4513', 100, owner_id=1, board_position=11),
            make_property(12, 'Bronze Two', '#8B4513', 100, owner_id=1, board_position=12),
            make_property(13, 'Bronze Three', '#8B4513', 120, owner_id=1, board_position=13),
        ]
        state = make_state([player, rival], properties, tax=0.48, stability=0.12)

        target = bots.choose_development_target(player, state, self.profile())

        self.assertIsNotNone(target)
        self.assertIn(target['id'], {11, 12, 13})

    def test_trade_proposal_targets_monopoly_completion(self):
        player = make_player(1, 'Atlas', 1800)
        rival = make_player(2, 'Rival', 1200, is_bot=False)
        properties = [
            make_property(21, 'Berlin', '#EAB308', 220, owner_id=1, board_position=21),
            make_property(23, 'Paris', '#EAB308', 240, owner_id=1, board_position=23),
            make_property(24, 'London', '#EAB308', 260, owner_id=2, board_position=24),
        ]
        state = make_state([player, rival], properties)

        with patch.object(bots.Trade, 'query', new=StaticQuery(count_value=0)):
            proposal = bots.choose_trade_proposal(player, state, self.profile())

        self.assertIsNotNone(proposal)
        self.assertEqual(proposal['receiver_id'], 2)
        self.assertEqual(proposal['requested_props'], [24])
        self.assertGreater(proposal['offered_money'], 0)

    def test_trade_proposal_prefers_property_swap_when_both_players_finish_sets(self):
        player = make_player(1, 'Atlas', 420)
        rival = make_player(2, 'Rival', 420, is_bot=False)
        properties = [
            make_property(21, 'Berlin', '#EAB308', 220, owner_id=1, board_position=21),
            make_property(24, 'London', '#EAB308', 260, owner_id=2, board_position=24),
            make_property(31, 'Osaka', '#3B82F6', 200, owner_id=1, board_position=31),
            make_property(32, 'Tokyo', '#3B82F6', 210, owner_id=2, board_position=32),
        ]
        state = make_state([player, rival], properties)

        with patch.object(bots.Trade, 'query', new=StaticQuery(count_value=0)):
            proposal = bots.choose_trade_proposal(player, state, self.profile())

        self.assertIsNotNone(proposal)
        self.assertEqual(proposal['receiver_id'], 2)
        self.assertEqual(proposal['requested_props'], [24])
        self.assertEqual(proposal['offered_props'], [31])

    def test_trade_proposal_skips_lowball_cash_only_request(self):
        player = make_player(1, 'Atlas', 900)
        rival = make_player(2, 'Rival', 150, is_bot=False)
        properties = [
            make_property(21, 'Berlin', '#EAB308', 220, owner_id=1, board_position=21),
            make_property(23, 'Paris', '#EAB308', 240, owner_id=1, board_position=23),
            make_property(24, 'London', '#EAB308', 260, owner_id=2, board_position=24),
        ]
        state = make_state([player, rival], properties)
        profile = self.profile()
        profile['trade']['max_cash_offer_share'] = 0.08
        profile['liquidity']['max_lobby_share'] = 0.0

        with patch.object(bots.Trade, 'query', new=StaticQuery(count_value=0)):
            proposal = bots.choose_trade_proposal(player, state, profile)

        self.assertIsNone(proposal)

    def test_trade_proposal_pauses_while_auction_is_active(self):
        player = make_player(1, 'Atlas', 1800)
        rival = make_player(2, 'Rival', 1200, is_bot=False)
        properties = [
            make_property(21, 'Berlin', '#EAB308', 220, owner_id=1, board_position=21),
            make_property(23, 'Paris', '#EAB308', 240, owner_id=1, board_position=23),
            make_property(24, 'London', '#EAB308', 260, owner_id=2, board_position=24),
        ]
        state = make_state([player, rival], properties)
        self.fake_redis.set('game:77:auction:24:active', '1')

        with patch.object(bots.Trade, 'query', new=StaticQuery(count_value=0)):
            proposal = bots.choose_trade_proposal(player, state, self.profile())

        self.assertIsNone(proposal)

    def test_queue_bot_state_evaluation_waits_for_auction_to_finish(self):
        bot_player = make_player(1, 'Atlas', 1800)
        state = make_state([bot_player], [], round_number=5)
        state['status'] = 'active'
        state['awaiting_end_turn_player_id'] = 1
        state['current_player_id'] = 1
        state['dice_rolled_this_turn'] = True
        self.fake_redis.set('game:77:auction:12:active', '1')

        with patch.object(bots, '_schedule_player_task') as schedule_task, patch.object(bots, 'queue_bot_trade_responses') as queue_trade_responses, patch.object(bots, 'queue_bot_auction_reactions') as queue_auction_reactions:
            bots.queue_bot_state_evaluation(77, state, reason='test')

        schedule_task.assert_not_called()
        queue_trade_responses.assert_called_once_with(77, replace_existing=True)
        queue_auction_reactions.assert_called_once_with(77, game_state=state, reason='test', replace_existing=True)

    def test_recover_bot_state_evaluation_only_schedules_missing_tasks(self):
        bot_player = make_player(1, 'Atlas', 1800)
        state = make_state([bot_player], [], round_number=5)
        state['status'] = 'active'
        state['awaiting_end_turn_player_id'] = 1
        state['current_player_id'] = 1
        state['dice_rolled_this_turn'] = True

        with patch.object(bots, '_schedule_player_task') as schedule_task, patch.object(bots, 'queue_bot_trade_responses') as queue_trade_responses, patch.object(bots, 'queue_bot_auction_reactions') as queue_auction_reactions:
            bots.recover_bot_state_evaluation(77, state, reason='refresh')

        schedule_task.assert_called_once_with(77, 1, 'manage_turn', 'refresh', replace_existing=False)
        queue_trade_responses.assert_called_once_with(77, replace_existing=False)
        queue_auction_reactions.assert_called_once_with(77, game_state=state, reason='refresh', replace_existing=False)

    def test_execute_manage_turn_ends_turn_after_repeated_failed_action(self):
        bot_player = make_player(1, 'Atlas', 1800)
        rival = make_player(2, 'Rival', 1200, is_bot=False)
        state = make_state([bot_player, rival], [], round_number=5)
        state['status'] = 'active'
        state['awaiting_end_turn_player_id'] = 1
        state['current_player_id'] = 1
        state['dice_rolled_this_turn'] = True

        match_player = SimpleNamespace(id=1, is_bot=True, is_bankrupt=False)
        action = {'type': 'trade', 'receiver_id': 2, 'offered_money': 100}

        with patch.object(bots.MatchPlayer, 'query', new=SimpleNamespace(get=lambda _pid: match_player)), patch.object(bots, 'load_game_state', return_value=state), patch.object(bots, 'ensure_bot_profile', return_value=self.profile(state['settings'])), patch.object(bots, 'choose_management_action', side_effect=[action, action]), patch.object(bots, '_execute_management_action', return_value=False) as execute_action, patch.object(bots, 'has_active_auction', return_value=False), patch.object(bots, 'has_pending_player_debt', return_value=False), patch.object(bots, '_bot_declare_bankruptcy') as declare_bankruptcy, patch.object(bots, 'end_turn', return_value={'ended': True}) as end_turn, patch.object(bots, 'persist_game_state') as persist_state, patch.object(bots, 'broadcast_game_state_snapshot') as broadcast_snapshot:
            bots._execute_manage_turn(77, 1)

        execute_action.assert_called_once_with(77, 1, action, state)
        declare_bankruptcy.assert_not_called()
        end_turn.assert_called_once()
        persist_state.assert_called_once_with({'ended': True}, 77, self.fake_redis)
        broadcast_snapshot.assert_called_once_with(bots.socketio, 77, {'ended': True})

    def test_execute_property_decision_falls_back_to_decline_after_failed_buy(self):
        bot_player = make_player(1, 'Atlas', 500)
        rival = make_player(2, 'Rival', 1200, is_bot=False)
        prop = make_property(31, 'Lima', '#84CC16', 200, owner_id=None, board_position=31)
        state = make_state([bot_player, rival], [prop], round_number=5)
        state['status'] = 'active'
        state['pending_action'] = {
            'type': 'buy_property',
            'player_id': 1,
            'property_id': 31,
        }
        state['pending_turn_context'] = {
            'dice_result': {'is_doubles': False},
        }

        match_player = SimpleNamespace(id=1, is_bot=True, is_bankrupt=False)

        with patch.object(bots.MatchPlayer, 'query', new=SimpleNamespace(get=lambda _pid: match_player)), patch.object(bots, 'load_game_state', return_value=state), patch.object(bots, 'ensure_bot_profile', return_value=self.profile(state['settings'])), patch.object(bots, 'choose_property_purchase', return_value={'decision': 'buy'}), patch.object(bots, '_bot_buy_property', return_value=False) as buy_property, patch.object(bots, '_bot_decline_property', return_value=True) as decline_property:
            bots._execute_property_decision(77, 1)

        buy_property.assert_called_once_with(77, 1, prop, {'is_doubles': False})
        decline_property.assert_called_once_with(77, 1, prop, {'is_doubles': False})

    def test_trade_response_accepts_profitable_offer(self):
        player = make_player(1, 'Atlas', 1200)
        rival = make_player(2, 'Rival', 1200, is_bot=False)
        properties = [
            make_property(21, 'Berlin', '#EAB308', 220, owner_id=1, board_position=21),
            make_property(23, 'Paris', '#EAB308', 240, owner_id=1, board_position=23),
            make_property(24, 'London', '#EAB308', 260, owner_id=2, board_position=24),
        ]
        state = make_state([player, rival], properties)
        trade = SimpleNamespace(
            offered_money=50,
            requested_money=0,
            offered_props=[24],
            requested_props=[],
        )
        decision = bots.evaluate_trade_response(trade, player, state, self.profile())
        self.assertEqual(decision, 'accept')

    def test_trade_response_values_favorable_lobby_pledges(self):
        player = make_player(1, 'Atlas', 220, is_bot=False)
        rival = make_player(2, 'Rival', 1400)
        state = make_state([player, rival], [], welfare=12.0, tax=0.22, government_type='social_democracy')
        trade = SimpleNamespace(
            offered_money=0,
            requested_money=0,
            offered_props=[],
            requested_props=[],
            offered_lobby_pledges=[{'target': 'welfare_increase', 'amount': 250}],
            requested_lobby_pledges=[],
        )

        decision = bots.evaluate_trade_response(trade, player, state, self.profile())

        self.assertEqual(decision, 'accept')

    def test_doctrine_aware_pledges_are_more_valuable_for_hard_and_expert(self):
        player = make_player(1, 'Atlas', 1200)
        rival = make_player(2, 'Rival', 1200, is_bot=False)
        state = make_state([player, rival], [], welfare=20.0, tax=0.22, government_type='social_democracy')
        state['econ']['bailout_enabled'] = False
        pledge = [{'axis': 'bailouts', 'direction': 'enable', 'amount': 250}]

        easy_value = bots._score_lobby_pledges_for_player(player, pledge, state, self.profile(state['settings'], difficulty='easy', persona='steady_collector'))
        hard_value = bots._score_lobby_pledges_for_player(player, pledge, state, self.profile(state['settings'], difficulty='hard', persona='policy_shaper'))
        expert_value = bots._score_lobby_pledges_for_player(player, pledge, state, self.profile(state['settings'], difficulty='expert', persona='leverage_architect'))

        self.assertLess(easy_value, hard_value)
        self.assertLess(hard_value, expert_value)

    def test_trade_response_rejects_monopoly_breaking_offer(self):
        player = make_player(1, 'Atlas', 1200)
        rival = make_player(2, 'Rival', 1200, is_bot=False)
        properties = [
            make_property(21, 'Berlin', '#EAB308', 220, owner_id=1, board_position=21),
            make_property(23, 'Paris', '#EAB308', 240, owner_id=1, board_position=23),
            make_property(24, 'London', '#EAB308', 260, owner_id=1, board_position=24),
        ]
        state = make_state([player, rival], properties)
        trade = SimpleNamespace(
            offered_money=200,
            requested_money=0,
            offered_props=[],
            requested_props=[24],
        )
        decision = bots.evaluate_trade_response(trade, player, state, self.profile())
        self.assertEqual(decision, 'reject')

    def test_jail_resolution_prefers_card_then_bail_then_roll(self):
        player = make_player(1, 'Atlas', 600, is_jailed=True, has_jail_card=True, jail_turns_remaining=2)
        state = make_state([player], [])
        profile = self.profile()
        self.assertEqual(bots.choose_jail_resolution(player, state, profile), 'card')

        player['has_jail_card'] = False
        player['jail_turns_remaining'] = 1
        self.assertEqual(bots.choose_jail_resolution(player, state, profile), 'pay')

        player['balance'] = 40
        self.assertEqual(bots.choose_jail_resolution(player, state, profile), 'roll')

    def test_mode_specific_doctrine_differs_between_standard_and_speed(self):
        player = make_player(1, 'Atlas', 2200)
        rival = make_player(2, 'Rival', 1400, is_bot=False)
        state_standard = make_state([player, rival], [], government_type='social_democracy')
        state_standard['econ']['bailout_enabled'] = False
        state_speed = make_state([player, rival], [], government_type='social_democracy')
        state_speed['settings']['game_mode'] = 'speed'
        state_speed['econ']['bailout_enabled'] = False

        standard_profile = self.profile(state_standard['settings'], difficulty='expert', persona='treasury_predator')
        speed_profile = self.profile(state_speed['settings'], difficulty='expert', persona='treasury_predator')

        standard_doctrine = bots.choose_bot_doctrine(player, state_standard, standard_profile)
        speed_doctrine = bots.choose_bot_doctrine(player, state_speed, speed_profile)

        self.assertEqual(standard_doctrine, 'policy_shaping')
        self.assertEqual(speed_doctrine, 'treasury_rebuild_then_leverage')

    def test_axis_direction_mapping_resolves_underlying_policies(self):
        self.assertEqual(resolve_lobbying_target(axis='tax_multiplier', direction='increase'), 'tax_multiplier_increase')
        self.assertEqual(resolve_lobbying_target(axis='welfare_rate', direction='decrease'), 'welfare_decrease')
        self.assertEqual(resolve_lobbying_target(axis='bailouts', direction='enable'), 'bailout_enable')
        self.assertEqual(resolve_lobbying_target(axis='housing_regulation', direction='loosen'), 'deregulate_housing')

    def test_recoverable_distress_prefers_bailout_over_engine_mortgage(self):
        player = make_player(1, 'Atlas', -120)
        rival = make_player(2, 'Rival', 900, is_bot=False)
        properties = [
            make_property(31, 'Tokyo', '#06B6D4', 300, owner_id=1, board_position=31),
            make_property(32, 'Seoul', '#06B6D4', 320, owner_id=1, board_position=32),
            make_property(34, 'Sydney', '#06B6D4', 320, owner_id=1, board_position=34),
        ]
        state = make_state([player, rival], properties, welfare=35.0, tax=0.24, government_type='social_democracy')
        state['econ']['bailout_enabled'] = True
        state['econ']['treasury_balance'] = 2600

        action = bots.choose_liquidation_action(
            player,
            state,
            self.profile(state['settings'], difficulty='expert', persona='leverage_architect'),
        )

        self.assertIsNotNone(action)
        self.assertEqual(action['type'], 'bankruptcy')

    def test_removed_jail_cards_are_absent_from_both_decks(self):
        removed_effects = {'get_out_of_jail_free', 'go_to_jail'}
        self.assertTrue(all(card['effect_type'] not in removed_effects for card in CHANCE_CARDS))
        self.assertTrue(all(card['effect_type'] not in removed_effects for card in COMMUNITY_CHEST_CARDS))


if __name__ == '__main__':
    unittest.main()