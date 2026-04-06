import { useRef, useEffect, useState } from 'react';
import BoardSpace from './BoardSpace';
import { BOARD_SPACES, needsDarkText } from '../../utils/constants';
import { useGameStore } from '../../hooks/useGameState';

/**
 * Board layout — 48 spaces, LANDSCAPE orientation (wider than tall).
 *
 * Corners:
 *   pos  0 = START       → top-left
 *   pos 11 = JAIL        → bottom-left
 *   pos 20 = FREE SPACE  → bottom-right
 *   pos 30 = GO TO JAIL  → top-right
 *
 * Clockwise movement:
 *   Top row    (L→R): 0, [47..31], 30   — 17 inner spaces
 *   Right col  (T→B): [29..21]          — 9 inner spaces
 *   Bottom row (L→R): 11, [12..19], 20  — 8 inner spaces
 *   Left col   (T→B): [1..10]           — 10 inner spaces
 */

const spaceByPos = Object.fromEntries(BOARD_SPACES.map((s) => [s.position, s]));

const CORNER_POSITIONS = new Set([0, 11, 20, 30]);

// Top row: L→R, corners 0 (TL) and 30 (TR), inner = 47 down to 31
const topRow = [0, 47, 46, 45, 44, 43, 42, 41, 40, 39, 38, 37, 36, 35, 34, 33, 32, 31, 30];
// Right col inner: T→B, 29 down to 21
const rightColInner = [29, 28, 27, 26, 25, 24, 23, 22, 21];
// Bottom row: L→R, corners 11 (BL) and 20 (BR), inner = 12 up to 19
const bottomRow = [11, 12, 13, 14, 15, 16, 17, 18, 19, 20];
// Left col inner: T→B, 1 up to 10
const leftColInner = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10];

const BOARD_INSET = 10;

// Cell sizing
const CORNER = 72;
const EDGE_W = 46;  // width of each inner cell on the top row (17 cells)
const EDGE_H = 60;  // height of each inner cell on the left col (10 cells)

const TOP_INNER = topRow.length - 2;      // 17
const BOTTOM_INNER = bottomRow.length - 2; // 8
const LEFT_INNER = leftColInner.length;    // 10
const RIGHT_INNER = rightColInner.length;  // 9

// Board dimensions are determined by the longest sides
const innerW = TOP_INNER * EDGE_W;        // 782px — width for inner area
const innerH = LEFT_INNER * EDGE_H;       // 600px — height for inner area
const totalW = CORNER + innerW + CORNER;  // 926px
const totalH = CORNER + innerH + CORNER;  // 744px

function buildBoardMetrics(containerWidth, containerHeight) {
  const availableWidth = Math.max(320, containerWidth - (BOARD_INSET * 2));
  const availableHeight = Math.max(260, containerHeight - (BOARD_INSET * 2));
  const preferredCorner = Math.min(
    availableWidth / (totalW / CORNER),
    availableHeight / (totalH / CORNER),
  );
  const corner = Math.max(36, preferredCorner);
  const boardWidth = availableWidth;
  const boardHeight = availableHeight;
  const responsiveInnerWidth = Math.max(1, boardWidth - (corner * 2));
  const responsiveInnerHeight = Math.max(1, boardHeight - (corner * 2));
  const tokenSize = Math.max(
    22,
    Math.min(40, Math.min(corner, responsiveInnerWidth / TOP_INNER, responsiveInnerHeight / LEFT_INNER) * 0.48),
  );

  return {
    inset: BOARD_INSET,
    boardWidth,
    boardHeight,
    corner,
    innerWidth: responsiveInnerWidth,
    innerHeight: responsiveInnerHeight,
    topCellW: responsiveInnerWidth / TOP_INNER,
    bottomCellW: responsiveInnerWidth / BOTTOM_INNER,
    leftCellH: responsiveInnerHeight / LEFT_INNER,
    rightCellH: responsiveInnerHeight / RIGHT_INNER,
    tokenSize,
  };
}

/**
 * Returns the center pixel coordinate of a board space on the responsive board.
 */
