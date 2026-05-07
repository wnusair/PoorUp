import { useGameStore } from '../../hooks/useGameState';
import { BOARD_SPACE_SHORT_NAMES, SPACE_ICONS, needsDarkText } from '../../utils/constants';
import { getBoardDevelopmentDisplay, getDevelopmentLabel } from '../../utils/propertyEconomy';
import hammerAndSickle from '../../assets/white_hammer_and_sickle.png';

function ControlBanner({ plotSeized, unionized }) {
  if (plotSeized || !unionized) {
    return null;
  }

  return (
    <div
      className={[
        'absolute inset-x-0 top-0 z-20 border-b px-1 py-0.5 text-center text-[0.4rem] font-black uppercase tracking-[0.24em] text-white pointer-events-none',
        plotSeized
          ? 'border-red-100/20 bg-gradient-to-r from-red-700 via-red-600 to-red-800'
          : 'border-cyan-100/20 bg-gradient-to-r from-cyan-700 via-sky-700 to-cyan-800',
      ].join(' ')}
    >
      {plotSeized ? 'People\'s Control' : 'Union Control'}
    </div>
  );
}

function SocialMarker({ space }) {
  const incidentType = space.social_incident_type;
  const unionized = Boolean(space.social_unionized);
  const plotSeized = Boolean(space.social_plot_seized);

  if (plotSeized || (!incidentType && !unionized)) {
    return null;
  }

  const incidentPalette = {
    protest: 'bg-amber-400 text-black',
    strike: 'bg-orange-500 text-white',
    uprising: 'bg-red-500 text-white',
    revolution: 'bg-rose-700 text-white',
  };

  return (
    <div className="absolute right-1 top-1 z-10 flex flex-col items-end gap-1 pointer-events-none">
      {incidentType && (
        <span
          className={[
            'rounded-full px-1.5 py-0.5 text-[0.45rem] font-bold uppercase tracking-[0.18em]',
            incidentPalette[incidentType] || 'bg-slate-600 text-white',
          ].join(' ')}
          title={incidentType}
        >
          {incidentType === 'uprising' ? 'CRK' : incidentType === 'revolution' ? 'REV' : incidentType[0]}
        </span>
      )}
      {unionized && (
        <span
          className="rounded-full bg-cyan-300 px-1.5 py-0.5 text-[0.42rem] font-bold uppercase tracking-[0.16em] text-slate-950"
          title="Unionized property"
        >
          U
        </span>
      )}
    </div>
  );
}

function DevelopmentMarker({ level, orientation, incidentType, unionized, economy }) {
  if (unionized || incidentType === 'revolution') {
    return null;
  }

  if (incidentType === 'strike' || incidentType === 'uprising') {
    return (
      <div
        className="absolute left-1 right-1 rounded-full border border-red-100/20 bg-gradient-to-r from-red-700 via-red-500 to-red-700 shadow-red-950/40"
        style={{
          bottom: orientation === 'left' || orientation === 'right' ? '3px' : '4px',
          height: orientation === 'left' || orientation === 'right' ? '6px' : '7px',
        }}
        title={incidentType === 'uprising' ? 'Uprising damage and strike shutdown' : 'Strike shutdown'}
      />
    );
  }

  if (!level || level <= 0) {
    return null;
  }

  const isVertical = orientation === 'left' || orientation === 'right';
  const { houses, hasHotel, extraHouses } = getBoardDevelopmentDisplay(level, economy);

  return (
    <div
      className="absolute left-1/2 -translate-x-1/2 flex items-center justify-center gap-0.5"
      style={{
        bottom: isVertical ? '2px' : '3px',
        maxWidth: 'calc(100% - 6px)',
      }}
      title={getDevelopmentLabel(level, economy)}
    >
      {Array.from({ length: houses }).map((_, index) => (
        <span
          key={index}
          className="rounded-sm border border-black/30 bg-emerald-400"
          style={{
            width: isVertical ? '4px' : '5px',
            height: isVertical ? '4px' : '5px',
            boxShadow: '0 0 0 1px rgba(0,0,0,0.15)',
          }}
        />
      ))}
      {hasHotel && (
        <span
          className="rounded-sm border border-black/30 bg-amber-400 text-[0.35rem] font-bold leading-none text-black"
          style={{
            minWidth: isVertical ? '7px' : '8px',
            height: isVertical ? '6px' : '7px',
            padding: '0 1px',
          }}
        >
          H
        </span>
      )}
      {!hasHotel && extraHouses > 0 && (
        <span
          className="rounded-full border border-black/30 bg-amber-400 px-1 text-[0.38rem] font-bold leading-none text-black"
          style={{ minHeight: isVertical ? '7px' : '8px' }}
        >
          +{extraHouses}
        </span>
      )}
    </div>
  );
}

