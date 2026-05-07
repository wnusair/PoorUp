import os
import sys
import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

from flask import Flask

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import db  # noqa: E402
from app.engine import deals  # noqa: E402
from app.models.deal import Deal, DealClause, DealInvestmentTranche  # noqa: E402
from app.models.player import Match, MatchPlayer, User  # noqa: E402
from app.models.property import Property  # noqa: E402


def make_state():
    return {
        'players': [
            {'id': 1, 'username': 'Atlas', 'balance': 500.0},
            {'id': 2, 'username': 'Rival', 'balance': 500.0},
        ],
        'deals': [],
        'settings': {'deals_enabled': True},
    }


class DealEngineTests(unittest.TestCase):
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
        self.tables = [
            User.__table__,
            Match.__table__,
            MatchPlayer.__table__,
            Property.__table__,
            Deal.__table__,
            DealClause.__table__,
            DealInvestmentTranche.__table__,
        ]
        db.metadata.create_all(bind=db.engine, tables=self.tables)
        self.addCleanup(self.app_context.pop)
        self.addCleanup(lambda: db.metadata.drop_all(bind=db.engine, tables=list(reversed(self.tables))))
        self.addCleanup(db.session.remove)

    def test_calculate_effective_build_loan_payout_uses_written_cap_without_ld_bonus(self):
        game_state = {
            'players': [
                {'id': 1, 'username': 'Atlas', 'balance': 500.0, 'is_bankrupt': False},
                {'id': 2, 'username': 'Rival', 'balance': 500.0, 'is_bankrupt': False},
            ],
        }
        economy = {
            'gov_type': 'liberal_democracy',
            'private_equity_bonus_multiplier': 1.15,
        }

        payout = deals.calculate_effective_build_loan_payout(200, game_state, economy)

        self.assertEqual(payout, 200.0)

    def test_request_deal_termination_records_first_request(self):
        deal = SimpleNamespace(
            id=44,
            match_id=77,
            proposer_id=1,
            counterparty_id=2,
            status=deals.DEAL_STATUS_ACCEPTED,
            clauses=[],
            termination_requested_by_id=None,
            termination_requested_at=None,
            last_updated_at=None,
        )

        with patch.object(deals, '_safe_commit', return_value=True) as safe_commit, patch.object(
            deals,
            'attach_deals_snapshot',
            side_effect=lambda game_state, *_args: {**game_state, 'deals': [{'id': 44}]},
        ) as attach_deals_snapshot:
            next_state, termination_status, error = deals.request_deal_termination(deal, 1, make_state())

        self.assertIsNone(error)
        self.assertEqual(termination_status, 'requested')
        self.assertEqual(deal.termination_requested_by_id, 1)
        self.assertIsInstance(deal.termination_requested_at, datetime)
        self.assertEqual(next_state['deals'], [{'id': 44}])
        safe_commit.assert_called_once()
        attach_deals_snapshot.assert_called_once()

    def test_request_deal_termination_requires_second_party_confirmation(self):
        deal = SimpleNamespace(
            id=44,
            match_id=77,
            proposer_id=1,
            counterparty_id=2,
            status=deals.DEAL_STATUS_ACCEPTED,
            clauses=[],
            termination_requested_by_id=1,
            termination_requested_at=datetime.utcnow(),
            last_updated_at=None,
        )

        terminated_state = {'players': make_state()['players'], 'deals': []}
        with patch.object(deals, 'terminate_deal', return_value=terminated_state) as terminate_deal, patch.object(
            deals,
            'attach_deals_snapshot',
            side_effect=lambda game_state, *_args: game_state,
        ) as attach_deals_snapshot:
            next_state, termination_status, error = deals.request_deal_termination(deal, 2, make_state())

        self.assertIsNone(error)
        self.assertEqual(termination_status, 'terminated')
        self.assertIs(next_state, terminated_state)
        terminate_deal.assert_called_once_with(deal, unittest.mock.ANY, status=deals.DEAL_STATUS_CANCELLED)
        attach_deals_snapshot.assert_called_once_with(terminated_state, 77)

    def test_serialize_deal_includes_termination_request_fields(self):
        deal = SimpleNamespace(
            id=44,
            match_id=77,
            proposer_id=1,
            counterparty_id=2,
            status=deals.DEAL_STATUS_ACCEPTED,
            title='Revenue Shield',
            created_at=None,
            responded_at=None,
            accepted_at=None,
            cancelled_at=None,
            last_updated_at=None,
            proposal_version=1,
            counter_of_deal_id=None,
            termination_requested_by_id=2,
            termination_requested_at=datetime(2026, 4, 6, 12, 0, 0),
            clauses=[],
        )

        payload = deals.serialize_deal(
            deal,
            player_lookup={1: {'username': 'Atlas'}, 2: {'username': 'Rival'}},
        )

        self.assertEqual(payload['termination_requested_by_id'], 2)
        self.assertEqual(payload['termination_requested_by_name'], 'Rival')
        self.assertEqual(payload['termination_requested_at'], '2026-04-06T12:00:00')

    def test_apply_investment_profit_share_uses_owner_funded_repayment_when_rent_is_waived(self):
        user_one = User(username='Atlas', password_hash='hash')
        user_two = User(username='Rival', password_hash='hash')
        db.session.add_all([user_one, user_two])
        db.session.flush()

        match = Match(room_code='ROOM77', host_user_id=user_one.id, government_type='liberal_democracy')
        db.session.add(match)
        db.session.flush()

        investor = MatchPlayer(match_id=match.id, user_id=user_one.id, balance=100.0, is_ready=True)
        recipient = MatchPlayer(match_id=match.id, user_id=user_two.id, balance=250.0, is_ready=True)
        db.session.add_all([investor, recipient])
        db.session.flush()

        prop = Property(
            match_id=match.id,
            name='Cairo Heights',
            region='Africa',
            group_color='#8B4513',
            board_position=4,
            base_price=180.0,
            current_value=180.0,
            dev_level=2,
            owner_id=recipient.id,
            property_type='property',
        )
        db.session.add(prop)
        db.session.flush()

        deal = Deal(
            match_id=match.id,
            proposer_id=investor.id,
            counterparty_id=recipient.id,
            status=deals.DEAL_STATUS_ACCEPTED,
            title='Fund Cairo',
            accepted_at=datetime.utcnow(),
            responded_at=datetime.utcnow(),
            last_updated_at=datetime.utcnow(),
        )
        db.session.add(deal)
        db.session.flush()

        clause = DealClause(
            deal_id=deal.id,
            clause_type=deals.CLAUSE_INVESTMENT,
            grantor_id=investor.id,
            beneficiary_id=recipient.id,
            scope_json={'mode': 'selected_property_ids', 'property_ids': [prop.id]},
            config_json={'escrow_amount': 200.0, 'profit_share_percent': 0.5, 'max_payout': 300.0},
            deadline_json={'metric': deals.DEADLINE_BENEFICIARY_TURNS, 'initial': 3},
            state_json={'remaining': 3, 'escrow_remaining': 0.0, 'payout_to_date': 0.0},
            status=deals.CLAUSE_STATUS_ACTIVE,
            activated_at=datetime.utcnow(),
        )
        db.session.add(clause)
        db.session.flush()

        tranche = DealInvestmentTranche(
            deal_clause_id=clause.id,
            property_id=prop.id,
            investor_id=investor.id,
            recipient_id=recipient.id,
            funded_cost=200.0,
            baseline_dev_level=1,
            funded_dev_level=2,
            baseline_rent=100.0,
            funded_rent=220.0,
            profit_share_percent=0.5,
            max_payout=300.0,
            payout_to_date=0.0,
            active=True,
            created_at=datetime.utcnow(),
        )
        db.session.add(tranche)
        db.session.commit()

        game_state = {
            'match_id': match.id,
            'players': [
                {'id': investor.id, 'username': 'Atlas', 'balance': 100.0, 'is_bankrupt': False},
                {'id': recipient.id, 'username': 'Rival', 'balance': 250.0, 'is_bankrupt': False},
            ],
            'properties': [
                {
                    'id': prop.id,
                    'name': prop.name,
                    'region': prop.region,
                    'group_color': prop.group_color,
                    'board_position': prop.board_position,
                    'base_price': float(prop.base_price),
                    'current_value': float(prop.current_value),
                    'dev_level': prop.dev_level,
                    'owner_id': prop.owner_id,
                    'property_type': prop.property_type,
                    'is_mortgaged': False,
                },
            ],
            'pending_debts': [],
        }

        next_state, logs = deals.apply_investment_profit_share(
            game_state,
            match.id,
            property_id=prop.id,
            owner_id=recipient.id,
            actual_rent_paid=0.0,
            triggered_rent_amount=220.0,
            owner_funded=True,
        )

        updated_investor = next(player for player in next_state['players'] if player['id'] == investor.id)
        updated_recipient = next(player for player in next_state['players'] if player['id'] == recipient.id)

        self.assertEqual(updated_investor['balance'], 160.0)
        self.assertEqual(updated_recipient['balance'], 190.0)
        self.assertEqual(float(DealInvestmentTranche.query.get(tranche.id).payout_to_date), 60.0)
        self.assertEqual(float(DealClause.query.get(clause.id).state_json['payout_to_date']), 60.0)
        self.assertTrue(any(entry['event_type'] == 'deal_profit_paid' for entry in logs))
        self.assertIn('build-loan repayment', logs[0]['description'])


if __name__ == '__main__':
    unittest.main()
