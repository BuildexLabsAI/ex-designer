export function Card() {
  return (
    <div className="rounded-sm bg-surface text-[13px] shadow-[0_1px_2px_rgba(22,22,22,0.08)]">
      <p style={{ color: "#5e5e5e" }}>A grey that is almost the muted token.</p>
      <p className="text-teal">Teal text</p>
      <p className="text-destructive">Error text</p>
    </div>
  );
}
