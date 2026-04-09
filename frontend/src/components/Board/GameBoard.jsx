import { useEffect, useMemo, useRef, useState } from 'react';
import BoardSpace from './BoardSpace';
import CenterLogDock from '../Log/CenterLogDock';
import { BOARD_SPACES, needsDarkText } from '../../utils/constants';
import { useGameStore } from '../../hooks/useGameState';
import hammerAndSickle from '../../assets/white_hammer_and_sickle.png';

/**
 * Board layout — sparse board positions with retired top-row spaces removed.
 *
 * Corners:
 *   pos  0 = START       → top-left
 *   pos 11 = JAIL        → bottom-left
 *   pos 20 = FREE SPACE  → bottom-right
 *   pos 30 = GO TO JAIL  → top-right
 *
 * Visual layout:
 *   Top row    (L→R): 0, sparse [47..31], 30   — weighted widths keep property cards readable
 *   Right col  (T→B): sparse live spaces from 30 toward 20
 *   Bottom row (L→R): 11, [12..19], 20
 *   Left col   (T→B): sparse live spaces from 0 toward 11
 */

const spaceByPos = Object.fromEntries(BOARD_SPACES.map((s) => [s.position, s]));

const CORNER_POSITIONS = new Set([0, 11, 20, 30]);

// Top row: L→R, corners 0 (TL) and 30 (TR), inner = 47 down to 31
const topRow = [0, 47, 40, 39, 38, 37, 36, 34, 32, 31, 30];
const topRowInner = topRow.slice(1, -1);
// Right col inner: T→B, surviving spaces between 30 and 20
const rightColInner = [27, 26, 25, 24, 23, 22];
// Bottom row: L→R, corners 11 (BL) and 20 (BR), inner = 12 up to 19
const bottomRow = [11, 12, 13, 14, 15, 16, 17, 18, 19, 20];
const bottomRowInner = bottomRow.slice(1, -1);
// Left col inner: T→B, surviving spaces between 0 and 11
const leftColInner = [2, 4, 5, 6, 9, 10];
const renderOrder = [...topRow, ...rightColInner, ...bottomRow, ...leftColInner];

const BOARD_INSET = 10;

const CORNER_REFERENCE = 90;
const TOP_EDGE_REFERENCE = 58;
const SIDE_EDGE_REFERENCE = 54;

const LEFT_INNER = leftColInner.length;
const RIGHT_INNER = rightColInner.length;

const innerW = topRowInner.length * TOP_EDGE_REFERENCE;
const innerH = LEFT_INNER * SIDE_EDGE_REFERENCE;
const totalW = CORNER_REFERENCE + innerW + CORNER_REFERENCE;
const totalH = CORNER_REFERENCE + innerH + CORNER_REFERENCE;

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function getTrackWeight(position) {
  const type = spaceByPos[position]?.type;

  switch (type) {
    case 'property':
      return 1.26;
    case 'transit':
      return 0.7;
    case 'chance':
    case 'community_chest':
    case 'tax':
      return 0.5;
    default:
      return 1;
  }
}

function distributeWeightedWidths(positions, totalWidth) {
  const weights = positions.map((position) => getTrackWeight(position));
  const totalWeight = weights.reduce((sum, weight) => sum + weight, 0) || 1;
  const widths = positions.map((_, index) => totalWidth * (weights[index] / totalWeight));

  if (!widths.length) {
    return widths;
  }

  const usedWidth = widths.slice(0, -1).reduce((sum, width) => sum + width, 0);
  widths[widths.length - 1] = Math.max(1, totalWidth - usedWidth);
  return widths;
}

