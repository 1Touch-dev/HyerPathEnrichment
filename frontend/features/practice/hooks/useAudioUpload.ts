import { useMutation } from "@tanstack/react-query";
import { uploadPracticeAudio } from "@/src/lib/api-client";

type UploadPracticeAudioInput = {
  practiceSessionId: string;
  audioFormat: string;
  file: Blob;
  filename: string;
};

/**
 * Deviation from the plan (§10.4): the plan suggests a raw `XMLHttpRequest`-based upload
 * with progress reporting. This is skipped as unnecessary complexity for this task's
 * scope — this repo's existing convention for mutations is the shared fetch-based
 * `api-client.ts` helpers, and no other upload flow in this codebase reports progress.
 */
export function useAudioUpload() {
  return useMutation({
    mutationFn: async ({
      practiceSessionId,
      audioFormat,
      file,
      filename,
    }: UploadPracticeAudioInput) =>
      (await uploadPracticeAudio(practiceSessionId, audioFormat, file, filename)).data,
  });
}
