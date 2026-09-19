import Link from "next/link";
import { JobImport } from "@/features/job-import/JobImport";

export default function JobImportPage() {
  return <div><Link href="/" className="underline">Back to resume upload</Link>
    <h1 className="mt-6 text-4xl font-medium">Add or update a job</h1>
    <p className="mt-3">For the project team. Candidate users only need to upload their resume.</p>
    <JobImport />
  </div>;
}
