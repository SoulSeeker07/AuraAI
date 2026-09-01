import React from 'react';

/**
 * CyberCard Component Primitive
 * Glassmorphic container with sci-fi chamfered styling and accent borders.
 */
export function CyberCard({ title, subtitle, children, badgeText, badgeColor = "cyan" }) {
  const badgeColorMap = {
    cyan: "bg-aura-cyan-dim text-aura-cyan border-aura-cyan/30",
    emerald: "bg-emerald-500/15 text-aura-emerald border-emerald-500/30",
    amber: "bg-amber-500/15 text-aura-amber border-amber-500/30",
    crimson: "bg-rose-500/15 text-aura-crimson border-rose-500/30",
  };

  return (
    <div className="bg-aura-bg-card border border-aura-border-subtle hover:border-aura-border-active rounded-aura-md p-5 backdrop-blur-md transition-all duration-200 shadow-aura-card">
      <div className="flex items-center justify-between mb-3">
        <div>
          {title && <h3 className="text-base font-bold text-aura-text-primary tracking-wide">{title}</h3>}
          {subtitle && <p className="text-xs text-aura-text-muted mt-0.5">{subtitle}</p>}
        </div>
        {badgeText && (
          <span className={`px-2.5 py-1 text-xs font-mono font-semibold rounded-aura-sm border ${badgeColorMap[badgeColor] || badgeColorMap.cyan}`}>
            {badgeText}
          </span>
        )}
      </div>
      <div className="text-sm text-aura-text-secondary">
        {children}
      </div>
    </div>
  );
}

export default CyberCard;
