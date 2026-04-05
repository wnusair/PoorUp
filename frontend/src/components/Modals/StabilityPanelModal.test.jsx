import { fireEvent, render, screen } from '@testing-library/react';
import StabilityPanelModal from './StabilityPanelModal';
import { useGameStore } from '../../hooks/useGameState';


function seedStore(overrides = {}) {
  useGameStore.setState({
    players: [
      { id: 1, username: 'Atlas', balance: 500 },
      { id: 2, username: 'Rival', balance: 650 },
      { id: 3, username: 'Broker', balance: 425 },
    ],
    myPlayerId: 1,
    economy: {
      gov_type: 'liberal_democracy',
      government_type: 'liberal_democracy',
    },
    properties: {
      1: {
        id: 11,
        name: 'Lagos',
        board_position: 1,
        owner_id: 1,
        current_value: 180,
        dev_level: 1,
      },
      2: {
        id: 12,
        name: 'Nairobi',
        board_position: 2,
        owner_id: 2,
        current_value: 160,
        dev_level: 0,
      },
    },
    social: {
      overall_rage: 72,
      stability_percent: 34,
      grievance_mix: { tax_pressure: 44, welfare_shortfall: 31, hostile_lobbying: 18 },
      territories: [
        {
          territory_key: '1|Africa',
          owner_id: 1,
          owner_name: 'Atlas',
          region: 'Africa',
          territory_instability: 84,
          active_incident_count: 1,
          unionized_property_count: 0,
          property_ids: [11],
          property_count: 1,
          dominant_grievances: ['tax_pressure'],
        },
        {
          territory_key: '2|Africa',
          owner_id: 2,
          owner_name: 'Rival',
          region: 'Africa',
          territory_instability: 62,
          active_incident_count: 0,
          unionized_property_count: 0,
          property_ids: [12],
          property_count: 1,
          dominant_grievances: ['hostile_lobbying'],
        },
      ],
      active_incidents: [
        {
          incident_id: 'incident-1',
          property_id: 11,
          incident_type: 'strike',
          negotiation_target: 180,
          negotiation_committed: 20,
          remaining_rounds: 2,
          spread_block_active: true,
        },
      ],
      properties: {
        11: {
          property_id: 11,
          incident_type: 'strike',
          tension: 81,
          region: 'Africa',
          dominant_grievance: 'tax_pressure',
          negotiation_target: 180,
          negotiation_committed: 20,
          remaining_rounds: 2,
          reason_breakdown: [
            { key: 'tax_pressure', label: 'Taxes are amplifying local stress', points: 12.4 },
            { key: 'hostile_lobbying', label: 'Owner is funding hostile anti-relief lobbying from a position of concentrated wealth', points: 9.2 },
          ],
          hostile_lobby_targets: [
            { target: 'welfare_decrease', label: 'Welfare Cuts', contribution: 120, pool_total: 220, points: 9.2 },
          ],
          recommended_actions: [
            { type: 'lobby', label: 'Reverse the hostile welfare or housing push', expected_relief: 15 },
            { type: 'negotiate', label: 'Fund local concessions before the backlash compounds', expected_relief: 18 },
          ],
        },
        12: {
          property_id: 12,
          tension: 58,
          territory_instability: 62,
          region: 'Africa',
          dominant_grievance: 'hostile_lobbying',
          reason_breakdown: [
            { key: 'hostile_lobbying', label: 'Owner is funding hostile anti-relief lobbying from a position of concentrated wealth', points: 8.5 },
          ],
          hostile_lobby_targets: [
            { target: 'welfare_decrease', label: 'Welfare Cuts', contribution: 90, pool_total: 220, points: 8.5 },
          ],
          recommended_actions: [
            { type: 'lobby', label: 'Reverse the hostile welfare or housing push', expected_relief: 15 },
          ],
        },
      },
      unionized_property_count: 0,
      national_flashpoint: {
        hottest_territory: {
          region: 'Africa',
          territory_instability: 84,
          owner_name: 'Atlas',
        },
        next_likely_escalation: {
          property_id: 11,
          tension: 81,
          next_state: 'uprising',
        },
      },
    },
    ...overrides,
  });
}


describe('StabilityPanelModal', () => {
  beforeEach(() => {
    seedStore();
  });

  it('renders national stability metrics and incident cards', () => {
    render(<StabilityPanelModal onClose={() => {}} />);

    expect(screen.getByText('Stability Panel')).toBeInTheDocument();
    expect(screen.getByText('Overall Rage')).toBeInTheDocument();
    expect(screen.getByText('Properties Close To Revolt')).toBeInTheDocument();
    expect(screen.getByText('Owner: Atlas')).toBeInTheDocument();
    expect(screen.getAllByText('Lagos').length).toBeGreaterThan(0);
  });

  it('submits negotiation funding through the provided callback', () => {
    const handleSubmitNegotiation = vi.fn();

    render(
      <StabilityPanelModal
        onClose={() => {}}
        onSubmitNegotiation={handleSubmitNegotiation}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Negotiation' }));

    const amountInput = screen.getByDisplayValue('160');
    fireEvent.change(amountInput, { target: { value: '75' } });
    expect(screen.getByText(/Projected relief if funded this round:/)).toBeInTheDocument();
    fireEvent.click(screen.getByText('Contribute'));

    expect(handleSubmitNegotiation).toHaveBeenCalledWith({
      property_id: 11,
      contribution: 75,
    });
  });

  it('shows Minarchist emergency reform controls when applicable', () => {
    seedStore({
      economy: {
        gov_type: 'minarchism',
        government_type: 'minarchism',
      },
    });

    render(
      <StabilityPanelModal
        onClose={() => {}}
        onApplyEmergencyReform={() => {}}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Negotiation' }));

    expect(screen.getByText('Private Relief Contract')).toBeInTheDocument();
    expect(screen.getByText('Tax Moratorium')).toBeInTheDocument();
    expect(screen.getByText('Property Rights Compact')).toBeInTheDocument();
  });

  it('lets you select a player and inspect their property instability breakdown', () => {
    render(<StabilityPanelModal onClose={() => {}} />);

    fireEvent.click(screen.getByRole('button', { name: 'Player Breakdown' }));
    fireEvent.click(screen.getByRole('button', { name: 'Rival' }));

    expect(screen.getByText('Net worth $810.00')).toBeInTheDocument();
    expect(screen.getAllByText('Nairobi').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Welfare Cuts').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Owner is funding hostile anti-relief lobbying from a position of concentrated wealth').length).toBeGreaterThan(0);
  });
});