function buildBoardMetrics(containerWidth, containerHeight) {
  const availableWidth = Math.max(320, containerWidth - (BOARD_INSET * 2));
  const availableHeight = Math.max(260, containerHeight - (BOARD_INSET * 2));
  const preferredCorner = Math.min(
    availableWidth / (totalW / CORNER_REFERENCE),
    availableHeight / (totalH / CORNER_REFERENCE),
  );
  const desiredCorner = Math.max(
    preferredCorner * 1.12,
    Math.min(availableHeight * 0.17, availableWidth * 0.105),
  );
  const maxCorner = Math.max(52, Math.min(126, (availableHeight / 2) - 24, (availableWidth / 2) - 40));
  const corner = clamp(desiredCorner, 52, maxCorner);
  const boardWidth = availableWidth;
  const boardHeight = availableHeight;
  const responsiveInnerWidth = Math.max(1, boardWidth - (corner * 2));
  const responsiveInnerHeight = Math.max(1, boardHeight - (corner * 2));
  const topCellWidths = distributeWeightedWidths(topRowInner, responsiveInnerWidth);
  const bottomCellWidths = distributeWeightedWidths(bottomRowInner, responsiveInnerWidth);
  const leftCellH = responsiveInnerHeight / LEFT_INNER;
  const rightCellH = responsiveInnerHeight / RIGHT_INNER;
  const narrowestHorizontalCell = Math.min(
    ...topCellWidths,
    ...bottomCellWidths,
  );
  const tokenSize = clamp(
    Math.min(corner * 0.38, narrowestHorizontalCell * 0.42, Math.min(leftCellH, rightCellH) * 0.42),
    20,
    34,
  );

  return {
    inset: BOARD_INSET,
    boardWidth,
    boardHeight,
    corner,
    innerWidth: responsiveInnerWidth,
    innerHeight: responsiveInnerHeight,
    topCellWidths,
    bottomCellWidths,
    leftCellH,
    rightCellH,
    tokenSize,
  };
}

function buildSpaceRects(metrics) {
  const rects = {
    0: { left: 0, top: 0, width: metrics.corner, height: metrics.corner, orientation: 'top' },
    11: { left: 0, top: metrics.boardHeight - metrics.corner, width: metrics.corner, height: metrics.corner, orientation: 'bottom' },
    20: { left: metrics.boardWidth - metrics.corner, top: metrics.boardHeight - metrics.corner, width: metrics.corner, height: metrics.corner, orientation: 'bottom' },
    30: { left: metrics.boardWidth - metrics.corner, top: 0, width: metrics.corner, height: metrics.corner, orientation: 'top' },
  };

  let topOffset = metrics.corner;
  topRowInner.forEach((position, index) => {
    const width = metrics.topCellWidths[index];
    rects[position] = {
      left: topOffset,
      top: 0,
      width,
      height: metrics.corner,
      orientation: 'top',
    };
    topOffset += width;
  });

  let bottomOffset = metrics.corner;
  bottomRowInner.forEach((position, index) => {
    const width = metrics.bottomCellWidths[index];
    rects[position] = {
      left: bottomOffset,
      top: metrics.boardHeight - metrics.corner,
      width,
      height: metrics.corner,
      orientation: 'bottom',
    };
    bottomOffset += width;
  });

  leftColInner.forEach((position, index) => {
    rects[position] = {
      left: 0,
      top: metrics.corner + (index * metrics.leftCellH),
      width: metrics.corner,
      height: metrics.leftCellH,
      orientation: 'left',
    };
  });

  rightColInner.forEach((position, index) => {
    rects[position] = {
      left: metrics.boardWidth - metrics.corner,
      top: metrics.corner + (index * metrics.rightCellH),
      width: metrics.corner,
      height: metrics.rightCellH,
      orientation: 'right',
    };
  });

  return rects;
}

function getTokenAnchor(position, rect, tokenSize) {
  if (!rect) {
    return { x: 0, y: 0, stackMode: 'diagonal' };
  }

  const margin = Math.max(4, tokenSize * 0.2);
  const radius = tokenSize / 2;

  if (position === 0 || position === 11) {
    return {
      x: rect.left + margin + radius,
      y: rect.top + margin + radius,
      stackMode: 'diagonal',
    };
  }

  if (position === 20 || position === 30) {
    return {
      x: rect.left + rect.width - margin - radius,
      y: rect.top + margin + radius,
      stackMode: 'diagonal',
    };
  }

  switch (rect.orientation) {
    case 'top':
    case 'bottom':
      return {
        x: rect.left + (rect.width / 2),
        y: rect.top + margin + radius,
        stackMode: 'horizontal',
      };
    case 'left':
      return {
        x: rect.left + margin + radius,
        y: rect.top + margin + radius,
        stackMode: 'vertical',
      };
    case 'right':
      return {
        x: rect.left + rect.width - margin - radius,
        y: rect.top + margin + radius,
        stackMode: 'vertical',
      };
    default:
      return {
        x: rect.left + (rect.width / 2),
        y: rect.top + (rect.height / 2),
        stackMode: 'diagonal',
      };
  }
}

