export function SkeletonGrid({ count = 6 }: { count?: number }) {
  return (
    <div className="grid" aria-hidden="true">
      {Array.from({ length: count }).map((_, i) => (
        <div className="skeleton" key={i}>
          <div className="sk-thumb" />
          <div className="sk-line" />
          <div className="sk-line short" />
        </div>
      ))}
    </div>
  );
}
