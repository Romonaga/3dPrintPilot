export type AuthUser = {
  id: number;
  username: string;
  email: string | null;
  role: string;
  isActive: boolean;
  forcePasswordChange: boolean;
  failedLoginCount: number;
  lastLoginAt: string | null;
};

export type AuthStatus = {
  authenticated: boolean;
  bootstrapRequired: boolean;
  user: AuthUser | null;
};

export type AuthSession = {
  token: string;
  expiresAt: string;
  user: AuthUser;
};