function getSpaceCenter(pos, metrics) {
  const {
    corner,
    boardWidth,
    boardHeight,
    topCellW,
    bottomCellW,
    leftCellH,
    rightCellH,
  } = metrics;

  // TL corner: 0
  if (pos === 0) return { x: corner / 2, y: corner / 2 };
  // Left col: 1–10 (top→bottom)
  if (pos >= 1 && pos <= 10)
    return { x: corner / 2, y: corner + (pos - 1) * leftCellH + leftCellH / 2 };
  // BL corner: 11
  if (pos === 11) return { x: corner / 2, y: boardHeight - corner / 2 };
  // Bottom row inner: 12–19 (left→right)
  if (pos >= 12 && pos <= 19)
    return { x: corner + (pos - 12) * bottomCellW + bottomCellW / 2, y: boardHeight - corner / 2 };
  // BR corner: 20
  if (pos === 20) return { x: boardWidth - corner / 2, y: boardHeight - corner / 2 };
  // Right col: 21–29 (29 is near top, 21 is near bottom)
  if (pos >= 21 && pos <= 29) {
    const rowIndex = 29 - pos; // 0 for pos=29, 8 for pos=21
    return { x: boardWidth - corner / 2, y: corner + rowIndex * rightCellH + rightCellH / 2 };
  }
  // TR corner: 30
  if (pos === 30) return { x: boardWidth - corner / 2, y: corner / 2 };
  // Top row inner: 31–47 (DOM left→right order: 47, 46, ..., 31)
  if (pos >= 31 && pos <= 47) {
    const cellIndex = 47 - pos; // 0 for pos=47 (leftmost inner), 16 for pos=31
    return { x: corner + cellIndex * topCellW + topCellW / 2, y: corner / 2 };
  }
  return { x: 0, y: 0 };
}

