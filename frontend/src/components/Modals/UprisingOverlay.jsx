/**
 * UprisingOverlay — full-screen flash when an uprising occurs.
 * Auto-dismisses after 3 seconds.
 */
import { useEffect } from 'react';
import { useGameStore } from '../../hooks/useGameState';

export default function UprisingOverlay() {
  const { uprisingEvent, clearUprising } = useGameStore();

  useEffect(() => {
    if (!uprisingEvent) return;
    const t = setTimeout(clearUprising, 3000);
    return () => clearTimeout(t);
  }, [uprisingEvent, clearUprising]);

  if (!uprisingEvent) return null;

  const incidentType = uprisingEvent.incident_type || 'uprising';
  const title = incidentType === 'revolution' ? 'Revolution' : 'Uprising';
  const headline = uprisingEvent.property_name || uprisingEvent.region?.toUpperCase() || 'Civil Unrest';

  return (
    <div
      className="fixed inset-0 z-[100] flex flex-col items-center justify-center
                 bg-red-900/60 backdrop-blur-sm pointer-events-none uprising-flash"
    >
      <div className="text-center">
        <p className="text-red-300 text-sm font-bold uppercase tracking-widest mb-2">
          {title}
        </p>
        <h1 className="text-4xl md:text-6xl font-extrabold text-white drop-shadow-lg">
          {headline}
        </h1>
        <p className="text-red-200 text-lg mt-3 font-semibold">
          {uprisingEvent.description || (incidentType === 'revolution' ? 'Union control is spreading through the territory.' : 'Local unrest just escalated.')}
        </p>
        {uprisingEvent.affected_properties?.length > 0 && (
          <p className="text-red-300 text-sm mt-2">
            Affected: {uprisingEvent.affected_properties.join(', ')}
          </p>
        )}
      </div>
    </div>
  );
}