function SpaceLabel({ space, owner, corporateOwner, orientation, economy }) {
  const isVertical = orientation === 'left' || orientation === 'right';
  const icon = SPACE_ICONS[space.type];
  const displayName = BOARD_SPACE_SHORT_NAMES[space.position] || space.name;
  const developmentLevel = Number(space.dev_level ?? space.development_level ?? 0) || 0;
  const propertyNameStyle = {
    fontSize: isVertical ? 'clamp(0.56rem, 0.78vw, 0.72rem)' : 'clamp(0.66rem, 0.96vw, 0.84rem)',
    color: '#e5e7eb',
    maxWidth: '100%',
    wordBreak: 'break-word',
    display: '-webkit-box',
    WebkitBoxOrient: 'vertical',
    WebkitLineClamp: isVertical ? 3 : 2,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
  };

  if (space.type === 'property' || space.type === 'transit') {
    const unionized = Boolean(space.social_unionized);
    const incidentType = space.social_incident_type;
    const plotSeized = Boolean(space.social_plot_seized);
    const seizedClusterSize = Number(space.social_plot_cluster_size ?? 0) || 0;
    const isClusterSeizure = seizedClusterSize > 1;
    const corporateSymbol = corporateOwner?.stock_symbol || corporateOwner?.asset_key || '';

    if (plotSeized) {
      return (
        <div className="relative flex h-full w-full items-center justify-center overflow-hidden bg-[#f40d0d] text-white">
          <div className="absolute inset-0 bg-[linear-gradient(135deg,rgba(255,255,255,0.08)_0%,transparent_32%,transparent_68%,rgba(255,255,255,0.06)_100%)] opacity-80" />
          <div className="relative flex h-full w-full items-center justify-center">
            {!isClusterSeizure ? (
              <img
                src={hammerAndSickle}
                alt=""
                className="pointer-events-none h-7 w-7 object-contain opacity-95 drop-shadow-[0_0_12px_rgba(255,255,255,0.28)]"
              />
            ) : null}
          </div>
        </div>
      );
    }

    return (
      <div className="flex flex-col h-full w-full overflow-hidden">
        {/* Group color bar */}
        {space.groupColor && (
          <div
            className="flex-shrink-0"
            style={{
              backgroundColor: space.groupColor,
              height: isVertical ? '7px' : '10px',
              width: '100%',
            }}
          />
        )}
        <div className="flex-1 flex flex-col items-center justify-center gap-1 overflow-hidden px-1 py-2">
          {space.type === 'transit' && icon && (
            <span style={{ fontSize: isVertical ? '0.95rem' : '1.08rem', lineHeight: 1 }}>{icon}</span>
          )}
          <span
            className="text-center leading-tight font-semibold"
            style={propertyNameStyle}
          >
            {displayName}
          </span>
          {owner && !unionized && incidentType !== 'revolution' && (
            <div
              className="flex items-center justify-center rounded-sm border border-white/20 shadow-sm"
              style={{
                minWidth: isVertical ? '14px' : '16px',
                height: isVertical ? '14px' : '16px',
                backgroundColor: owner.color_hex || '#555',
                color: needsDarkText(owner.color_hex || '#555') ? '#111' : '#fff',
                fontSize: isVertical ? '0.46rem' : '0.5rem',
                fontWeight: 700,
              }}
              title={`Owned by ${owner.username}`}
            >
              {owner.username?.[0]?.toUpperCase() || '?'}
            </div>
          )}
          {!owner && corporateOwner && !unionized && incidentType !== 'revolution' && (
            <div
              className="flex items-center justify-center rounded-sm border border-white/30 text-[0.42rem] font-bold shadow-sm"
              style={{
                minWidth: isVertical ? '28px' : '34px',
                height: isVertical ? '14px' : '16px',
                letterSpacing: '0',
                backgroundColor: corporateOwner.color_hex || '#06b6d4',
                color: needsDarkText(corporateOwner.color_hex || '#06b6d4') ? '#111' : '#fff',
              }}
              title={`Owned by ${corporateOwner.name || corporateSymbol || 'Corporation'} · Rent ${space.corporate_rent != null ? `$${Number(space.corporate_rent).toFixed(0)}` : ''}`}
            >
              {corporateSymbol ? corporateSymbol.slice(0, 4).toUpperCase() : (corporateOwner.name || 'CORP').slice(0, 4).toUpperCase()}
            </div>
          )}
          {!owner && space.social_unionized && (
            <div
              className="flex items-center justify-center rounded-sm border border-white/20 bg-cyan-300 text-[0.42rem] font-bold text-slate-950 shadow-sm"
              style={{
                minWidth: isVertical ? '14px' : '16px',
                height: isVertical ? '14px' : '16px',
              }}
              title="Proletariat Union"
            >
              U
            </div>
          )}
          {(space.corporate_rent != null || space.basePrice) && (
            <span
              title={space.corporate_rent != null ? `Rent $${Number(space.corporate_rent).toFixed(0)} · Buy $${Number(space.corporate_listing_price || space.basePrice).toFixed(0)}` : `Price $${space.basePrice}`}
              style={{ fontSize: isVertical ? '0.52rem' : '0.58rem', color: space.corporate_rent != null ? (corporateOwner?.color_hex || '#06b6d4') : '#9ca3af', fontWeight: 600 }}
            >
              {space.corporate_rent != null
                ? `R$${Number(space.corporate_rent).toFixed(0)}`
                : `$${space.basePrice}`}
            </span>
          )}
        </div>
        {space.type === 'property' && (
          <DevelopmentMarker
            level={developmentLevel}
            orientation={orientation}
            incidentType={incidentType}
            unionized={unionized}
            economy={economy}
          />
        )}
      </div>
    );
  }

  // Special spaces (start, jail, free, go_to_jail, chance, community_chest, tax)
  return (
    <div className="flex h-full w-full flex-col items-center justify-center gap-1 overflow-hidden px-1 py-1.5">
      {icon && (
        <span
          className="text-gray-200"
          style={{ fontSize: isVertical ? '1rem' : '1.14rem', lineHeight: 1 }}
        >
          {icon}
        </span>
      )}
      <span
        className="text-center font-semibold leading-tight"
        style={{
          fontSize: isVertical ? 'clamp(0.54rem, 0.76vw, 0.7rem)' : 'clamp(0.68rem, 0.98vw, 0.86rem)',
          color: '#e5e7eb',
          wordBreak: 'break-word',
          maxWidth: '100%',
          display: '-webkit-box',
          WebkitBoxOrient: 'vertical',
          WebkitLineClamp: isVertical ? 3 : 2,
          overflow: 'hidden',
        }}
      >
        {displayName}
      </span>
    </div>
  );
}

