/** Auth state (Zustand + persist). Access token in memory; refresh cookie is HttpOnly. */

import { create } from 'zustand'
import { persist } from 'zustand/middleware'

import { api, setAccessToken } from '@/lib/api'
import type { TokenPair, User } from '@/types'

interface AuthState {
  user: User | null
  accessToken: string | null
  loading: boolean
  bootstrap: () => Promise<void>
  login: (email: string, password: string) => Promise<User>
  register: (fullName: string, email: string, password: string) => Promise<User>
  logout: () => Promise<void>
  setUser: (user: User | null) => void
  clear: () => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      accessToken: null,
      loading: false,

      bootstrap: async () => {
        const token = get().accessToken
        setAccessToken(token)
        if (!token) {
          set({ loading: false })
          return
        }
        set({ loading: true })
        try {
          const user = await api.get<User>('/auth/me')
          set({ user, loading: false })
        } catch {
          set({ user: null, accessToken: null, loading: false })
          setAccessToken(null)
        }
      },

      login: async (email, password) => {
        const pair = await api.post<TokenPair>('/auth/login', { email, password })
        setAccessToken(pair.access_token)
        const me = await api.get<User>('/auth/me')
        set({ user: me, accessToken: pair.access_token })
        return me
      },

      register: async (fullName, email, password) => {
        const user = await api.post<User>('/auth/register', {
          full_name: fullName,
          email,
          password,
        })
        const pair = await api.post<TokenPair>('/auth/login', { email, password })
        setAccessToken(pair.access_token)
        set({ user, accessToken: pair.access_token })
        return user
      },

      logout: async () => {
        try {
          await api.post('/auth/logout')
        } catch {
          /* best effort */
        }
        get().clear()
      },

      setUser: (user) => set({ user }),

      clear: () => {
        setAccessToken(null)
        set({ user: null, accessToken: null })
      },
    }),
    {
      name: 'smartsupport-auth',
      partialize: (state) => ({ user: state.user, accessToken: state.accessToken }),
      onRehydrateStorage: () => (state) => {
        setAccessToken(state?.accessToken ?? null)
      },
    },
  ),
)
