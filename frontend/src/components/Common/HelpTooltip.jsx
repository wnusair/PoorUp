import { useEffect, useId, useRef, useState } from 'react';
import { createPortal } from 'react-dom';


export default function HelpTooltip({ content, label = 'More info' }) {
  const tooltipId = useId();
  const buttonRef = useRef(null);
  const [isHovered, setIsHovered] = useState(false);
  const [isPinned, setIsPinned] = useState(false);
  const [tooltipStyle, setTooltipStyle] = useState(null);
  const isOpen = isHovered || isPinned;

  useEffect(() => {
    if (!isOpen || !buttonRef.current || typeof window === 'undefined') {
      return undefined;
    }

    const updatePosition = () => {
      if (!buttonRef.current) {
        return;
      }

      const rect = buttonRef.current.getBoundingClientRect();
      const tooltipWidth = Math.min(288, window.innerWidth - 16);
      const horizontalMargin = 8;
      const gap = 8;
      const fallbackHeight = 84;
      const measuredHeight = tooltipStyle?.height || fallbackHeight;

      const centeredLeft = rect.left + (rect.width / 2) - (tooltipWidth / 2);
      const left = Math.max(
        horizontalMargin,
        Math.min(centeredLeft, window.innerWidth - tooltipWidth - horizontalMargin),
      );

      const preferredTop = rect.bottom + gap;
      const shouldFlipAbove = preferredTop + measuredHeight > window.innerHeight - horizontalMargin
        && rect.top - gap - measuredHeight >= horizontalMargin;
      const top = shouldFlipAbove
        ? Math.max(horizontalMargin, rect.top - measuredHeight - gap)
        : Math.max(horizontalMargin, preferredTop);

      setTooltipStyle({
        left,
        top,
        width: tooltipWidth,
        height: measuredHeight,
      });
    };

    updatePosition();

    const handleViewportChange = () => {
      updatePosition();
    };

    window.addEventListener('resize', handleViewportChange);
    window.addEventListener('scroll', handleViewportChange, true);

    return () => {
      window.removeEventListener('resize', handleViewportChange);
      window.removeEventListener('scroll', handleViewportChange, true);
    };
  }, [isOpen, tooltipStyle?.height]);

  const tooltip = isOpen && typeof document !== 'undefined'
    ? createPortal(
        <div
          id={tooltipId}
          role="tooltip"
          ref={(node) => {
            if (!node) {
              return;
            }

            const nextHeight = node.getBoundingClientRect().height;
            setTooltipStyle((current) => {
              if (current && Math.abs((current.height || 0) - nextHeight) < 1) {
                return current;
              }

              return {
                ...(current || {}),
                height: nextHeight,
              };
            });
          }}
          className="fixed z-[2147483647] max-w-[calc(100vw-1rem)] rounded-xl border border-gray-700 bg-gray-950 px-3 py-2 text-left text-xs leading-5 text-gray-200 shadow-2xl"
          style={{
            left: tooltipStyle?.left ?? 8,
            top: tooltipStyle?.top ?? 8,
            width: tooltipStyle?.width ?? Math.min(288, typeof window === 'undefined' ? 288 : window.innerWidth - 16),
          }}
        >
          {content}
          <p className="mt-2 text-[11px] text-gray-500">Hover to preview. Click to keep open.</p>
        </div>,
        document.body,
      )
    : null;

  return (
    <span className="relative inline-flex items-center align-middle">
      <button
        ref={buttonRef}
        type="button"
        aria-label={label}
        aria-controls={tooltipId}
        aria-expanded={isOpen}
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
        onFocus={() => setIsHovered(true)}
        onBlur={() => setIsHovered(false)}
        onClick={() => setIsPinned((current) => !current)}
        onKeyDown={(event) => {
          if (event.key === 'Escape') {
            setIsHovered(false);
            setIsPinned(false);
          }
        }}
        className={[
          'inline-flex h-4 w-4 items-center justify-center rounded-full border text-[10px] font-bold transition',
          isOpen
            ? 'border-cyan-400/70 bg-cyan-500/15 text-cyan-100'
            : 'border-gray-600 bg-gray-900 text-gray-300 hover:border-gray-500 hover:text-white',
        ].join(' ')}
      >
        ?
      </button>
      {tooltip}
    </span>
  );
}