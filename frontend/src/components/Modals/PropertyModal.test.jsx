import { fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { useGameStore } from '../../hooks/useGameState';
import PropertyModal from './PropertyModal';


function setStoreState() {
  const property = {
    id: 11,
    board_position: 11,
    name: 'Karachi',
    owner_id: 1,
    property_type: 'property',
    group_color: '#EC4899',
    base_price: 120,
    current_value: 120,
    dev_level: 1,
    is_mortgaged: false,
    deal_investment_options: [
      {
        deal_id: 5,
        clause_id: 9,
        escrow_remaining: 220,
        profit_share_percent: 0.3,
        max_payout: 300,
      },
    ],
    deal_profit_obligations: [
      {
        deal_id: 5,
        tranche_id: 12,
        profit_share_percent: 0.3,
        payout_to_date: 60,
        max_payout: 300,
      },
    ],
  };

  useGameStore.setState({
    pendingAction: null,
    myPlayerId: 1,
    currentPlayerId: 1,
    players: [
      { id: 1, username: 'Atlas', balance: 900 },
      { id: 2, username: 'Rival', balance: 700 },
    ],
    properties: {
      11: property,
    },
    economy: {
      gov_type: 'liberal_democracy',
      government_type: 'liberal_democracy',
      market_confidence: 79,
      capital_yield_rate: 0.021,
      private_equity_bonus_multiplier: 1.15,
    },
    social: {
      plot: {
        exists: false,
        public: false,
        member_ids: [],
        coalition_member_ids: [],
        committed_member_ids: [],
        command_chain: [],
        action_catalog: [],
        counter_action_catalog: [],
        legal_targets: [],
        seized_properties: [],
        seized_property_ids: [],
      },
      properties: {},
    },
  });

  return property;
}


describe('PropertyModal', () => {
  afterEach(() => {
    useGameStore.setState({
      pendingAction: null,
      myPlayerId: null,
      currentPlayerId: null,
      players: [],
      properties: {},
      economy: {},
      social: { plot: {}, properties: {} },
    });
  });

  it('shows effective PE ceilings under liberal democracy', () => {
    const property = setStoreState();

    render(
      <PropertyModal
        property={property}
        mode="details"
        onBuy={vi.fn()}
        onDecline={vi.fn()}
        onDevelop={vi.fn()}
        onMortgage={vi.fn()}
        onSellHouse={vi.fn()}
        onUnmortgage={vi.fn()}
        onClose={vi.fn()}
      />,
    );

    expect(screen.getByText("This Round's Cash Rules")).toBeInTheDocument();
    expect(screen.getByText(/1v1 bonus active:/i)).toBeInTheDocument();
    expect(screen.getAllByText(/\$380/).length).toBeGreaterThan(0);
  });

  it('shows property-scoped plot actions in the plot tab', () => {
    const property = setStoreState();
    const onPlotAction = vi.fn();

    useGameStore.setState({
      social: {
        plot: {
          exists: true,
          public: false,
          stage: 3,
          member_ids: [1],
          coalition_member_ids: [],
          committed_member_ids: [1],
          command_chain: [
            {
              player_id: 1,
              username: 'Atlas',
              role: 'organizer',
              can_issue_orders: true,
              can_manage_membership: true,
            },
          ],
          action_catalog: [
            {
              action_type: 'agitate_property',
              stage: 1,
              cost: { support: 2 },
              description: 'Raise agitation on a specific property.',
              label: 'Agitate Property',
            },
          ],
          counter_action_catalog: [],
          legal_targets: [
            {
              property_id: 11,
              owner_id: 1,
              board_position: 11,
              agitation: 2,
              preview_score: 9,
            },
          ],
          seized_properties: [],
          seized_property_ids: [],
        },
        properties: {
          '11': {
            property_id: 11,
            plot_seized: false,
          },
        },
      },
    });

    render(
      <PropertyModal
        property={property}
        mode="details"
        onBuy={vi.fn()}
        onDecline={vi.fn()}
        onDevelop={vi.fn()}
        onMortgage={vi.fn()}
        onSellHouse={vi.fn()}
        onUnmortgage={vi.fn()}
        onPlotAction={onPlotAction}
        onPlotCounterAction={vi.fn()}
        onOpenPlotPanel={vi.fn()}
        onClose={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Plot' }));

    expect(screen.getByRole('button', { name: 'Increase Support' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Increase Support' }));
    expect(onPlotAction).toHaveBeenCalledWith({ action_type: 'agitate_property', property_id: 11 });
  });
});