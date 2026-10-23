import { createFileRoute } from "@tanstack/react-router"

import { LoginIcon } from "@solar-icons/react/line-duotone"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { env } from "@/lib/env"

export const Route = createFileRoute("/login")({ component: LoginPage })

function LoginPage() {
  const error =
    typeof window !== "undefined"
      ? new URLSearchParams(window.location.search).get("error")
      : null

  return (
    <div className="flex min-h-dvh items-center justify-center">
      <Card className="w-full max-w-sm rounded-4xl px-6 py-10 pt-14 shadow-sm">
        <CardContent>
          <div className="flex flex-col items-center space-y-8">
            <img src="logo-white.svg" className="size-28" />
            <div className="space-y-2 text-center">
              <h1 className="text-3xl font-semibold text-balance text-foreground">
                FHIR Verity
              </h1>
              <p className="text-sm text-pretty text-muted-foreground">
                Sign in with your Institute Account to continue.
              </p>
            </div>

            {error && (
              <p className="text-sm text-destructive">
                Sign-in failed: {error}
              </p>
            )}

            <Button
              className="group w-full rounded-xl"
              size="lg"
              onClick={() => {
                window.location.href = `${env.API_URL}/api/v1/auth/login`
              }}
            >
              Sign in
              <LoginIcon
                strokeWidth={2.3}
                className="size-6 translate-x-0 transition-transform group-hover:translate-x-1"
              />
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
