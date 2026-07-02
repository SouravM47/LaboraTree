import SystemStatus from "@/components/SystemStatus";

const LABS: { name: string; blurb: string; badge: string }[] = [
  { name: "Signal Lab", blurb: "Any raw mix → one consolidated master workbook.", badge: "flagship" },
  { name: "Paper Lab · Study", blurb: "Plain-language paper card + chat + explain-simpler.", badge: "flagship" },
  { name: "Paper Lab · Experiment", blurb: "Auto-fetch data, reproduce & out-explore the paper.", badge: "flagship" },
  { name: "Data Lab", blurb: "Connectors + transforms with leakage checks.", badge: "core" },
  { name: "Insight Lab", blurb: "EDA + charts with causal-discovery hints.", badge: "core" },
  { name: "Model Lab", blurb: "ML · DL · econometrics · time-series · anomaly.", badge: "core" },
  { name: "Trend Lab", blurb: "Decomposition + causal impact.", badge: "scaffold" },
  { name: "Decision Lab", blurb: "Counterfactual, uncertainty-aware recommendations.", badge: "scaffold" },
  { name: "Ideation Lab", blurb: "Co-Scientist hypothesis tournament.", badge: "scaffold" },
];

export default function Home() {
  return (
    <main className="mx-auto max-w-5xl px-6 py-16">
      <header className="text-center">
        <p className="font-display text-sm uppercase tracking-[0.3em] text-leaf">
          Grow · Innovate · Impact
        </p>
        <h1 className="mt-3 font-display text-5xl font-semibold text-forest">Laboratree</h1>
        <p className="mx-auto mt-4 max-w-2xl text-lg text-muted">
          The trustworthy, agentic, human-in-the-loop research lab — every result provably backed
          by a re-runnable execution.
        </p>
      </header>

      <section className="mt-14">
        <h2 className="font-display text-xl text-forest">System</h2>
        <div className="mt-4">
          <SystemStatus />
        </div>
      </section>

      <section className="mt-14">
        <h2 className="font-display text-xl text-forest">Labs</h2>
        <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {LABS.map((lab) => (
            <div key={lab.name} className="rounded-2xl border border-line bg-white p-5">
              <div className="flex items-center justify-between">
                <h3 className="font-medium text-forest">{lab.name}</h3>
                <span
                  className={`rounded-full px-2 py-0.5 text-xs ${
                    lab.badge === "flagship"
                      ? "bg-leaf/20 text-forest"
                      : lab.badge === "core"
                        ? "bg-sprout/30 text-forest"
                        : "bg-line text-muted"
                  }`}
                >
                  {lab.badge}
                </span>
              </div>
              <p className="mt-2 text-sm text-muted">{lab.blurb}</p>
            </div>
          ))}
        </div>
      </section>

      <footer className="mt-16 border-t border-line pt-6 text-center text-sm text-muted">
        Laboratree · v0.1 foundation
      </footer>
    </main>
  );
}
