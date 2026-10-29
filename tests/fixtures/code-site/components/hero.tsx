// Traps for the token scan: a fragment link and an SVG gradient id that look like hex colours, an asset whose
// name holds a token's hex code, an arbitrary Tailwind value, a palette class and a hex in a style object.
export function Hero() {
  return (
    <section className="bg-background text-foreground md:py-24">
      <h1 className="display text-foreground">Alpha Studio</h1>
      <p className="text-muted-foreground">We make calm software.</p>
      <a className="rounded-lg bg-accent text-accent-foreground hover:bg-accent/90" href="#cafe">Start</a>
      <span className="bg-[#1d4ed8] text-white">New</span>
      <div style={{ color: "#0f766e" }}>Teal note</div>
      <svg aria-hidden="true">
        <rect width="8" height="8" fill="url(#bead42)" />
      </svg>
      <img src="/assets/stripe-0f766e.svg" alt="" />
    </section>
  );
}
