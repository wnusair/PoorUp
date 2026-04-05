import { useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useGameStore } from '../hooks/useGameState';
import { useSocket } from '../hooks/useSocket';
import GameLayout from '../components/Game/GameLayout';
import { api } from '../utils/api';
import {
  normalizeDeals,
  normalizeEconomy,
  normalizePendingDebts,
  normalizePlayers,
  normalizeProperties,
  normalizeSocial,
  normalizeSettings,
} from '../utils/gameState';

export default function GamePage() {
  const { matchId } = useParams();
  const numericMatchId = Number(matchId);
  const navigate = useNavigate();
  const {
    setMyPlayerId, setMatchId, setGamePhase,
    setPlayers, setProperties, setEconomy,
    setDeals,
    setPendingDebts,
    setTaxStats,
    setLobbyingStats,
    setPlayerFinanceHistory,
    setSocial,
    setCurrentPlayerId,
    setSettings,
    setAwaitingEndTurnPlayerId,
    setPendingAction,
    clearPendingAction,
    setActiveModal,
    setDiceResult,
    setDiceRolledThisTurn,
    setIsRolling,
    gamePhase,
  } = useGameStore();

  // Fetch initial full game state
  useEffect(() => {
    async function fetchState() {
      try {
        const { data } = await api.get(`/game/${matchId}/state`);
        const gs = data.state;
        if (!gs) return;

        setMatchId(numericMatchId);
        setGamePhase('playing');

        if (gs.players) {
          setPlayers(normalizePlayers(gs.players));
        }

        const normalizedSocial = normalizeSocial(gs.social, gs);
        setSocial(normalizedSocial);

        setPendingDebts(normalizePendingDebts(gs.pending_debts || []));
        setDeals(normalizeDeals(gs.deals || []));

        if (gs.properties) {
          setProperties(normalizeProperties(gs.properties, normalizedSocial.properties));
        }

          if (gs.econ) setEconomy(normalizeEconomy(gs.econ, gs));
          if (gs.tax_stats) setTaxStats(gs.tax_stats);
          if (gs.lobbying_stats) setLobbyingStats(gs.lobbying_stats);
          if (gs.player_finance_history) setPlayerFinanceHistory(gs.player_finance_history);
        if (gs.settings) setSettings(normalizeSettings(gs.settings));

        if (gs.current_player_id != null) {
          setCurrentPlayerId(gs.current_player_id);
        }

        setAwaitingEndTurnPlayerId(gs.awaiting_end_turn_player_id ?? null);

        if (gs.dice_rolled_this_turn != null) {
          const diceRolled = Boolean(gs.dice_rolled_this_turn);
          setDiceRolledThisTurn(diceRolled);
          if (!diceRolled) {
            setDiceResult(null);
            setIsRolling(false);
          }
        }

        const user = JSON.parse(localStorage.getItem('poorup_user') || 'null');
        let myResolvedPlayerId = null;
        if (user && gs.players) {
          const me = gs.players.find(p => p.user_id === user.id);
          if (me) {
            myResolvedPlayerId = me.id;
            setMyPlayerId(me.id);
          }
        }

        if (gs.pending_action && gs.pending_action.player_id === myResolvedPlayerId) {
          const pendingType = gs.pending_action.type || 'buy_property';
          setPendingAction({ type: pendingType, data: gs.pending_action });
          if (pendingType === 'buy_property') {
            setActiveModal('property');
          }
        } else {
          clearPendingAction();
        }
      } catch (err) {
        console.error('Failed to fetch game state:', err);
      }
    }
    fetchState();
  }, [matchId]);

  // Socket
  const myPlayerId = useGameStore((state) => state.myPlayerId);
  const socketActions = useSocket({
    matchId: Number.isFinite(numericMatchId) ? numericMatchId : null,
    roomCode: null,
    playerId: myPlayerId,
    enabled: Boolean(myPlayerId && numericMatchId),
  });

  // Redirect when game ends
  useEffect(() => {
    if (gamePhase === 'ended') {
      // Stay on page — GameOverModal will show
    }
  }, [gamePhase, navigate]);

  return <GameLayout socketActions={socketActions} myPlayerId={myPlayerId} />;
}
