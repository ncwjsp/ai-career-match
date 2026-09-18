import type { CandidateProfile } from "@/lib/api/client";

export function ProfileView({ profile }: { profile: CandidateProfile }) {
  return (
    <section className="mt-8 space-y-5" aria-labelledby="profile-heading">
      <h2 id="profile-heading" className="text-2xl font-medium">Your recognized profile</h2>
      <p>{profile.summary ?? "There is not enough evidence to produce a summary."}</p>
      <dl className="space-y-3 text-sm leading-6">
        <div><dt className="font-semibold">Skills</dt><dd>{profile.skills.map(s => s.name).join(", ") || "Not identified"}</dd></div>
        <div><dt className="font-semibold">Roles</dt><dd>{profile.job_titles.join(", ") || "Not identified"}</dd></div>
        <div><dt className="font-semibold">Organizations</dt><dd>{profile.organizations.join(", ") || "Not identified"}</dd></div>
        <div><dt className="font-semibold">Estimated experience</dt><dd>{profile.estimated_experience_years === null ? "Unknown — dates were incomplete" : `${profile.estimated_experience_years} years (overlapping periods counted once)`}</dd></div>
        <div><dt className="font-semibold">Education</dt><dd>{profile.education.map(e => [e.qualification, e.institution].filter(Boolean).join(" · ")).join("; ") || "Not identified"}</dd></div>
      </dl>
      {profile.experience.length > 0 && <div><h3 className="font-semibold">Experience</h3><ul className="list-inside list-disc text-sm">{profile.experience.map((e, i) => <li key={i}>{e.job_title ?? "Role unknown"} · {e.organization ?? "Organization unknown"} ({e.start_date ?? "Unknown start"} – {e.end_date ?? "Unknown end"})</li>)}</ul></div>}
      {profile.projects.length > 0 && <div><h3 className="font-semibold">Projects</h3><ul className="list-inside list-disc text-sm">{profile.projects.map((p, i) => <li key={i}>{p.name}: {p.description}</li>)}</ul></div>}
      {profile.extraction_warnings.length > 0 && <details><summary>Extraction notes</summary><ul className="list-inside list-disc text-sm">{profile.extraction_warnings.map((w, i) => <li key={i}>{w.replaceAll("_", " ").toLowerCase()}</li>)}</ul></details>}
      <details><summary>Source evidence</summary><ul className="mt-2 space-y-2 text-sm">{profile.evidence.map((e, i) => <li key={i}><span className="font-medium">{e.page ? `Page ${e.page}` : e.section ?? "Resume"}: </span><q className="whitespace-pre-wrap">{e.excerpt}</q></li>)}</ul></details>
      <p className="text-xs text-emerald-950/65">Unknown values are kept unknown. Negated or uncertain skill mentions are not counted as confirmed skills.</p>
    </section>
  );
}
