import { useQuery } from "@tanstack/react-query";
import { getPracticeAudioStatus } from "@/src/lib/api-client";
import { practiceKeys } from "../api/keys";

/** Used by the report page to fetch `analysisData`/`voiceToneSignals` per audio attempt. */
export function useAudioStatus(recordingId: string | undefined) {
  return useQuery({
    queryKey: practiceKeys.audioStatus(recordingId ?? ""),
    queryFn: async () => (await getPracticeAudioStatus(recordingId!)).data,
    enabled: Boolean(recordingId),
  });
}
