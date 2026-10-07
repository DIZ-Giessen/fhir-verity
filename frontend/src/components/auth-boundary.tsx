import { useQuery } from "@tanstack/react-query"
import { Navigate, useLocation } from "@tanstack/react-router"
import { AlertTriangle } from "lucide-react"
import { useEffect, useState } from "react"
import { Loading } from "./Loading"
import type { ReactNode } from "react"

import { SiteHeader } from "@/components/site-header"
import { authConfigQueryOptions, meQueryOptions } from "@/api/queries"
import { LoadingUserMessage, LodatingText } from "@/lib/interface/loading"

const PUBLIC_PATHS = ["/login"]

export function AuthBoundary({ children }: { children: ReactNode }) {
  const [mounted, setMounted] = useState(false)
  useEffect(() => setMounted(true), [])

  if (!mounted) {
    return <Loading texts={LodatingText} />
  }

  return <AuthGate>{children}</AuthGate>
}

function AuthGate({ children }: { children: ReactNode }) {
  const { pathname } = useLocation()
  const isPublic = PUBLIC_PATHS.some((p) => pathname.startsWith(p))

  const { data, isPending } = useQuery(meQueryOptions())
  const { data: authConfig, isPending: configPending } = useQuery(
    authConfigQueryOptions()
  )
  const authDisabled = authConfig?.auth_enabled === false

  if (isPending || configPending) {
    return <Loading texts={LoadingUserMessage} />
  }

  const isAuthenticated = data != null

  if (isAuthenticated) {
    if (isPublic) return <Navigate to="/" />
    return (
      <div className="flex min-h-svh flex-col">
        <SiteHeader />
        {authDisabled && <AuthDisabledBanner />}
        <main className="container mx-auto flex-1 px-4 py-6 lg:px-6">
          {children}
        </main>
      </div>
    )
  }

  // Without auth there is nothing to sign in to: /auth/me only fails here
  // when the backend itself is broken, so say that instead of offering login.
  if (authDisabled) {
    return (
      <div className="flex min-h-dvh items-center justify-center p-4 text-center text-sm text-muted-foreground">
        The backend did not return a user. Check that it is running and
        reachable.
      </div>
    )
  }

  if (isPublic) return <>{children}</>
  return <Navigate to="/login" />
}

function AuthDisabledBanner() {
  return (
    <div
      role="status"
      className="border-b border-amber-200 bg-amber-50 text-amber-900 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-50"
    >
      <p className="container mx-auto flex items-center gap-2 px-4 py-2 text-sm lg:px-6">
        <AlertTriangle className="size-4 shrink-0" aria-hidden />
        Authentication is disabled (AUTH_ENABLED=false). Everyone works as the
        built-in admin, for development and demos only.
      </p>
    </div>
  )
}
