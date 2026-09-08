export default function Home() {
  return (
    <div>
      <p className="mb-5 text-xs font-semibold uppercase tracking-[0.2em] text-emerald-700">
        A more personal job search
      </p>
      <h1 className="max-w-3xl text-5xl leading-[1.08] font-medium tracking-tight sm:text-7xl">
        Your experience.
        <br />
        New possibilities.
      </h1>
      <p className="mt-7 max-w-xl text-lg leading-8 text-emerald-950/65">
        One resume will connect you with relevant jobs, explain your strengths, and help you
        understand the skills each role needs.
      </p>
      <div className="mt-10 max-w-xl border-l-2 border-emerald-600 pl-5">
        <p className="font-medium">We&rsquo;re building your matching experience.</p>
        <p className="mt-2 text-sm leading-6 text-emerald-950/65">
          Resume upload is not available yet. Once a resume has been analyzed, its ranked jobs and
          explanations appear at <code>/recommendations/&lt;candidate id&gt;</code> for that
          session. New jobs refresh those results automatically, with no second upload.
          This preview does not collect personal information.
        </p>
      </div>
    </div>
  );
}