export default function BoardSpace({
  space,
  owner = null,
  corporateOwner = null,
  orientation = 'bottom',
  isCorner = false,
  onClick,
}) {
  if (!space) return null;
  const economy = useGameStore((state) => state.economy);

  // Corner tiles are square and larger, edge tiles are thinner
  const cornerClass = 'w-full h-full';
  const edgeClass = 'w-full h-full';

  const bgColors = {
    start: '#1a3a1a',
    jail: '#1a1a3a',
    free: '#1a2a1a',
    go_to_jail: '#3a1a1a',
    chance: '#2a2a1a',
    community_chest: '#1a2a3a',
    tax: '#3a2a1a',
    property: '#111827',
    transit: '#111827',
  };

  const bg = bgColors[space.type] || '#111827';
  const plotSeized = Boolean(space.social_plot_seized);
  const unionized = Boolean(space.social_unionized);
  const revolutionary = space.social_incident_type === 'revolution' || unionized;

  return (
    <div
      className={[
        'relative border border-gray-700 cursor-pointer hover:border-gray-400 transition-colors overflow-hidden',
        plotSeized ? 'border-red-200/80 hover:border-red-100' : revolutionary ? 'bg-red-950/70 border-red-500/70 hover:border-rose-500' : '',
        isCorner ? cornerClass : edgeClass,
      ].join(' ')}
      style={{ background: plotSeized ? '#f40d0d' : revolutionary ? '#450a0a' : bg }}
      onClick={() => onClick && onClick(space)}
      title={`${space.name}${space.basePrice ? ` — $${space.basePrice}` : ''}`}
    >
      <ControlBanner plotSeized={plotSeized} unionized={unionized && !plotSeized} />
      <SocialMarker space={space} />
      <SpaceLabel space={space} owner={owner} corporateOwner={corporateOwner} orientation={orientation} economy={economy} />
    </div>
  );
}
