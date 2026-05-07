import os
import random
import sys
import unittest


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.engine.economy import ensure_regime_economy_state  # noqa: E402
from app.engine.liberal_democracy import (  # noqa: E402
    buy_corporate_property,
    deposit_bank_funds,
    get_liberal_democracy_go_salary,
    process_liberal_democracy_round,
    repay_bank_loan,
    request_bank_loan,
    setup_liberal_democracy_state,
    submit_market_order,
    withdraw_bank_funds,
)


def make_settings():
    return {
        'government_type': 'liberal_democracy',
        'go_salary': 200,
    }


def make_player(player_id, username, *, balance=0.0):
    return {
        'id': player_id,
        'username': username,
        'balance': balance,
        'is_bankrupt': False,
        'portfolio': {'stocks': {}, 'crypto': {}, 'recent_orders': []},
        'bank_savings_balance': 0.0,
        'bank_loan_principal': 0.0,
        'bank_loan_interest_rate': 0.0,
        'bank_missed_payments': 0,
        'bank_account_open': True,
        'employment_status': 'employed',
        'salary': 240.0,
        'salary_band': 240.0,
        'job_event_history': [],
        'unemployment_rounds_remaining': 0,
    }


def make_property(property_id, name, board_position, base_price, *, property_type='property', region='Africa', group_color='#8B4513'):
    return {
        'id': property_id,
        'name': name,
        'board_position': board_position,
        'base_price': base_price,
        'current_value': base_price,
        'owner_id': None,
        'dev_level': 0,
        'is_mortgaged': False,
        'property_type': property_type,
        'region': region,
        'group_color': group_color,
    }


def make_econ():
    return ensure_regime_economy_state(
        {
            'gov_type': 'liberal_democracy',
            'government_type': 'liberal_democracy',
            'interest_rate': 0.06,
            'inflation_rate': 0.03,
            'treasury_balance': 750.0,
            'welfare_payout': 18.0,
            'bailout_enabled': True,
        },
        make_settings(),
    )