function buildPlotClusterOverlays(properties, spaceRects) {
  const clusters = {};

  Object.values(properties || {}).forEach((property) => {
    if (!property?.social_plot_seized || !property?.social_plot_cluster_id) {
      return;
    }
    const rect = spaceRects[property.board_position];
    if (!rect) {
      return;
    }
    const clusterId = property.social_plot_cluster_id;
    if (!clusters[clusterId]) {
      clusters[clusterId] = [];
    }
    clusters[clusterId].push({ property, rect });
  });

  return Object.entries(clusters)
    .map(([clusterId, entries]) => {
      if (entries.length < 2) {
        return null;
      }

      const bounds = entries.reduce(
        (current, entry) => ({
          left: Math.min(current.left, entry.rect.left),
          top: Math.min(current.top, entry.rect.top),
          right: Math.max(current.right, entry.rect.left + entry.rect.width),
          bottom: Math.max(current.bottom, entry.rect.top + entry.rect.height),
        }),
        { left: Number.POSITIVE_INFINITY, top: Number.POSITIVE_INFINITY, right: Number.NEGATIVE_INFINITY, bottom: Number.NEGATIVE_INFINITY },
      );

      const orientation = entries[0]?.rect?.orientation || 'top';
      const width = Math.max(0, bounds.right - bounds.left);
      const height = Math.max(0, bounds.bottom - bounds.top);
      const trackLength = orientation === 'left' || orientation === 'right' ? height : width;

      return {
        clusterId,
        left: bounds.left,
        top: bounds.top,
        width,
        height,
        orientation,
        trackLength,
        narrow: trackLength < 176 || Math.min(width, height) < 54,
      };
    })
    .filter(Boolean);
}

function buildPlotClusterSizes(properties) {
  return Object.values(properties || {}).reduce((counts, property) => {
    if (!property?.social_plot_seized || !property?.social_plot_cluster_id) {
      return counts;
    }

    const clusterId = property.social_plot_cluster_id;
    counts[clusterId] = (counts[clusterId] || 0) + 1;
    return counts;
  }, {});
}

