import { HeadContent, Scripts, createRootRoute } from "@tanstack/react-router"
import type { ReactNode } from "react"

import { AuthBoundary } from "@/components/auth-boundary"

import appCss from "../styles.css?url"
import { ThemeProvider } from "@/components/theme-provider"
import { Toaster } from "sonner"

export const Route = createRootRoute({
  head: () => ({
    meta: [
      { charSet: "utf-8" },
      { name: "viewport", content: "width=device-width, initial-scale=1" },
      { title: "FHIR Verity" },
    ],
    links: [{ rel: "stylesheet", href: appCss }],
  }),
  notFoundComponent: () => (
    <div className="space-y-1">
      <h1 className="text-2xl font-semibold tracking-tight">404</h1>
      <p className="text-sm text-muted-foreground">
        The requested page could not be found.
      </p>
    </div>
  ),
  shellComponent: RootDocument,
})

function RootDocument({ children }: { children: ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <HeadContent />
      </head>
      <body className="bg-background text-foreground antialiased">
        <ThemeProvider defaultTheme="dark" storageKey="theme">
          <AuthBoundary>
            {children}

            <Toaster position="bottom-right" />
          </AuthBoundary>
        </ThemeProvider>
        <Scripts />
      </body>
    </html>
  )
}
