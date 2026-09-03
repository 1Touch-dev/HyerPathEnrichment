"use client";

import React, { createContext, useContext, useState, useEffect, ReactNode } from "react";
import { startProactiveRefresh, stopProactiveRefresh } from "@/src/lib/token-refresh";

interface User {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  is_verified: boolean;
  is_active: boolean;
  avatar_url?: string;
  created_at: string;
  is_superuser: boolean;
  role_id?: string | null;
  role_name?: string | null;
  permissions?: Array<string | { resource?: string; action?: string; name?: string }>;
  mfa_enabled?: boolean;
}

interface AuthContextType {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  register: (
    email: string,
    password: string,
    firstName: string,
    lastName: string,
    inviteToken?: string,
  ) => Promise<void>;
  deleteAccount: () => Promise<void>;
  refetchUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchUser = async () => {
    try {
      const response = await fetch("/api/auth/me", {
        credentials: "include",
      });

      if (response.ok) {
        const data = await response.json();
        setUser(data);
      } else {
        setUser(null);
      }
    } catch (error) {
      console.error("Failed to fetch user:", error);
      setUser(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchUser();
  }, []);

  // Start/stop proactive token refresh based on auth state
  useEffect(() => {
    if (user) {
      // User is authenticated - start proactive refresh
      startProactiveRefresh();
    } else {
      // User is not authenticated - stop proactive refresh
      stopProactiveRefresh();
    }

    // Cleanup on unmount
    return () => {
      stopProactiveRefresh();
    };
  }, [user]);

  const login = async (email: string, password: string) => {
    const response = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
      credentials: "include",
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || "Login failed");
    }

    const data = await response.json();
    setUser(data.user);
  };

  const logout = async () => {
    await fetch("/api/auth/logout", {
      method: "POST",
      credentials: "include",
    });
    setUser(null);
  };

  const register = async (
    email: string,
    password: string,
    firstName: string,
    lastName: string,
    inviteToken?: string,
  ) => {
    const body: {
      email: string;
      password: string;
      first_name: string;
      last_name: string;
      invite_token?: string;
    } = {
      email,
      password,
      first_name: firstName,
      last_name: lastName,
    };
    // Omit the key entirely when absent (not an empty string) -- backend
    // auth/router.py keys its invite-lookup logic on `if user_data.invite_token:`.
    if (inviteToken) {
      body.invite_token = inviteToken;
    }

    const response = await fetch("/api/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      credentials: "include",
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || "Registration failed");
    }
  };

  const deleteAccount = async () => {
    await fetch("/api/auth/delete-account", {
      method: "POST",
      credentials: "include",
    });
    setUser(null);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        login,
        logout,
        register,
        deleteAccount,
        refetchUser: fetchUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
