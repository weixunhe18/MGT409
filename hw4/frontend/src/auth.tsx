import { createContext, useCallback, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";

import * as api from "./api";
import type { RegisterInput, User } from "./api";

type AuthState = {
  user: User | null;
  /** True until the first /me check resolves, so the nav does not flash "Log In". */
  checking: boolean;
  login: (email: string, password: string) => Promise<User>;
  register: (input: RegisterInput) => Promise<User>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthState | null>(null);

/**
 * The session lives in an httpOnly cookie the page cannot read, so the only way
 * to learn who is logged in is to ask the server. This holds that answer.
 */
export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    api
      .fetchMe()
      .then(setUser)
      .finally(() => setChecking(false));
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const signedIn = await api.login(email, password);
    setUser(signedIn);
    return signedIn;
  }, []);

  const register = useCallback(async (input: RegisterInput) => {
    const created = await api.register(input);
    setUser(created);
    return created;
  }, []);

  const logout = useCallback(async () => {
    await api.logout();
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, checking, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
