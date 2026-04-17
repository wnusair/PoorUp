import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { useGameStore } from '../../hooks/useGameState';
import PlotPanelModal from './PlotPanelModal';


describe('PlotPanelModal founder entry', () => {
  afterEach(() => {
    act(() => {
      useGameStore.setState({
        social: { plot: {} },
        players: [],
        properties: {},
        myPlayerId: null,
      });
    });
  });

  it('shows the founder action when the current player is eligible', async () => {
    const onPlotStart = vi.fn().mockResolvedValue({ summary: 'The plot has begun.' });

    act(() => {
      useGameStore.setState({
        social: { plot: {} },
        players: [
          {
            id: 1,
            username: 'Atlas',
            plot_can_found: true,
            plot_role: null,
          },
        ],
        properties: {},
        myPlayerId: 1,
      });
    });

    render(
      <PlotPanelModal
        onClose={vi.fn()}
        onPlotStart={onPlotStart}
        onPlotAction={vi.fn()}
        onPlotJoin={vi.fn()}
        onPlotLeave={vi.fn()}
        onPlotCounterAction={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Organization' }));
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Found The Plot' }));
    });

    expect(onPlotStart).toHaveBeenCalledWith({});
    await waitFor(() => {
      expect(screen.getByText('The plot has begun.')).toBeInTheDocument();
    });
  });

  it('lets a member request entry from the organization tab', async () => {
    const onPlotJoin = vi.fn().mockResolvedValue({ summary: 'Request sent.' });

    act(() => {
      useGameStore.setState({
        social: {
          plot: {
            exists: true,
            public: true,
            member_ids: [2],
            coalition_member_ids: [],
            join_requests: {},
            join_invites: {},
            command_chain: [],
            recruitable_players: [],
            action_catalog: [],
            counter_action_catalog: [],
            clusters: [],
            regions: {},
          },
        },
        players: [
          {
            id: 1,
            username: 'Atlas',
            plot_can_found: false,
            plot_role: null,
            plot_hardship_trigger_count: 2,
          },
          {
            id: 2,
            username: 'Founder',
            plot_role: 'founder',
          },
        ],
        properties: {},
        myPlayerId: 1,
      });
    });

    render(
      <PlotPanelModal
        onClose={vi.fn()}
        onPlotStart={vi.fn()}
        onPlotAction={vi.fn()}
        onPlotJoin={onPlotJoin}
        onPlotLeave={vi.fn()}
        onPlotCounterAction={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Organization' }));
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Request To Join' }));
    });

    expect(onPlotJoin).toHaveBeenCalledWith({ intent: 'request' });
    await waitFor(() => {
      expect(screen.getByText('Request sent.')).toBeInTheDocument();
    });
  });

  it('shows next-stage requirements and explains missing promotion progress', () => {
    act(() => {
      useGameStore.setState({
        social: {
          plot: {
            exists: true,
            stage: 2,
            stage_name: 'Agitation Network',
            next_stage: {
              stage: 3,
              stage_name: 'Open Seizure',
              requirements: [
                { label: 'Committed members 0/1', met: false },
                { label: 'Support 4/6', met: false },
              ],
            },
            public: false,
            member_ids: [1, 2],
            coalition_member_ids: [],
            join_requests: {},
            join_invites: {},
            recruitable_players: [],
            action_catalog: [
              {
                action_type: 'convert_to_organizer',
                stage: 2,
              },
            ],
            counter_action_catalog: [],
            clusters: [],
            regions: {},
            command_chain: [
              {
                player_id: 1,
                username: 'Atlas',
                role: 'founder',
                can_manage_membership: true,
                can_issue_orders: true,
                is_commander: true,
                next_role: 'committed_member',
                contribution_round_count: 1,
                required_contribution_rounds: 1,
                successful_actions_supported: 1,
                required_successful_actions: 1,
                promotion_ready: true,
              },
              {
                player_id: 2,
                username: 'Rival',
                role: 'sympathizer',
                can_manage_membership: false,
                can_issue_orders: false,
                is_commander: false,
                next_role: 'organizer',
                contribution_round_count: 1,
                required_contribution_rounds: 2,
                successful_actions_supported: 0,
                required_successful_actions: 1,
                promotion_ready: false,
              },
            ],
          },
        },
        players: [
          {
            id: 1,
            username: 'Atlas',
            plot_can_found: false,
            plot_role: 'founder',
            plot_hardship_trigger_count: 3,
          },
          {
            id: 2,
            username: 'Rival',
            plot_role: 'sympathizer',
          },
        ],
        properties: {},
        myPlayerId: 1,
      });
    });

    render(
      <PlotPanelModal
        onClose={vi.fn()}
        onPlotStart={vi.fn()}
        onPlotAction={vi.fn()}
        onPlotJoin={vi.fn()}
        onPlotLeave={vi.fn()}
        onPlotCounterAction={vi.fn()}
      />,
    );

    expect(screen.getByText('Need: Committed members 0/1')).toBeInTheDocument();
    expect(screen.getByText('Need: Support 4/6')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Operations' }));

    expect(screen.getByText('Promotion to organizer unlocks plot operations and regional orders.')).toBeInTheDocument();
    expect(screen.getByText('Needs 2 contribution rounds. Current progress: 1/2.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Promote' })).toBeDisabled();
  });
});