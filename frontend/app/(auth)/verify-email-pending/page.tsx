"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
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
    <div className="flex min-h-screen items-center justify-center px-4 py-16">
      <Card variant="accent" className="w-full max-w-md text-center shadow-panel">
        <CardHeader>
          <div className="mx-auto mb-2 flex size-16 items-center justify-center rounded-full bg-primary-soft text-primary">
            <Mail className="size-8" />
          </div>
          <CardTitle className="text-3xl tracking-tight">Check your email</CardTitle>
          <CardDescription>
            We&apos;ve sent a verification link to your email address.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {error && (
            <Alert variant="destructive" className="mb-4 text-left">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          {resent && (
            <Alert variant="success" className="mb-4 text-left">
              <AlertDescription>Verification email sent successfully!</AlertDescription>
            </Alert>
          )}

          <div className="space-y-4">
            <Button
              onClick={openEmail}
              className="w-full bg-primary text-primary-foreground"
              size="lg"
            >
              <Mail className="mr-2 h-4 w-4" />
              Open Email App
            </Button>

            <div className="border-t border-border/60 pt-4">
              <p className="mb-3 text-sm text-muted-foreground">Didn&apos;t receive the email?</p>
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

          <p className="mt-6 text-xs text-muted-foreground">
            Check your spam folder if you don&apos;t see it within a few minutes.
          </p>

          <Button variant="link" onClick={() => router.push("/login")} className="mt-4">
            Back to Login
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
