"use client";

import { useState } from "react";
import { useAuth } from "@/providers/auth-provider";
import { AlertCircle, X } from "lucide-react";
import { Button } from "@/components/ui/button";

export function VerificationBanner() {
  const { user } = useAuth();
  const [dismissed, setDismissed] = useState(false);
  const [resending, setResending] = useState(false);
  const [message, setMessage] = useState("");

  if (!user || user.is_verified || dismissed) {
    return null;
  }

  const handleResend = async () => {
    setResending(true);
    setMessage("");
    try {
      const response = await fetch("/api/auth/resend-verification", {
        method: "POST",
        credentials: "include",
      });

      if (response.ok) {
        setMessage("Verification email sent!");
        setTimeout(() => setMessage(""), 3000);
      } else {
        const data = await response.json();
        setMessage(data.detail || "Failed to send email");
      }
    } catch (error) {
      setMessage("Failed to send email. Please try again.");
    } finally {
      setResending(false);
    }
  };

  return (
    <div className="bg-yellow-50 border-b border-yellow-200 px-4 py-3">
      <div className="max-w-7xl mx-auto flex items-center justify-between">
        <div className="flex items-center gap-2">
          <AlertCircle className="h-5 w-5 text-yellow-600" />
          <p className="text-sm text-yellow-800">
            Please verify your email to access all features.
          </p>
          <Button
            variant="link"
            size="sm"
            onClick={handleResend}
            disabled={resending}
            className="text-yellow-800 underline h-auto p-0"
          >
            {resending ? "Sending..." : "Resend email"}
          </Button>
          {message && <span className="text-xs text-yellow-700">{message}</span>}
        </div>
        <button
          onClick={() => setDismissed(true)}
          className="text-yellow-600 hover:text-yellow-800"
        >
          <X className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