class LiberalDemocracyEngineTests(unittest.TestCase):
    def test_setup_assigns_one_property_per_player_and_corporatizes_the_rest(self):
        players = [
            make_player(1, 'Atlas'),
            make_player(2, 'Nova'),
            make_player(3, 'Sable'),
            make_player(4, 'Ion'),
        ]
        properties = [
            make_property(1, 'Nairobi', 2, 60),
            make_property(2, 'Cairo', 4, 100),
            make_property(3, 'BOM', 6, 200, property_type='transit', region='Transit', group_color='#6B7280'),
            make_property(4, 'Karachi', 9, 120, region='South Asia', group_color='#EC4899'),
            make_property(5, 'Tokyo', 31, 300, region='Oceania', group_color='#06B6D4'),
            make_property(6, 'Sydney', 34, 320, region='Oceania', group_color='#06B6D4'),
            make_property(7, 'São Paulo', 37, 350, region='Americas', group_color='#16A34A'),
            make_property(8, 'JFK', 36, 200, property_type='transit', region='Transit', group_color='#6B7280'),
        ]

        next_players, next_properties, next_econ = setup_liberal_democracy_state(
            players,
            properties,
            make_econ(),
            make_settings(),
            rng=random.Random(7),
        )

        player_owned = [prop for prop in next_properties if prop.get('owner_id') is not None]
        corporate_owned = [prop for prop in next_properties if prop.get('corporate_owner_id')]

        self.assertEqual(len(player_owned), 4)
        self.assertEqual(len(corporate_owned), 4)
        self.assertEqual(len(next_econ['corporations']['active_ids']), 4)
        self.assertTrue(all(player.get('starting_property_id') for player in next_players))
        self.assertIn('BTC', next_econ['market']['assets'])
        self.assertIn('ETH', next_econ['market']['assets'])

    def test_bank_actions_update_cash_savings_and_principal(self):
        state = {
            'players': [make_player(1, 'Atlas', balance=1000.0)],
            'properties': [],
            'econ': make_econ(),
            'settings': make_settings(),
        }

        state, deposit_result = deposit_bank_funds(state, player_id=1, amount=200.0)
        state, loan_result = request_bank_loan(state, player_id=1, amount=150.0)
        state, repay_result = repay_bank_loan(state, player_id=1, amount=50.0)
        state, withdraw_result = withdraw_bank_funds(state, player_id=1, amount=75.0)

        player = state['players'][0]
        self.assertEqual(deposit_result['player']['bank_savings_balance'], 200.0)
        self.assertEqual(loan_result['player']['bank_loan_principal'], 150.0)
        self.assertEqual(repay_result['player']['bank_loan_principal'], 100.0)
        self.assertEqual(withdraw_result['player']['bank_savings_balance'], 125.0)
        self.assertEqual(player['balance'], 975.0)

    def test_market_orders_and_corporate_buyouts_update_portfolios_and_property_ownership(self):
        players = [make_player(1, 'Atlas', balance=5000.0), make_player(2, 'Nova', balance=1500.0)]
        properties = [
            make_property(1, 'Nairobi', 2, 60),
            make_property(2, 'Cairo', 4, 100),
            make_property(3, 'DXB', 15, 200, property_type='transit', region='Transit', group_color='#6B7280'),
            make_property(4, 'Tokyo', 31, 300, region='Oceania', group_color='#06B6D4'),
            make_property(5, 'Sydney', 34, 320, region='Oceania', group_color='#06B6D4'),
        ]
        next_players, next_properties, next_econ = setup_liberal_democracy_state(
            players,
            properties,
            make_econ(),
            make_settings(),
            rng=random.Random(11),
        )
        state = {
            'players': next_players,
            'properties': next_properties,
            'econ': next_econ,
            'settings': make_settings(),
        }

        state, market_result = submit_market_order(state, player_id=1, asset_key='BTC', side='buy', quantity=2.0)
        target_property = next(prop for prop in state['properties'] if prop.get('corporate_owner_id'))
        state['players'][0]['balance'] = 8000.0
        state, buyout_result = buy_corporate_property(state, player_id=1, property_id=target_property['id'])

        player = next(player for player in state['players'] if player['id'] == 1)
        purchased_property = next(prop for prop in state['properties'] if prop['id'] == target_property['id'])

        self.assertEqual(market_result['asset_key'], 'BTC')
        self.assertEqual(player['portfolio']['crypto']['BTC'], 2.0)
        self.assertEqual(buyout_result['property_id'], target_property['id'])
        self.assertEqual(purchased_property['owner_id'], 1)
        self.assertIsNone(purchased_property['corporate_owner_id'])

    def test_go_salary_is_halved_for_unemployed_players(self):
        state = {
            'players': [
                {**make_player(1, 'Atlas'), 'employment_status': 'unemployed'},
                {**make_player(2, 'Nova'), 'employment_status': 'employed'},
            ],
        }

        self.assertEqual(get_liberal_democracy_go_salary(state, 1, 200.0), 100.0)
        self.assertEqual(get_liberal_democracy_go_salary(state, 2, 200.0), 200.0)

    def test_market_history_and_decay_cycle_follow_macro_policy_pressure(self):
        players = [make_player(1, 'Atlas', balance=2500.0), make_player(2, 'Nova', balance=1500.0)]
        properties = [
            make_property(1, 'Nairobi', 2, 60),
            make_property(2, 'Cairo', 4, 100),
            make_property(3, 'Tokyo', 31, 300, region='Oceania', group_color='#06B6D4'),
            make_property(4, 'Sydney', 34, 320, region='Oceania', group_color='#06B6D4'),
            make_property(5, 'JFK', 36, 200, property_type='transit', region='Transit', group_color='#6B7280'),
        ]
        next_players, next_properties, next_econ = setup_liberal_democracy_state(
            players,
            properties,
            {**make_econ(), 'inflation_rate': 0.16, 'interest_rate': 0.13, 'welfare_payout': 55.0, 'treasury_balance': 20.0},
            make_settings(),
            rng=random.Random(13),
        )
        state = {
            'current_round': 5,
            'players': next_players,
            'properties': next_properties,
            'econ': {
                **next_econ,
                'inflation_rate': 0.16,
                'interest_rate': 0.13,
                'welfare_payout': 55.0,
                'treasury_balance': 20.0,
                'market_policy_bias': -0.025,
            },
            'settings': make_settings(),
        }

        next_state, logs = process_liberal_democracy_round(state)
        market = next_state['econ']['market']
        asset = next(iter(market['assets'].values()))

        self.assertEqual(market['cycle']['phase'], 'decay')
        self.assertLess(market['cycle']['policy_pressure'], 0)
        self.assertGreaterEqual(len(market['history']), 2)
        self.assertGreaterEqual(len(asset['history']), 2)
        self.assertTrue(any('decay phase' in entry for entry in market['last_round_summary']))
        self.assertTrue(logs)


if __name__ == '__main__':
    unittest.main()
