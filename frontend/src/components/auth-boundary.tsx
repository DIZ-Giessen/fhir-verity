import { useQuery } from "@tanstack/react-query"
import { Navigate, useLocation } from "@tanstack/react-router"
import { useEffect, useState, type ReactNode } from "react"

import { SiteHeader } from "@/components/site-header"
import { meQueryOptions } from "@/api/queries"

const PUBLIC_PATHS = ["/login"]

export function AuthBoundary({ children }: { children: ReactNode }) {
  const [mounted, setMounted] = useState(false)
  useEffect(() => setMounted(true), [])

  if (!mounted) {
    return <Centered>Loading...</Centered>
  }

  return <AuthGate>{children}</AuthGate>
}

function AuthGate({ children }: { children: ReactNode }) {
  const { pathname } = useLocation()
  const isPublic = PUBLIC_PATHS.some((p) => pathname.startsWith(p))

  const { data, isPending } = useQuery(meQueryOptions())

  if (isPending) {
    return <Centered>Loading...</Centered>
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
      <p className="animate-pulse text-sm text-muted-foreground">{children}</p>
    </div>
  )
}
