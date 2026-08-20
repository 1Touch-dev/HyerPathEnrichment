import type { ManualJobEntry } from "@/src/lib/types";

export interface CreateManualJobEntryInput {
  title: string;
  company: string;
  location?: string | null;
  sourceLabel?: string | null;
  sourceUrl?: string | null;
  notes?: string | null;
}

export async function createManualJobEntry(
  input: CreateManualJobEntryInput,
): Promise<ManualJobEntry> {
  const res = await fetch("/api/manual-jobs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      title: input.title,
      company: input.company,
      location: input.location ?? null,
      source_label: input.sourceLabel ?? null,
      source_url: input.sourceUrl ?? null,
      notes: input.notes ?? null,
    }),
  });
  if (!res.ok) throw new Error(`Failed to create manual job entry: ${res.status}`);
  const json = await res.json();
  return json.data;
}
