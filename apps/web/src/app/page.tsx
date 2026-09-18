import { ResumeUpload } from "@/features/upload/ResumeUpload";

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
      <ResumeUpload />
    </div>
  );
}
