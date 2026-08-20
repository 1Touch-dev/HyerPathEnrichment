"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { JdPracticeSessionView } from "@/features/jd-practice";
import { PracticeLandingView } from "./PracticeLandingView";

/**
 * `/app/practice` already existed on this base branch as Module 3's role-based practice
 * landing page (`PracticeLandingView`, no query-param awareness). Rather than creating a
 * conflicting new route (phase2_module4 §9.6 asks for `frontend/app/app/practice/page.tsx`
 * but this path was already taken), this adds a JD-tailored mode alongside the existing
 * one: when `?jobMatchId=` is present the JD-tailored flow renders instead of the generic
 * role-picker, leaving `PracticeLandingView` and the `[sessionId]` routes untouched.
 */
function PracticeRouter() {
  const searchParams = useSearchParams();
  const jobMatchId = searchParams.get("jobMatchId");

  if (jobMatchId) {
    return <JdPracticeSessionView jobMatchId={jobMatchId} />;
  }

  return <PracticeLandingView />;
}

export default function PracticePage() {
  return (
    <Suspense fallback={<div className="animate-pulse h-96 rounded-lg bg-muted" />}>
      <PracticeRouter />
    </Suspense>
  );
}
