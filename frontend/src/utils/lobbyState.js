import { useGameStore } from '../hooks/useGameState';
import { normalizePlayers, normalizeSettings } from './gameState';


function getStoredUserId() {
  if (typeof globalThis === 'undefined' || !globalThis.localStorage) {
    return null;
  }

  try {
    const rawUser = globalThis.localStorage.getItem('poorup_user');
    if (!rawUser) {
      return null;
    }

    const parsedUser = JSON.parse(rawUser);
    const userId = Number(parsedUser?.id);
    return Number.isFinite(userId) ? userId : null;
  } catch {
    return null;
  }
}


export function resolveLobbyPlayerId(players = [], fallbackPlayerId = null) {
  const numericFallback = Number(fallbackPlayerId);
  if (Number.isFinite(numericFallback) && players.some((player) => player.id === numericFallback)) {
    return numericFallback;
  }

  const storedUserId = getStoredUserId();
  if (storedUserId == null) {
    return null;
  }

  const matchingPlayer = players.find((player) => Number(player.user_id) === storedUserId);
  return matchingPlayer?.id ?? null;
}


export function buildTakenColors(players = [], takenColors = []) {
  if (Array.isArray(takenColors) && takenColors.length > 0) {
    return takenColors.filter(Boolean);
  }

  return players.map((player) => player.color_hex).filter(Boolean);
}


export function applyLobbySnapshot(snapshot, { roomCode } = {}) {
  if (!snapshot) {
    return null;
  }

  const storeState = useGameStore.getState();
  const normalizedPlayers = normalizePlayers(snapshot.players || []);
  const normalizedSettings = normalizeSettings(snapshot.settings || {});
  const resolvedMyPlayerId = snapshot.your_player_id != null
    ? Number(snapshot.your_player_id)
    : resolveLobbyPlayerId(normalizedPlayers, storeState.myPlayerId);
  const resolvedRoomCode = String(snapshot.match?.room_code || roomCode || storeState.roomCode || '').trim().toUpperCase();
  const resolvedMatchId = snapshot.match?.id ?? storeState.matchId ?? null;

  const nextState = {
    lobbyData: snapshot,
    players: normalizedPlayers,
    settings: normalizedSettings,
    takenColors: buildTakenColors(normalizedPlayers, snapshot.taken_colors),
    roomCode: resolvedRoomCode,
    matchId: resolvedMatchId,
  };

  if (resolvedMyPlayerId != null) {
    nextState.myPlayerId = resolvedMyPlayerId;
  } else if (storeState.myPlayerId != null && !normalizedPlayers.some((player) => player.id === storeState.myPlayerId)) {
    nextState.myPlayerId = null;
  }

  useGameStore.setState(nextState);
  return nextState;
}