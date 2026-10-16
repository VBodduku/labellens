export function Skeleton({ className = "" }: { className?: string }) {
  return <div aria-hidden="true" className={`animate-pulse rounded-card bg-surface-2 motion-reduce:animate-none ${className}`} />;
}
