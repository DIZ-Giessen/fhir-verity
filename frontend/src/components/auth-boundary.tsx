import { useQuery } from "@tanstack/react-query"
import { Navigate, useLocation } from "@tanstack/react-router"
import { useEffect, useState, type ReactNode } from "react"

import { SiteHeader } from "@/components/site-header"
import { ApiError, api } from "@/lib/api-client"

const PUBLIC_PATHS = ["/login"]

interface AuthUser {
  id: string
  username: string | null
  email: string | null
  full_name: string | null
  role: "viewer" | "editor" | "admin"
}

export function AuthBoundary({ children }: { children: ReactNode }) {
  const [mounted, setMounted] = useState(false)
  useEffect(() => setMounted(true), [])

  if (!mounted) {
    return <Centered>Loading…</Centered>
  }

  return <AuthGate>{children}</AuthGate>
}

function AuthGate({ children }: { children: ReactNode }) {
  const { pathname } = useLocation()
  const isPublic = PUBLIC_PATHS.some((p) => pathname.startsWith(p))

  const { data, isPending } = useQuery({
    queryKey: ["auth", "me"],
    queryFn: async (): Promise<AuthUser | null> => {
      try {
        const { data } = await api.GET("/api/v1/auth/me")
        return (data as AuthUser) ?? null
      } catch (err) {
        if (err instanceof ApiError && err.status === 401) return null
        throw err
      }
    },
    retry: false,
    staleTime: 60_000,
  })

  if (isPending) {
    return <Centered>Loading…</Centered>
  }

  const isAuthenticated = data != null

  if (isAuthenticated) {
    if (isPublic) return <Navigate to="/" />
    return (
      <div className="flex min-h-svh flex-col">
        <SiteHeader />
        <main className="container mx-auto flex-1 px-4 py-6 lg:px-6">
          {children}
        </main>
      </div>
    )
  }

  if (isPublic) return <>{children}</>
  return <Navigate to="/login" />
}

function Centered({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-svh items-center justify-center">
      <p className="text-sm text-muted-foreground">{children}</p>
    </div>
  )
}
