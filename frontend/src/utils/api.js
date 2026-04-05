import axios from 'axios';

const api = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
  timeout: 15000,
  withCredentials: true,
});

// Attach auth token from localStorage if available
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('poorup_token');
  if (token) {
    config.headers['Authorization'] = `Bearer ${token}`;
  }
  return config;
});

// Auth
export const authRegister = (data) => api.post('/auth/register', data);
export const authLogin = (data) => api.post('/auth/login', data);

// Lobby
export const lobbyCreate = () => api.post('/lobby/create');
export const lobbyJoin = (data) => api.post('/lobby/join', data);
export const lobbyGet = (roomCode) => api.get(`/lobby/${roomCode}`);
export const lobbyUpdateSettings = (roomCode, settings) =>
  api.patch(`/lobby/${roomCode}/settings`, settings);
export const lobbyStart = (roomCode) => api.post(`/lobby/${roomCode}/start`);
export const lobbyAddBot = (roomCode, data = {}) => api.post(`/lobby/${roomCode}/bots`, data);
export const lobbyUpdateBot = (roomCode, playerId, data) =>
  api.patch(`/lobby/${roomCode}/bots/${playerId}`, data);
export const lobbyRemoveBot = (roomCode, playerId) => api.delete(`/lobby/${roomCode}/bots/${playerId}`);

// Game state
export const gameGetState = (matchId) => api.get(`/game/${matchId}/state`);
export const gameRoll = (matchId) => api.post(`/game/${matchId}/roll`);
export const gameBuy = (matchId) => api.post(`/game/${matchId}/buy`);
export const gameDecline = (matchId) => api.post(`/game/${matchId}/decline`);
export const gameDevelop = (matchId, data) => api.post(`/game/${matchId}/develop`, data);
export const gameMortgage = (matchId, data) => api.post(`/game/${matchId}/mortgage`, data);
export const gameUnmortgage = (matchId, data) => api.post(`/game/${matchId}/unmortgage`, data);
export const gameTrade = (matchId, data) => api.post(`/game/${matchId}/trade`, data);
export const gameRespondTrade = (matchId, tradeId, data) =>
  api.patch(`/game/${matchId}/trade/${tradeId}`, data);
export const gameLobby = (matchId, data) => api.post(`/game/${matchId}/lobby`, data);
export const gameGetDeals = (matchId) => api.get(`/game/${matchId}/deals`);
export const gameSubmitDeal = (matchId, data) => api.post(`/game/${matchId}/deals`, data);
export const gameRespondDeal = (matchId, dealId, data) => api.patch(`/game/${matchId}/deals/${dealId}`, data);
export const gameCounterDeal = (matchId, dealId, data) => api.post(`/game/${matchId}/deals/${dealId}/counter`, data);
export const gameCancelDeal = (matchId, dealId) => api.delete(`/game/${matchId}/deals/${dealId}`);
export const gameGetLog = (matchId) => api.get(`/game/${matchId}/log`);
export const gameJailPay = (matchId) => api.post(`/game/${matchId}/jail/pay`);
export const gameJailCard = (matchId) => api.post(`/game/${matchId}/jail/card`);

export { api };
export default api;
