// Local wrapper for the one CV-management call that `src/lib/api-client.ts`'s
// `acceptCvBullet(reportId, bulletIndex)` cannot fully express: the real, merged backend
// route is `POST /api/documents/{document_id}/feedback/{report_id}/accept` (scoped by
// document_id — see backend/app/modules/documents/router.py), but `acceptCvBullet` only
// takes `reportId`/`bulletIndex`. Rather than editing that shared foundation file (out of
// scope for this chunk), this feature-local fetcher sends `documentId` through to the BFF
// route at `/api/cv-feedback/[reportId]/accept-bullet` directly. See final report for the
// recommended foundation fix (add `documentId` to `acceptCvBullet`'s signature).
export async function acceptCvFeedbackBullet(
  documentId: string,
  reportId: string,
  bulletIndex: number,
): Promise<{ accepted: boolean }> {
  const res = await fetch(`/api/cv-feedback/${reportId}/accept-bullet`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ documentId, bulletIndex }),
  });
  if (!res.ok) throw new Error(`Failed to accept CV feedback bullet: ${res.status}`);
  const json = await res.json();
  return json.data;
}
