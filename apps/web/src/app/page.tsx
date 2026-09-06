export default function Home() {
  return (
    <main className="mx-auto flex min-h-screen max-w-5xl flex-col px-6 py-10 sm:px-12">
      <header className="flex items-center justify-between border-b border-emerald-950/15 pb-6">
        <span className="text-lg font-semibold tracking-tight">AI Career Match<span className="text-emerald-600">.</span></span>
        <span className="rounded-full border border-emerald-950/20 px-3 py-1 text-xs">Project preview</span>
      </header>
      <section className="flex flex-1 flex-col justify-center py-20">
        <p className="mb-5 text-xs font-semibold uppercase tracking-[0.2em] text-emerald-700">A more personal job search</p>
        <h1 className="max-w-3xl text-5xl leading-[1.08] font-medium tracking-tight sm:text-7xl">
          Your experience.<br />New possibilities.
        </h1>
        <p className="mt-7 max-w-xl text-lg leading-8 text-emerald-950/65">
          One resume will connect you with relevant jobs, explain your strengths,
          and help you understand the skills each role needs.
        </p>
        <div className="mt-10 max-w-xl border-l-2 border-emerald-600 pl-5">
          <p className="font-medium">We’re building your matching experience.</p>
          <p className="mt-2 text-sm leading-6 text-emerald-950/65">
            Resume upload and job recommendations are not available yet.
            This preview does not collect personal information.
          </p>
        </div>
      </section>
      <footer className="border-t border-emerald-950/15 pt-6 text-xs text-emerald-950/60">
        Assumption University · NLP Project 2026
      </footer>
    </main>
  );
}