export default function GameBoard({ players = [], properties = {}, onSpaceClick }) {
  const containerRef = useRef(null);
  const [boardSize, setBoardSize] = useState({
    width: totalW + (BOARD_INSET * 2),
    height: totalH + (BOARD_INSET * 2),
  });
  const { playerAnimPositions, movingPlayerId } = useGameStore();

  const metrics = buildBoardMetrics(boardSize.width, boardSize.height);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const compute = () => {
      const width = el.clientWidth;
      const height = el.clientHeight;
      if (!width || !height) return;
      setBoardSize((current) => (
        current.width === width && current.height === height
          ? current
          : { width, height }
      ));
    };
    compute();
    const ro = new ResizeObserver(compute);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const getOwner = (position) => {
    const prop = properties[position];
    if (!prop?.owner_id) return null;
    return players.find((p) => p.id === prop.owner_id) || null;
  };

  const renderSpace = (pos, orientation, isCorner = false) => {
    const space = spaceByPos[pos];
    if (!space) return null;

    const liveProperty = properties[pos];
    const mergedSpace = liveProperty
      ? {
          ...space,
          type: liveProperty.property_type || space.type,
          groupColor: liveProperty.group_color ?? space.groupColor ?? null,
          basePrice: liveProperty.base_price ?? space.basePrice ?? null,
          dev_level: liveProperty.dev_level ?? liveProperty.development_level ?? 0,
          development_level: liveProperty.development_level ?? liveProperty.dev_level ?? 0,
        }
      : space;

    return (
      <BoardSpace
        key={pos}
        space={mergedSpace}
        owner={getOwner(pos)}
        orientation={orientation}
        isCorner={isCorner}
        onClick={onSpaceClick}
      />
    );
  };

  // Build overlay tokens — one per non-bankrupt player, positioned at their
  // current animated board position with CSS transitions for smooth movement.
  const overlayTokens = players
    .filter((p) => !p.bankrupt)
    .map((player) => {
      const pos = playerAnimPositions[player.id] ?? player.position ?? 0;

      // Count players sharing this space to stagger tokens
      const siblings = players.filter(
        (p) => !p.bankrupt && (playerAnimPositions[p.id] ?? p.position ?? 0) === pos
      );
      const offsetIndex = siblings.findIndex((p) => p.id === player.id);
      const offset = offsetIndex * Math.max(4, metrics.tokenSize * 0.18);

      const { x, y } = getSpaceCenter(pos, metrics);
      const isMoving = player.id === movingPlayerId;
      const color = player.color_hex || '#888';
      const textColor = needsDarkText(color) ? '#111' : '#fff';

      return (
        <div
          key={player.id}
          title={player.username}
          style={{
            position: 'absolute',
            width: `${metrics.tokenSize}px`,
            height: `${metrics.tokenSize}px`,
            left: `${x - metrics.tokenSize / 2 - offset}px`,
            top: `${y - metrics.tokenSize / 2 - offset}px`,
            // Smooth glide between spaces — matches the STEP_MS in useSocket
            transition: 'left 0.13s ease-out, top 0.13s ease-out, box-shadow 0.1s, transform 0.1s',
            backgroundColor: color,
            color: textColor,
            borderRadius: '50%',
            border: isMoving ? '2.5px solid #fff' : '2px solid rgba(255,255,255,0.55)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: `${Math.max(10, metrics.tokenSize * 0.38)}px`,
            fontWeight: 'bold',
            userSelect: 'none',
            zIndex: 20 + offsetIndex,
            boxShadow: isMoving
              ? `0 0 0 4px rgba(255,255,255,0.75), 0 0 18px 7px ${color}, 0 3px 10px rgba(0,0,0,0.5)`
              : '0 2px 6px rgba(0,0,0,0.45)',
            transform: isMoving ? 'scale(1.25)' : 'scale(1)',
            overflow: 'hidden',
          }}
        >
          {player.username?.[0]?.toUpperCase() || '?'}
          {isMoving && (
            <span
              className="animate-ping"
              style={{
                position: 'absolute',
                inset: 0,
                borderRadius: '50%',
                backgroundColor: color,
                opacity: 0.4,
                pointerEvents: 'none',
              }}
            />
          )}
        </div>
      );
    });

  return (
    <div ref={containerRef} className="relative h-full w-full overflow-hidden">
      <div
        className="absolute select-none"
        style={{
          left: `${metrics.inset}px`,
          top: `${metrics.inset}px`,
          width: `${metrics.boardWidth}px`,
          height: `${metrics.boardHeight}px`,
        }}
      >
        {/* Top row: corners 0 (TL) and 30 (TR), inner positions 47→31 */}
        <div
          className="absolute flex"
          style={{ top: 0, left: 0, width: `${metrics.boardWidth}px`, height: `${metrics.corner}px` }}
        >
          {topRow.map((pos) => {
            const isC = CORNER_POSITIONS.has(pos);
            return (
              <div
                key={pos}
                style={{
                  width: isC ? `${metrics.corner}px` : `${metrics.topCellW}px`,
                  height: `${metrics.corner}px`,
                  flexShrink: 0,
                }}
              >
                {renderSpace(pos, 'top', isC)}
              </div>
            );
          })}
        </div>

        {/* Bottom row: corners 11 (BL) and 20 (BR), inner positions 12→19 */}
        <div
          className="absolute flex"
          style={{ bottom: 0, left: 0, width: `${metrics.boardWidth}px`, height: `${metrics.corner}px` }}
        >
          {bottomRow.map((pos) => {
            const isC = CORNER_POSITIONS.has(pos);
            return (
              <div
                key={pos}
                style={{
                  width: isC ? `${metrics.corner}px` : `${metrics.bottomCellW}px`,
                  height: `${metrics.corner}px`,
                  flexShrink: 0,
                }}
              >
                {renderSpace(pos, 'bottom', isC)}
              </div>
            );
          })}
        </div>

        {/* Left col inner: positions 1→10, T→B */}
        <div
          className="absolute flex flex-col"
          style={{
            top: `${metrics.corner}px`,
            left: 0,
            width: `${metrics.corner}px`,
            height: `${metrics.innerHeight}px`,
          }}
        >
          {leftColInner.map((pos) => (
            <div
              key={pos}
              style={{ width: `${metrics.corner}px`, height: `${metrics.leftCellH}px`, flexShrink: 0 }}
            >
              {renderSpace(pos, 'left', false)}
            </div>
          ))}
        </div>

        {/* Right col inner: positions 29→21, T→B */}
        <div
          className="absolute flex flex-col"
          style={{
            top: `${metrics.corner}px`,
            right: 0,
            width: `${metrics.corner}px`,
            height: `${metrics.innerHeight}px`,
          }}
        >
          {rightColInner.map((pos) => (
            <div
              key={pos}
              style={{ width: `${metrics.corner}px`, height: `${metrics.rightCellH}px`, flexShrink: 0 }}
            >
              {renderSpace(pos, 'right', false)}
            </div>
          ))}
        </div>

        {/* Center — logo */}
        <div
          className="absolute flex items-center justify-center"
          style={{
            top: `${metrics.corner}px`,
            left: `${metrics.corner}px`,
            right: `${metrics.corner}px`,
            bottom: `${metrics.corner}px`,
            background: 'radial-gradient(ellipse at center, #1a1f2e 0%, #0f1319 100%)',
          }}
        >
          <div className="text-center">
            <div
              className="text-transparent bg-clip-text bg-gradient-to-br from-yellow-400 via-orange-500 to-red-500 font-black tracking-wider"
              style={{ fontSize: `${Math.max(32, Math.min(60, metrics.innerWidth * 0.08))}px` }}
            >
              POOR<span className="text-white">UP</span>
            </div>
            <div
              className="mt-1 text-gray-600 tracking-widest uppercase"
              style={{ fontSize: `${Math.max(10, Math.min(16, metrics.innerWidth * 0.018))}px` }}
            >
              Goon to Victory
            </div>
          </div>
        </div>

        {/* Token overlay — rendered above all spaces, transitions between pixel coords */}
        <div
          className="absolute inset-0"
          style={{ pointerEvents: 'none', zIndex: 20 }}
        >
          {overlayTokens}
        </div>
      </div>
    </div>
  );
}
