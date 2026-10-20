"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/providers/auth-provider";
import { resolvePostLoginPath } from "@/src/lib/product-doors";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { PasswordInput } from "@/components/ui/password-input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Loader2, Mail } from "lucide-react";

export default function LoginPage() {
  const router = useRouter();
  const { login, completeLoginMfa } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [mfaStep, setMfaStep] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("mfa") === "required") {
      setMfaStep(true);
    }
  }, []);

  const continueAfterLogin = (user: Parameters<typeof resolvePostLoginPath>[0]) => {
    router.push(
      resolvePostLoginPath(user, new URLSearchParams(window.location.search).get("redirect")),
    );
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");

    try {
      if (mfaStep) {
        const user = await completeLoginMfa(code);
        continueAfterLogin(user);
        return;
      }
      const outcome = await login(email, password);
      if (outcome.mfaRequired) {
        setMfaStep(true);
        return;
      }
      continueAfterLogin(outcome.user);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center px-4 py-16">
      <Card variant="accent" className="w-full max-w-md shadow-panel">
        <CardHeader className="text-center">
          <p className="text-[0.7rem] font-semibold uppercase tracking-[0.16em] text-primary">
            Sign in
          </p>
          <CardTitle className="text-3xl tracking-tight">
            {mfaStep ? "Check your authenticator" : "Welcome Back"}
          </CardTitle>
          <CardDescription>
            {mfaStep
              ? "Enter the 6-digit code from your authenticator app."
              : "Sign in to your account"}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {error && (
            <Alert variant="destructive" className="mb-4">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            {mfaStep ? (
              <div className="space-y-2">
                <Label htmlFor="mfa-code">6-digit code</Label>
                <Input
                  id="mfa-code"
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                  placeholder="123456"
                  required
                />
              </div>
            ) : (
              <>
                <div className="space-y-2">
                  <Label htmlFor="email">Email</Label>
                  <Input
                    id="email"
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="you@example.com"
                    required
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="password">Password</Label>
                  <PasswordInput
                    id="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="Enter your password"
                    required
                    minLength={8}
                  />
                </div>
              </>
            )}

            <Button
              type="submit"
              className="w-full bg-primary text-primary-foreground"
              disabled={loading}
            >
              {loading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Signing in...
                </>
              ) : (
                <>
                  <Mail className="mr-2 h-4 w-4" />
                  {mfaStep ? "Verify code" : "Sign In"}
                </>
              )}
            </Button>
          </form>

          {mfaStep ? (
            <Button
              type="button"
              variant="link"
              className="mt-4 h-auto w-full p-0"
              onClick={() => {
                setMfaStep(false);
                setCode("");
                setError("");
              }}
            >
              Use email and password instead
            </Button>
          ) : null}

          {!mfaStep ? (
            <>
              <div className="relative my-6">
                <div className="absolute inset-0 flex items-center">
                  <span className="w-full border-t" />
                </div>
                <div className="relative flex justify-center text-xs uppercase">
                  <span className="bg-card px-2 text-muted-foreground">Or</span>
                </div>
              </div>

              <Button
                type="button"
                variant="outline"
                className="w-full"
                disabled={loading}
                onClick={() => {
                  window.location.href = "/api/auth/google/authorize";
                }}
              >
                Continue with Google
              </Button>
            </>
          ) : null}

          <div className="mt-6 text-center text-sm">
            <p className="text-muted-foreground">
              Don&apos;t have an account?{" "}
              <Button
                variant="link"
                onClick={() => router.push("/register")}
                className="h-auto p-0 font-semibold"
              >
                Sign up
              </Button>
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
