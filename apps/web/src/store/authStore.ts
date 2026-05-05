import { create } from 'zustand';
import type { UserRead } from '@/types/user';

interface AuthState {
  token: string | null;
  user: UserRead | null;
  isInitialized: boolean;
  setAuth: (token: string, user: UserRead) => void;
  setUser: (user: UserRead) => void;
  setInitialized: () => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  token: localStorage.getItem('access_token'),
  user: null,
  isInitialized: false,

  setAuth: (token, user) => {
    localStorage.setItem('access_token', token);
    set({ token, user });
  },

  setUser: (user) => set({ user }),

  setInitialized: () => set({ isInitialized: true }),

  logout: () => {
    localStorage.removeItem('access_token');
    set({ token: null, user: null });
  },
}));
