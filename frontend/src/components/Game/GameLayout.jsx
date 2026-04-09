import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import GameBoard from '../Board/GameBoard';
import PlayerPanel from './PlayerPanel';
import ActionPanel from './ActionPanel';
import EconomyDashboard from './EconomyDashboard';
import SidebarMenuStack from './SidebarMenuStack';
import StabilityWidget from './StabilityWidget';
import TradeQueueWidget from './TradeQueueWidget';
import DealsWidget from './DealsWidget';

// Modals
import PropertyModal from '../Modals/PropertyModal';
import CardDrawModal from '../Modals/CardDrawModal';
import BankruptcyModal from '../Modals/BankruptcyModal';
import UprisingOverlay from '../Modals/UprisingOverlay';
import HyperInflationBanner from '../Modals/HyperInflationBanner';
import GameOverModal from '../Modals/GameOverModal';
import AuctionModal from '../Auction/AuctionModal';
import TradePanel from '../Trade/TradePanel';
import DealDeskModal from '../Deal/DealDeskModal';
import LobbyModal from '../Lobby/LobbyModal';
import StabilityPanelModal from '../Modals/StabilityPanelModal';
import TaxationDetailsModal from '../Modals/TaxationDetailsModal';
import PlotPanelModal from '../Modals/PlotPanelModal';

import { useGameStore } from '../../hooks/useGameState';
import { gameGetLog } from '../../utils/api';

export default function GameLayout({ socketActions, myPlayerId }) {
  const { matchId } = useParams();
  const navigate = useNavigate();
  const {
    activeModal,
    uprisingEvent,
    pendingAction,
    setMatchId,
    setActiveModal,
    closeModal,
    setLogEntries,
    players,
    properties,
  } = useGameStore();

  const [selectedSpace, setSelectedSpace] = useState(null);

  // Load the latest log on mount. GamePage owns the initial state fetch.
  useEffect(() => {
    if (!matchId) return;
    setMatchId(Number(matchId));

    gameGetLog(matchId)
      .then((res) => {
        const entries = res.data?.entries || res.data?.log || [];
        if (entries.length) {
          setLogEntries(entries.map((entry) => ({
            ...entry,
            type: entry.type || entry.event_type || 'move',
            message: entry.message || entry.description || '',
          })));
        }
      })
      .catch(console.error);
  }, [matchId]);

  const handleSpaceClick = (space) => {
    if (!space || !['property', 'transit'].includes(space.type)) return;
    setSelectedSpace(space);
  };

  const selectedProperty = selectedSpace
    ? {
        ...selectedSpace,
        ...(properties[selectedSpace.position] || {}),
        board_position: selectedSpace.position,
        group_color: properties[selectedSpace.position]?.group_color || selectedSpace.groupColor || null,
        property_type: properties[selectedSpace.position]?.property_type || selectedSpace.type,
        base_price: properties[selectedSpace.position]?.base_price ?? selectedSpace.basePrice ?? null,
        current_value: properties[selectedSpace.position]?.current_value ?? selectedSpace.basePrice ?? null,
      }
    : null;

  return (
    <div className="flex flex-col h-screen bg-gray-900 text-white overflow-hidden">
      <HyperInflationBanner />

      {/* Main content area */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left: Board */}
        <div className="flex flex-1 overflow-hidden">
          <div className="relative flex-1 overflow-hidden bg-gray-950">
            <GameBoard
              players={players}
              properties={properties}
              onSpaceClick={handleSpaceClick}
            />
          </div>
        </div>

        {/* Right sidebar */}
        <div className="w-72 flex-shrink-0 border-l border-gray-700 flex flex-col overflow-hidden">
          {/* Sidebar widgets */}
          <div className="flex-1 overflow-y-auto p-3 space-y-3">
            <PlayerPanel />
            <EconomyDashboard />
            <StabilityWidget />
            <TradeQueueWidget />
            <DealsWidget />
            <SidebarMenuStack />
          </div>

          {/* Turn controls */}
          <div className="border-t border-gray-700 p-3 flex-shrink-0">
            <ActionPanel
              onRoll={socketActions?.rollDice}
              onEndTurn={socketActions?.endTurn}
              onPayJail={socketActions?.payJailBail}
              onJailCard={socketActions?.useJailCard}
              onDeclareBankruptcy={socketActions?.declareBankruptcy}
            />
          </div>
        </div>
      </div>

      {/* Uprising overlay — full screen */}
      {uprisingEvent && <UprisingOverlay event={uprisingEvent} />}

      {/* Modals */}
      {activeModal === 'property' && (
        <PropertyModal
          mode="prompt"
          data={pendingAction?.data}
          onBuy={socketActions?.buyProperty}
          onDecline={socketActions?.declineProperty}
          onClose={closeModal}
        />
      )}
      {selectedProperty && activeModal !== 'property' && (
        <PropertyModal
          mode="inspect"
          property={selectedProperty}
          onBuy={socketActions?.buyProperty}
          onDecline={socketActions?.declineProperty}
          onDevelop={socketActions?.developProperty}
          onMortgage={socketActions?.mortgageProperty}
          onSellHouse={socketActions?.sellHouse}
          onUnmortgage={socketActions?.unmortgageProperty}
          onClose={() => setSelectedSpace(null)}
        />
      )}
      {activeModal === 'card' && (
        <CardDrawModal
          data={pendingAction?.data}
          onClose={closeModal}
        />
      )}
      {activeModal === 'auction' && (
        <AuctionModal
          onBid={socketActions?.placeBid}
          onClose={closeModal}
        />
      )}
      {activeModal === 'trade' && (
        <TradePanel
          myPlayerId={myPlayerId}
          onSubmit={socketActions?.submitTrade}
          onRespond={socketActions?.respondTrade}
          onClose={closeModal}
        />
      )}
      {activeModal === 'deals' && (
        <DealDeskModal
          myPlayerId={myPlayerId}
          onSubmit={socketActions?.submitDeal}
          onRespond={socketActions?.respondDeal}
          onCounter={socketActions?.counterDeal}
          onCancel={socketActions?.cancelDeal}
          onClose={closeModal}
        />
      )}
      {activeModal === 'lobby' && (
        <LobbyModal
          matchId={matchId}
          onClose={closeModal}
        />
      )}
      {activeModal === 'taxation' && (
        <TaxationDetailsModal onClose={closeModal} />
      )}
      {activeModal === 'stability' && (
        <StabilityPanelModal
          onClose={closeModal}
          onSubmitNegotiation={socketActions?.submitNegotiation}
          onApplyEmergencyReform={socketActions?.applyEmergencyReform}
        />
      )}
      {activeModal === 'plot' && (
        <PlotPanelModal
          onClose={closeModal}
          onPlotStart={socketActions?.plotStart}
          onPlotAction={socketActions?.plotAction}
          onPlotJoin={socketActions?.plotJoin}
          onPlotLeave={socketActions?.plotLeave}
          onPlotCounterAction={socketActions?.plotCounterAction}
        />
      )}
      {activeModal === 'bankruptcy' && (
        <BankruptcyModal
          data={pendingAction?.data}
          onClose={closeModal}
        />
      )}
      {activeModal === 'game_over' && (
        <GameOverModal
          data={pendingAction?.data}
          onClose={() => navigate('/')}
        />
      )}
    </div>
  );
}
