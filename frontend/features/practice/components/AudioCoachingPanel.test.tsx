import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { AudioCoachingPanel } from "./AudioCoachingPanel";
import type { AudioRecordingStatus } from "@/src/lib/types";

function makeStatus(overrides: Partial<AudioRecordingStatus> = {}): AudioRecordingStatus {
  return {
    id: "rec-1",
    transcriptionStatus: "completed",
    transcription: "This is my answer.",
    analysisData: null,
    voiceToneSignals: null,
    durationSeconds: 42,
    ...overrides,
  };
}

describe("AudioCoachingPanel", () => {
  it("renders analysisData fields (filler words, WPM, clarity) when present", () => {
    render(
      <AudioCoachingPanel
        status={makeStatus({
          analysisData: { fillerWordCount: 3, wordsPerMinute: 130, clarityScore: 0.82 },
        })}
      />,
    );
    expect(screen.getByText("Filler words")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText("Words per minute")).toBeInTheDocument();
    expect(screen.getByText("130")).toBeInTheDocument();
    expect(screen.getByText("Clarity")).toBeInTheDocument();
    expect(screen.getByText("0.82")).toBeInTheDocument();
  });

  it("renders nothing extra when voiceToneSignals is null (HUME_API_KEY unset - fail-soft default)", () => {
    const { container } = render(
      <AudioCoachingPanel status={makeStatus({ voiceToneSignals: null })} />,
    );
    // Only the "Audio coaching" heading and (absent) analysis grid should be present -
    // no tone-related text should have been rendered at all.
    expect(container.textContent).not.toMatch(/tone/i);
  });

  it(
    "renders voiceToneSignals only as plain descriptive text - never a numeric score, " +
      "badge, or progress-bar element (ADR 0015 Decision 2/4, a firm product requirement)",
    () => {
      render(
        <AudioCoachingPanel
          status={makeStatus({
            voiceToneSignals: { overall_tone: "steady and confident", pacing_note: "even pacing" },
          })}
        />,
      );

      expect(screen.getByText(/overall tone/i)).toBeInTheDocument();
      expect(screen.getByText(/steady and confident/i)).toBeInTheDocument();
      expect(screen.getByText(/pacing note/i)).toBeInTheDocument();

      // No progress bars, meters, or ARIA-scored widgets anywhere in the panel.
      expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();
      expect(screen.queryByRole("meter")).not.toBeInTheDocument();
      // No "%"-suffixed confidence-score-looking text anywhere in the rendered output.
      expect(screen.queryByText(/%/)).not.toBeInTheDocument();
    },
  );

  it("renders both analysisData and voiceToneSignals together without cross-contaminating their styling", () => {
    render(
      <AudioCoachingPanel
        status={makeStatus({
          analysisData: { fillerWordCount: 1, wordsPerMinute: 145 },
          voiceToneSignals: { overall_tone: "slightly rushed toward the end" },
        })}
      />,
    );
    expect(screen.getByText("Filler words")).toBeInTheDocument();
    expect(screen.getByText(/slightly rushed toward the end/i)).toBeInTheDocument();
    expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();
  });
});
