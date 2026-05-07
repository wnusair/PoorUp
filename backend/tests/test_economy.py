import os
import sys
import unittest
from unittest.mock import patch


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.engine.economy import (  # noqa: E402
    apply_capital_yield,
    apply_fiscal_inflation,
    apply_income_tax,
    apply_luxury_tax,
    apply_per_turn_tax,
    apply_property_tax,
    apply_super_tax,
    apply_treasury_lobbying_inflation,
    calculate_development_cost,
    drift_economy,
    ensure_regime_economy_state,
    get_effective_tax_rate,
    get_rent_multiplier,
    pay_welfare,
    property_is_fully_developed,
)
from app.engine.liberal_democracy import apply_tax_bracket_policy  # noqa: E402


class EconomyEngineTests(unittest.TestCase):
    def test_cash_taxes_are_percentage_based_and_never_push_cash_negative(self):
        player = {'balance': 25.0}
        econ = {'tax_multiplier': 4.0}

        income_tax, income_balance = apply_income_tax(player, econ, {})
        turn_tax, turn_balance = apply_per_turn_tax(player, econ)
        luxury_tax, luxury_balance, _ = apply_luxury_tax(player, econ)
        super_tax, super_balance, _ = apply_super_tax(player, econ)

        self.assertLessEqual(income_tax, player['balance'])
        self.assertLessEqual(turn_tax, player['balance'])
        self.assertLessEqual(luxury_tax, player['balance'])
        self.assertLessEqual(super_tax, player['balance'])
        self.assertGreaterEqual(income_balance, 0)
        self.assertGreaterEqual(turn_balance, 0)
        self.assertGreaterEqual(luxury_balance, 0)
        self.assertGreaterEqual(super_balance, 0)

    def test_cash_taxes_follow_live_percentage_rates(self):
        player = {'balance': 1500.0}
        econ = {'tax_multiplier': 0.15}

        self.assertAlmostEqual(get_effective_tax_rate(econ), 0.13043478, places=6)

        income_tax, _ = apply_income_tax(player, econ, {})
        luxury_tax, _, _ = apply_luxury_tax(player, econ)
        super_tax, _, _ = apply_super_tax(player, econ)

        self.assertAlmostEqual(income_tax, 195.65, places=2)
        self.assertAlmostEqual(luxury_tax, 97.83, places=2)
        self.assertAlmostEqual(super_tax, 195.65, places=2)

    def test_property_tax_can_still_push_players_into_debt(self):
        player = {'balance': 5.0}
        props = [{'current_value': 1000.0, 'is_mortgaged': False}]
        econ = {'tax_multiplier': 1.0}

        total_tax, new_balance = apply_property_tax(player, props, econ)

        self.assertEqual(total_tax, 10.0)
        self.assertEqual(new_balance, -5.0)

    def test_minarchism_development_cost_scales_after_four_houses(self):
        state = {
            'econ': {'gov_type': 'minarchism'},
            'settings': {'government_type': 'minarchism'},
        }

        self.assertEqual(calculate_development_cost(200, 4, state), 100.0)
        self.assertEqual(calculate_development_cost(200, 5, state), 135.0)
        self.assertEqual(calculate_development_cost(200, 6, state), 205.0)

    def test_inflation_increases_development_costs(self):
        state = {
            'econ': {'gov_type': 'social_democracy', 'inflation_rate': 0.20},
            'settings': {'government_type': 'social_democracy'},
        }

        self.assertEqual(calculate_development_cost(200, 1, state), 120.0)
        self.assertEqual(calculate_development_cost(200, 2, state), 120.0)

    def test_minarchism_rent_multiplier_keeps_scaling_without_hotel_cap(self):
        state = {
            'econ': {'gov_type': 'minarchism'},
            'settings': {'government_type': 'minarchism'},
        }

        self.assertEqual(get_rent_multiplier(4, state), 30.0)
        self.assertEqual(get_rent_multiplier(5, state), 38.0)
        self.assertEqual(get_rent_multiplier(6, state), 46.0)

    def test_only_non_minarchism_properties_have_a_hard_development_cap(self):
        liberal_state = {
            'econ': {'gov_type': 'liberal_democracy'},
            'settings': {'government_type': 'liberal_democracy'},
        }
        minarchism_state = {
            'econ': {'gov_type': 'minarchism'},
            'settings': {'government_type': 'minarchism'},
        }

        self.assertTrue(property_is_fully_developed({'dev_level': 5}, liberal_state))
        self.assertFalse(property_is_fully_developed({'dev_level': 9}, minarchism_state))

    def test_direct_stimulus_adds_more_inflation_than_treasury_injection(self):
        econ = {'government_type': 'social_democracy', 'gov_type': 'social_democracy', 'inflation_rate': 0.03}
        settings = {'government_type': 'social_democracy', 'go_salary': 200}

        _, welfare_delta = apply_fiscal_inflation(
            econ,
            600,
            settings,
            active_player_count=4,
            category='welfare_distribution',
        )
        _, stimulus_delta = apply_fiscal_inflation(
            econ,
            600,
            settings,
            active_player_count=4,
            category='economic_stimulus',
        )
        _, treasury_delta = apply_fiscal_inflation(
            econ,
            600,
            settings,
            active_player_count=4,
            category='treasury_injection',
        )

        self.assertGreater(welfare_delta, 0)
        self.assertGreater(stimulus_delta, welfare_delta)
        self.assertGreater(welfare_delta, treasury_delta)

    def test_treasury_lobbying_has_stronger_inflation_floor(self):
        econ = {'government_type': 'social_democracy', 'gov_type': 'social_democracy', 'inflation_rate': 0.03}
        settings = {'government_type': 'social_democracy', 'go_salary': 200}

        updated_econ, inflation_delta = apply_treasury_lobbying_inflation(
            econ,
            400,
            settings,
            active_player_count=4,
        )

        self.assertGreaterEqual(inflation_delta, 0.008)
        self.assertLessEqual(inflation_delta, 0.05)
        self.assertGreater(updated_econ['inflation_rate'], econ['inflation_rate'])

    def test_successful_welfare_round_raises_inflation(self):
        players = [
            {'id': 1, 'balance': 0.0, 'is_bankrupt': False},
            {'id': 2, 'balance': 80.0, 'is_bankrupt': False},
            {'id': 3, 'balance': 900.0, 'is_bankrupt': False},
        ]
        econ = {
            'government_type': 'social_democracy',
            'gov_type': 'social_democracy',
            'welfare_payout': 60.0,
            'treasury_balance': 1500.0,
            'inflation_rate': 0.03,
        }
        settings = {
            'government_type': 'social_democracy',
            'welfare_system_enabled': True,
            'go_salary': 200,
        }

        updated_players, updated_econ, distribution = pay_welfare(players, econ, settings)

        self.assertTrue(distribution['successful'])
        self.assertGreater(distribution['inflation_delta'], 0)
        self.assertGreater(updated_econ['inflation_rate'], econ['inflation_rate'])
        self.assertGreater(updated_players[0]['balance'], players[0]['balance'])

    def test_liberal_democracy_state_derives_market_metrics(self):
        econ = ensure_regime_economy_state(
            {
                'gov_type': 'liberal_democracy',
                'government_type': 'liberal_democracy',
                'interest_rate': 0.065,
                'inflation_rate': 0.02,
                'market_confidence': 78.0,
            },
            {'government_type': 'liberal_democracy', 'go_salary': 200},
        )

        self.assertEqual(econ['gov_type'], 'liberal_democracy')
        self.assertGreater(econ['market_confidence'], 0)
        self.assertEqual(econ['capital_yield_rate'], 0.0)
        self.assertGreaterEqual(econ['private_equity_bonus_multiplier'], 1.0)
        self.assertEqual(econ['capital_yield_reserve_floor'], 0.0)
        self.assertIn('market', econ)
        self.assertIn('corporations', econ)
        self.assertIn('bank', econ)
        self.assertIn('jobs', econ)
        self.assertIn('tax_brackets', econ)

    def test_liberal_democracy_capital_yield_rewards_liquidity_with_cap(self):
        players = [
            {'id': 1, 'balance': 1600.0, 'is_bankrupt': False},
            {'id': 2, 'balance': 140.0, 'is_bankrupt': False},
        ]
        econ = ensure_regime_economy_state(
            {
                'gov_type': 'liberal_democracy',
                'government_type': 'liberal_democracy',
                'market_confidence': 82.0,
                'interest_rate': 0.08,
                'inflation_rate': 0.02,
            },
            {'government_type': 'liberal_democracy', 'go_salary': 200},
        )

        updated_players, updated_econ, distribution = apply_capital_yield(
            players,
            econ,
            {'government_type': 'liberal_democracy', 'go_salary': 200},
        )

        self.assertFalse(distribution['successful'])
        self.assertEqual(distribution['eligible_count'], 0)
        self.assertEqual(distribution['total_payout'], 0.0)
        self.assertEqual(distribution['reason'], 'The old cash bonus has been retired in this Liberal Democracy mode.')
        self.assertEqual(updated_players[0]['balance'], players[0]['balance'])
        self.assertEqual(updated_players[1]['balance'], players[1]['balance'])
        self.assertEqual(updated_econ['capital_yield_last_round'], distribution['total_payout'])

    def test_liberal_democracy_tax_bracket_policy_updates_boundaries_and_rates(self):
        econ = ensure_regime_economy_state(
            {
                'gov_type': 'liberal_democracy',
                'government_type': 'liberal_democracy',
            },
            {'government_type': 'liberal_democracy', 'go_salary': 200},
        )

        boundary_shifted = apply_tax_bracket_policy(econ, mode='boundary_up')
        rate_shifted = apply_tax_bracket_policy(boundary_shifted, mode='rate_up')

        self.assertEqual(boundary_shifted['tax_brackets']['brackets'][0]['max_net_worth'], 2499)
        self.assertEqual(boundary_shifted['tax_brackets']['brackets'][1]['min_net_worth'], 2500)
        self.assertAlmostEqual(rate_shifted['tax_brackets']['brackets'][0]['rate'], 0.02, places=4)

    def test_liberal_democracy_drift_pulls_high_welfare_back_toward_market_center(self):
        players = [
            {'id': 1, 'balance': 2000.0, 'is_bankrupt': False},
            {'id': 2, 'balance': 120.0, 'is_bankrupt': False},
            {'id': 3, 'balance': 60.0, 'is_bankrupt': False},
        ]
        econ = ensure_regime_economy_state(
            {
                'gov_type': 'liberal_democracy',
                'government_type': 'liberal_democracy',
                'market_confidence': 70.0,
                'interest_rate': 0.06,
                'inflation_rate': 0.03,
                'welfare_payout': 45.0,
                'tax_multiplier': 0.30,
                'stability': 0.70,
                'treasury_balance': 300.0,
            },
            {'government_type': 'liberal_democracy', 'go_salary': 200},
        )

        with patch('app.engine.economy.random.uniform', return_value=0.0):
            updated_econ = drift_economy(
                econ,
                players,
                4,
                {'government_type': 'liberal_democracy', 'go_salary': 200},
            )

        self.assertLess(updated_econ['welfare_payout'], 45.0)
        self.assertLess(updated_econ['market_confidence'], 70.0)


if __name__ == '__main__':
    unittest.main()
