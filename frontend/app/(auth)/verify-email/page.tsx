"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { CheckCircle, XCircle, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

function VerifyEmailContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const token = searchParams.get("token");

  const [status, setStatus] = useState<"verifying" | "success" | "error">("verifying");
  const [error, setError] = useState("");

  useEffect(() => {
    if (!token) {
      setStatus("error");
      setError("No verification token provided");
      return;
    }

    verifyEmail();
  }, [token]);

  const verifyEmail = async () => {
    try {
      const response = await fetch("/api/auth/verify-email", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token }),
        credentials: "include",
      });

      if (response.ok) {
        setStatus("success");
        setTimeout(() => {
          router.push("/app");
        }, 2000);
      } else {
        const data = await response.json();
        setStatus("error");
        setError(data.error || "Verification failed");
      }
    } catch (err) {
      setStatus("error");
      setError("Network error. Please try again.");
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center px-4 py-16">
      <Card variant="accent" className="w-full max-w-md text-center shadow-panel">
        <CardHeader>
          {status === "verifying" && (
            <>
              <div className="mx-auto mb-2 flex size-16 items-center justify-center rounded-full bg-primary-soft text-primary">
                <Loader2 className="size-8 animate-spin" />
              </div>
              <CardTitle className="text-2xl tracking-tight">Verifying your email...</CardTitle>
              <CardDescription>Please wait a moment</CardDescription>
            </>
          )}

          {status === "success" && (
            <>
              <div className="mx-auto mb-2 flex size-16 items-center justify-center rounded-full bg-success-soft text-success">
                <CheckCircle className="size-8" />
              </div>
              <CardTitle className="text-2xl tracking-tight">Email Verified!</CardTitle>
              <CardDescription>
                Your email has been verified successfully.
                <br />
                Redirecting to your dashboard...
              </CardDescription>
            </>
          )}

          {status === "error" && (
            <>
              <div className="mx-auto mb-2 flex size-16 items-center justify-center rounded-full bg-destructive-soft text-destructive">
                <XCircle className="size-8" />
              </div>
              <CardTitle className="text-2xl tracking-tight">Verification Failed</CardTitle>
              <CardDescription>{error}</CardDescription>
            </>
          )}
        </CardHeader>

        {status === "error" ? (
          <CardContent className="space-y-2">
            <Button
              onClick={() => router.push("/login")}
              className="w-full bg-primary text-primary-foreground"
            >
              Go to Login
            </Button>
            <Button
              variant="outline"
              onClick={() => router.push("/verify-email-pending")}
              className="w-full"
            >
              Resend Verification Email
            </Button>
          </CardContent>
        ) : null}
      </Card>
    </div>
  );
}

export default function VerifyEmailPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center px-4 py-16">
          <Card variant="accent" className="w-full max-w-md text-center shadow-panel">
            <CardHeader>
              <div className="mx-auto mb-2 flex size-16 items-center justify-center rounded-full bg-primary-soft text-primary">
                <Loader2 className="size-8 animate-spin" />
              </div>
              <CardTitle className="text-2xl tracking-tight">Loading...</CardTitle>
            </CardHeader>
          </Card>
        </div>
      }
    >
      <VerifyEmailContent />
    </Suspense>
  );
}
