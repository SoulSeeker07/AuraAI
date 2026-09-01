import React from 'react';

/**
 * NeonButton Component Primitive
 * High-tech button with glowing neon hover and active feedback.
 */
export function NeonButton({ children, variant = "primary", size = "md", onClick, disabled = false, className = "" }) {
  const variantStyles = {
    primary: "bg-aura-cyan-dim text-aura-cyan border-aura-cyan/40 hover:bg-aura-cyan/25 hover:border-aura-cyan shadow-aura-cyan/20 active:scale-95",
    blue: "bg-aura-blue/15 text-aura-blue border-aura-blue/40 hover:bg-aura-blue/25 hover:border-aura-blue shadow-aura-blue/20 active:scale-95",
    danger: "bg-aura-crimson/15 text-aura-crimson border-aura-crimson/40 hover:bg-aura-crimson/25 hover:border-aura-crimson active:scale-95",
    ghost: "bg-aura-bg-surface text-aura-text-secondary border-aura-border-subtle hover:border-aura-border-active hover:text-aura-text-primary active:scale-95",
  };

  const sizeStyles = {
    sm: "px-2.5 py-1 text-xs",
    md: "px-4 py-2 text-sm",
    lg: "px-5 py-2.5 text-base",
  };

  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`inline-flex items-center justify-center font-semibold rounded-aura-sm border transition-all duration-150 cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed ${variantStyles[variant] || variantStyles.primary} ${sizeStyles[size] || sizeStyles.md} ${className}`}
    >
      {children}
    </button>
  );
}

export default NeonButton;
