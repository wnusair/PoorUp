import { useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useGameStore } from '../hooks/useGameState';
import { useSocket } from '../hooks/useSocket';
import LobbyRoom from '../components/Lobby/LobbyRoom';
import { api } from '../utils/api';
import { normalizeSettings } from '../utils/gameState';

export default function LobbyPage() {
  const { roomCode } = useParams();
  const normalizedRoomCode = roomCode?.trim().toUpperCase() || '';
  const navigate = useNavigate();
  const {
    lobbyData, setLobbyData, setMyPlayerId, setRoomCode, setMatchId,
    setPlayers, setSettings,
  } = useGameStore();

  // Load initial lobby state from REST
  useEffect(() => {
    async function fetchLobby() {
      try {
        const { data } = await api.get(`/lobby/${normalizedRoomCode}`);
        setLobbyData(data);
        setRoomCode(normalizedRoomCode);
        if (data.players) setPlayers(data.players);
        if (data.settings) setSettings(normalizeSettings(data.settings));
        if (data.match?.id) setMatchId(data.match.id);

        if (data.match?.status === 'active' && data.match?.id) {
          useGameStore.getState().setGamePhase('playing');
          navigate(`/game/${data.match.id}`, { replace: true });
          return;
        }

        // Determine my player from stored user
        const user = JSON.parse(localStorage.getItem('poorup_user') || 'null');
        if (user && data.players) {
          const me = data.players.find(p => p.user_id === user.id);
          if (me) setMyPlayerId(me.id);
        }
      } catch (err) {
        console.error('Failed to load lobby:', err);
      }
    }
    fetchLobby();
  }, [navigate, normalizedRoomCode, setLobbyData, setMatchId, setMyPlayerId, setPlayers, setRoomCode, setSettings]);

  // Socket connection for live lobby updates
  const myPlayerId = useGameStore(s => s.myPlayerId);
  useSocket({
    roomCode: normalizedRoomCode,
    playerId: myPlayerId,
    enabled: true,
  });

  // Listen for game_start to navigate to game
  useEffect(() => {
    const unsub = useGameStore.subscribe(
      state => state.gamePhase,
      phase => {
        if (phase === 'playing') {
          const matchId = useGameStore.getState().matchId;
          navigate(`/game/${matchId}`);
        }
      }
    );
    return unsub;
  }, [navigate]);

  if (!lobbyData) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-950">
        <div className="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-950 p-4 md:p-8">
      <LobbyRoom roomCode={normalizedRoomCode} />
    </div>
  );
}
