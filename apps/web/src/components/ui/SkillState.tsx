import type { SkillComparison } from "@/lib/api/client";

/**
 * A skill's state, always spelled out.
 *
 * "Missing" means the resume did not evidence the skill. It is not a claim that
 * the person lacks it, and the wording here has to keep saying so.
 */
const LABELS: Record<SkillComparison["state"], { text: string; mark: string; className: string }> =
  {
    present: { text: "Evidenced", mark: "✓", className: "border-emerald-700 text-emerald-800" },
    partial: { text: "Partly evidenced", mark: "△", className: "border-amber-700 text-amber-800" },
    missing: { text: "Not evidenced", mark: "✕", className: "border-emerald-950/30 text-emerald-950/60" },
  };

export function SkillState({ skill }: { skill: SkillComparison }) {
  const label = LABELS[skill.state];
  return (
    <li className={`flex items-baseline gap-2 rounded border px-3 py-2 text-sm ${label.className}`}>
      <span aria-hidden="true">{label.mark}</span>
      <span className="font-medium">{skill.skill}</span>
      <span className="text-xs">
        {label.text}
        {skill.required ? " · required" : " · preferred"}
      </span>
    </li>
  );
}
