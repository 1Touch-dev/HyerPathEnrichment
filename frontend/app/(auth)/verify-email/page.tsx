"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { CheckCircle, XCircle, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

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
    <div className="flex min-h-screen items-center justify-center px-4">
      <Card className="w-full max-w-md p-8 shadow-lg text-center">
        {status === "verifying" && (
          <>
            <div className="mx-auto w-16 h-16 rounded-full bg-blue-100 dark:bg-blue-900/20 flex items-center justify-center mb-6">
              <Loader2 className="w-8 h-8 text-blue-600 dark:text-blue-400 animate-spin" />
            </div>
            <h2 className="text-2xl font-bold tracking-tight">Verifying your email...</h2>
            <p className="text-muted-foreground mt-2">Please wait a moment</p>
          </>
        )}

        {status === "success" && (
          <>
            <div className="mx-auto w-16 h-16 rounded-full bg-green-100 dark:bg-green-900/20 flex items-center justify-center mb-6">
              <CheckCircle className="w-8 h-8 text-green-600 dark:text-green-400" />
            </div>
            <h2 className="text-2xl font-bold tracking-tight">Email Verified!</h2>
            <p className="text-muted-foreground mt-2">
              Your email has been verified successfully.
              <br />
              Redirecting to your dashboard...
            </p>
          </>
        )}

        {status === "error" && (
          <>
            <div className="mx-auto w-16 h-16 rounded-full bg-red-100 dark:bg-red-900/20 flex items-center justify-center mb-6">
              <XCircle className="w-8 h-8 text-red-600 dark:text-red-400" />
            </div>
            <h2 className="text-2xl font-bold tracking-tight">Verification Failed</h2>
            <p className="text-muted-foreground mt-2">{error}</p>
            <div className="space-y-2 mt-6">
              <Button onClick={() => router.push("/login")} className="w-full">
                Go to Login
              </Button>
              <Button
                variant="outline"
                onClick={() => router.push("/verify-email-pending")}
                className="w-full"
              >
                Resend Verification Email
              </Button>
            </div>
          </>
        )}
      </Card>
    </div>
  );
}

export default function VerifyEmailPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center px-4">
          <Card className="w-full max-w-md p-8 shadow-lg text-center">
            <div className="mx-auto w-16 h-16 rounded-full bg-blue-100 dark:bg-blue-900/20 flex items-center justify-center mb-6">
              <Loader2 className="w-8 h-8 text-blue-600 dark:text-blue-400 animate-spin" />
            </div>
            <h2 className="text-2xl font-bold tracking-tight">Loading...</h2>
          </Card>
        </div>
      }
    >
      <VerifyEmailContent />
    </Suspense>
  );
}
