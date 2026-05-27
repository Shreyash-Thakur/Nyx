// ─── Landing — app entry ───────────────────────────────────────────

function LandingApp() {
  return (
    <>
      <LandingNav/>
      <Hero/>
      <Numbers/>
      <Ribbon/>
      <ProductBreathing/>
      <Method/>
      <Trust/>
      <Closing/>
      <Footer/>
    </>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<LandingApp/>);
