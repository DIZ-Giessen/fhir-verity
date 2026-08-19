import {
  ArrowRightUp,
  SquareBottomUp,
} from "@solar-icons/react-perf/category/style/LineDuotone"
import { createFileRoute, Link } from "@tanstack/react-router"

export const Route = createFileRoute("/")({
  component: HomePage,
})

function HomePage() {
  return (
    <div className="flex flex-col items-center justify-center gap-6 p-6">
      <div className="flex flex-col items-center gap-2 text-center">
        <h1 className="text-3xl font-semibold tracking-tight">FHIR Verity</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Validation hub for FHIR resources, made with ❤️ by the Data
          Integration Center of Giessen.
        </p>
        <div className="flex items-center gap-4 pt-4">
          <a
            href="https://mirgitlab.med.uni-giessen.de/povoc1/fhir-verity/-/tree/main/documentation?ref_type=heads"
            rel="noopener noreferrer"
            target="_blank"
            className="inline-flex items-center gap-1 text-sm text-muted-foreground underline hover:text-primary"
          >
            Read the documentation <ArrowRightUp className="h-4 w-4" />
          </a>
          <a
            href="https://mirgitlab.med.uni-giessen.de/povoc1/fhir-verity"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 text-sm text-muted-foreground underline hover:text-primary"
          >
            view the Project <SquareBottomUp className="h-4 w-4" />
          </a>
        </div>
      </div>
    </div>
  )
}
