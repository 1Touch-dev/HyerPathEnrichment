import { bffError } from "@/src/lib/bff-response";

export function PUT() {
  return bffError(
    "FEATURE_FLAGS_READ_ONLY",
    "Feature flag mutation is disabled until an application consumer exists.",
    405,
  );
}
