import { Link } from "@tanstack/react-router"

import { Button } from "@/components/ui/button"
import { MainNav } from "@/components/main-nav"

export function SiteHeader() {
  return (
    <header className="sticky top-0 z-40 w-full border-b bg-background">
      <div className="container mx-auto flex h-14 items-center justify-between gap-4 px-4 lg:px-6">
        <Link to="/" className="flex items-center">
          <img src="/logo-white.png" className="size-8" aria-hidden />
          <span className="text-xl font-semibold tracking-tight">
            FHIR Verity
          </span>
        </Link>

        <div className="flex flex-1 justify-center">
          <MainNav />
        </div>

        <div className="flex items-center gap-2">
          <Button variant="ghost" size="sm" asChild>
            <Link to="/">Log in</Link>
          </Button>
        </div>
      </div>
    </header>
  )
}
