// The old footer blue was #0000ff; it is gone.
export function Footer() {
  return (
    <footer className="border-t border-border bg-surface font-mono" style={{ borderColor: "rgb(15, 118, 110)" }}>
      <p className="text-gray-500">&#169; 2026 Alpha Studio</p>
      <p style={{ fontFamily: "Comic Neue, cursive" }}>Signed</p>
    </footer>
  );
}
