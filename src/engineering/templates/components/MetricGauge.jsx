import React from 'react';

/**
 * MetricGauge Component Primitive
 * High-tech telemetry card displaying hardware or agent performance gauges.
 */
export function MetricGauge({ label, value, subtext, color = "cyan", percent = 0 }) {
  const colorMap = {
    cyan: "text-aura-cyan bg-aura-cyan",
    blue: "text-aura-blue bg-aura-blue",
    emerald: "text-aura-emerald bg-aura-emerald",
    amber: "text-aura-amber bg-aura-amber",
    crimson: "text-aura-crimson bg-aura-crimson",
  };

  const activeColor = colorMap[color] || colorMap.cyan;
  const textColor = activeColor.split(" ")[0];
  const barColor = activeColor.split(" ")[1];

  return (
    <div className="bg-aura-bg-surface border border-aura-border-subtle rounded-aura-md p-4 flex flex-col justify-between">
      <div className="flex justify-between items-start">
        <span className="text-xs font-mono font-medium text-aura-text-muted tracking-wider uppercase">{label}</span>
        <span className={`text-lg font-mono font-bold ${textColor}`}>{value}</span>
      </div>
      <div className="mt-3">
        <div className="w-full bg-aura-bg-deep rounded-full h-1.5 overflow-hidden">
          <div
            className={`h-full ${barColor} transition-all duration-300 rounded-full`}
            style={{ width: `${Math.max(0, Math.min(100, percent))}%` }}
          />
        </div>
        {subtext && <p className="text-[10px] text-aura-text-muted mt-1.5 font-mono">{subtext}</p>}
      </div>
    </div>
  );
}

export default MetricGauge;
