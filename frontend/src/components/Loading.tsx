import { AnimatedLoadingText, useLoadingText } from "@/lib/interface/loading"
import { TextDots } from "./text-dots"

export function Loading({ texts }: { texts: string[] }) {
  const loadingText = useLoadingText(texts)
  return (
    <div>
      <div className="flex min-h-svh items-center justify-center">
        <p className="animate-pulse text-sm text-muted-foreground">
          <TextDots>
            <AnimatedLoadingText text={loadingText} className="mr-1" />
          </TextDots>
        </p>
      </div>
    </div>
  )
}