export default function GameBoard({ players = [], properties = {}, onSpaceClick }) {
  const containerRef = useRef(null);
  const [boardSize, setBoardSize] = useState({
    width: totalW + (BOARD_INSET * 2),
    height: totalH + (BOARD_INSET * 2),
  });
  const { playerAnimPositions, movingPlayerId } = useGameStore();

  const metrics = useMemo(
    () => buildBoardMetrics(boardSize.width, boardSize.height),
    [boardSize.height, boardSize.width],
  );
  const spaceRects = useMemo(() => buildSpaceRects(metrics), [metrics]);
  const plotClusterSizes = useMemo(() => buildPlotClusterSizes(properties), [properties]);
  const plotClusterOverlays = useMemo(() => buildPlotClusterOverlays(properties, spaceRects), [properties, spaceRects]);

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
          ...liveProperty,
          type: liveProperty.property_type || space.type,
          groupColor: liveProperty.group_color ?? space.groupColor ?? null,
          basePrice: liveProperty.base_price ?? space.basePrice ?? null,
          dev_level: liveProperty.dev_level ?? liveProperty.development_level ?? 0,
          development_level: liveProperty.development_level ?? liveProperty.dev_level ?? 0,
          social_plot_cluster_size: liveProperty.social_plot_cluster_id
            ? plotClusterSizes[liveProperty.social_plot_cluster_id] ?? 0
            : 0,
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
      const centeredOffset = offsetIndex - ((siblings.length - 1) / 2);
      const rect = spaceRects[pos];
      const { x, y, stackMode } = getTokenAnchor(pos, rect, metrics.tokenSize);
      const stackStep = Math.max(4, metrics.tokenSize * 0.28);
      const offsetX = stackMode === 'horizontal'
        ? centeredOffset * stackStep
        : stackMode === 'diagonal'
          ? centeredOffset * stackStep * 0.7
          : 0;
      const offsetY = stackMode === 'vertical'
        ? centeredOffset * stackStep
        : stackMode === 'diagonal'
          ? centeredOffset * stackStep * 0.55
          : 0;
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
            left: `${x + offsetX - metrics.tokenSize / 2}px`,
            top: `${y + offsetY - metrics.tokenSize / 2}px`,
            // Smooth glide between spaces — matches the STEP_MS in useSocket
            transition: 'left 0.13s ease-out, top 0.13s ease-out, box-shadow 0.1s, transform 0.1s',
            backgroundColor: color,
            color: textColor,
            borderRadius: '50%',
            border: isMoving ? '2.5px solid #fff' : '2px solid rgba(255,255,255,0.55)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: `${Math.max(10, metrics.tokenSize * 0.36)}px`,
            fontWeight: 'bold',
            userSelect: 'none',
            zIndex: 24 + offsetIndex,
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
        {renderOrder.map((pos) => {
          const rect = spaceRects[pos];
          if (!rect) {
            return null;
          }

          return (
            <div
              key={pos}
              style={{
                position: 'absolute',
                left: `${rect.left}px`,
                top: `${rect.top}px`,
                width: `${rect.width}px`,
                height: `${rect.height}px`,
              }}
            >
              {renderSpace(pos, rect.orientation, CORNER_POSITIONS.has(pos))}
            </div>
          );
        })}

        {plotClusterOverlays.map((overlay) => {
          const vertical = overlay.orientation === 'left' || overlay.orientation === 'right';
          return (
            <div
              key={overlay.clusterId}
              className="pointer-events-none absolute overflow-hidden"
              style={{
                left: `${overlay.left + 4}px`,
                top: `${overlay.top + 4}px`,
                width: `${Math.max(0, overlay.width - 8)}px`,
                height: `${Math.max(0, overlay.height - 8)}px`,
                zIndex: 13,
              }}
            >
              <div
                className="absolute left-1/2 top-1/2 flex items-center justify-center gap-3 opacity-95"
                style={{
                  transform: vertical ? 'translate(-50%, -50%) rotate(90deg)' : 'translate(-50%, -50%)',
                }}
              >
                <img
                  src={hammerAndSickle}
                  alt=""
                  className="h-6 w-6 object-contain opacity-95 drop-shadow-[0_0_10px_rgba(255,255,255,0.25)]"
                />
                <span
                  className={[
                    'whitespace-nowrap font-black uppercase text-white [text-shadow:0_0_10px_rgba(255,255,255,0.18)]',
                    overlay.narrow ? 'text-[0.48rem] tracking-[0.22em]' : 'text-[0.6rem] tracking-[0.34em]',
                  ].join(' ')}
                >
                  Property Of The People
                </span>
              </div>
            </div>
          );
        })}

        {/* Center — logo */}
        <div
          className="absolute overflow-hidden rounded-[2rem] border border-slate-800/70 shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]"
          style={{
            top: `${metrics.corner}px`,
            left: `${metrics.corner}px`,
            right: `${metrics.corner}px`,
            bottom: `${metrics.corner}px`,
            background: 'radial-gradient(ellipse at center, #1a1f2e 0%, #0f1319 100%)',
          }}
        >
          <div className="absolute inset-0 flex items-center justify-center pb-[clamp(6rem,16vh,8.5rem)]">
            <div className="text-center">
            <div
              className="text-transparent bg-clip-text bg-gradient-to-br from-yellow-400 via-orange-500 to-red-500 font-black tracking-wider"
              style={{ fontSize: `${Math.max(24, Math.min(46, Math.min(metrics.innerWidth, metrics.innerHeight) * 0.095))}px` }}
            >
              POOR<span className="text-white">UP</span>
            </div>
            <div
              className="mt-1 text-gray-600 tracking-widest uppercase"
              style={{ fontSize: `${Math.max(9, Math.min(13, Math.min(metrics.innerWidth, metrics.innerHeight) * 0.024))}px` }}
            >
              Goon to Victory
            </div>
            </div>
          </div>

          <CenterLogDock />
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
