import React from 'react';

/**
 * StatusBadge Component Primitive
 * Displays tactical agent or system execution states with glowing pulse dot.
 */
export function StatusBadge({ status = "IDLE", label }) {
  const statusConfigs = {
    IDLE: {
      dot: "bg-aura-text-muted",
      container: "bg-aura-bg-surface text-aura-text-muted border-aura-border-subtle",
      pulse: false,
    },
    RUNNING: {
      dot: "bg-aura-cyan shadow-aura-cyan",
      container: "bg-aura-cyan-dim text-aura-cyan border-aura-cyan/40",
      pulse: true,
    },
    SUCCESS: {
      dot: "bg-aura-emerald",
      container: "bg-emerald-500/15 text-aura-emerald border-emerald-500/30",
      pulse: false,
    },
    ERROR: {
      dot: "bg-aura-crimson",
      container: "bg-rose-500/15 text-aura-crimson border-rose-500/30",
      pulse: false,
    },
  };

  const current = statusConfigs[status.toUpperCase()] || statusConfigs.IDLE;
  const displayText = label || status;

  return (
    <span className={`inline-flex items-center space-x-2 px-2.5 py-1 rounded-aura-sm border text-xs font-mono font-medium ${current.container}`}>
      <span className={`w-2 h-2 rounded-full ${current.dot} ${current.pulse ? 'animate-pulse' : ''}`} />
      <span>{displayText}</span>
    </span>
  );
}

export default StatusBadge;
