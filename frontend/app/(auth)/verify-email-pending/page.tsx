"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Mail, RefreshCw } from "lucide-react";

export default function VerifyEmailPendingPage() {
  const router = useRouter();
  const [resending, setResending] = useState(false);
  const [resent, setResent] = useState(false);
  const [error, setError] = useState("");

  const handleResend = async () => {
    setResending(true);
    setError("");

    try {
      const response = await fetch("/api/auth/resend-verification", {
        method: "POST",
        credentials: "include",
      });

      if (response.ok) {
        setResent(true);
        setTimeout(() => setResent(false), 3000);
      } else {
        const data = await response.json();
        setError(data.error || "Failed to resend email");
      }
    } catch (error) {
      console.error("Failed to resend:", error);
      setError("Network error. Please try again.");
    } finally {
      setResending(false);
    }
  };

  const openEmail = () => {
    window.location.href = "mailto:";
  };

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <Card className="w-full max-w-md p-8 shadow-lg text-center">
        <div className="mx-auto w-16 h-16 rounded-full bg-blue-100 dark:bg-blue-900/20 flex items-center justify-center mb-6">
          <Mail className="w-8 h-8 text-blue-600 dark:text-blue-400" />
        </div>

        <div className="mb-6">
          <h2 className="text-3xl font-bold tracking-tight">Check your email</h2>
          <p className="mt-2 text-muted-foreground">
            We've sent a verification link to your email address.
          </p>
        </div>

        {error && (
          <Alert variant="destructive" className="mb-4 text-left">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {resent && (
          <Alert className="mb-4 text-left border-green-200 bg-green-50 dark:bg-green-900/20">
            <AlertDescription className="text-green-800 dark:text-green-200">
              Verification email sent successfully!
            </AlertDescription>
          </Alert>
        )}

        <div className="space-y-4">
          <Button onClick={openEmail} className="w-full" size="lg">
            <Mail className="mr-2 h-4 w-4" />
            Open Email App
          </Button>

          <div className="border-t pt-4">
            <p className="text-sm text-muted-foreground mb-3">Didn't receive the email?</p>
            <Button
              variant="outline"
              onClick={handleResend}
              disabled={resending || resent}
              className="w-full"
            >
              {resending ? (
                <>
                  <RefreshCw className="mr-2 h-3 w-3 animate-spin" />
                  Sending...
                </>
              ) : (
                "Resend verification email"
              )}
            </Button>
          </div>
        </div>

        <p className="text-xs text-muted-foreground mt-6">
          Check your spam folder if you don't see it within a few minutes.
        </p>

        <Button variant="link" onClick={() => router.push("/login")} className="mt-4">
          Back to Login
        </Button>
      </Card>
    </div>
  );
}
