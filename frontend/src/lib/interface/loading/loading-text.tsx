import { AnimatePresence, motion } from "motion/react"
import { cn } from "@/lib/utils"

type AnimatedLoadingTextProps = {
  text: string
  className?: string
}

export function AnimatedLoadingText({
  text,
  className,
}: AnimatedLoadingTextProps) {
  return (
    <AnimatePresence mode="popLayout" initial={false}>
      <motion.span
        key={text}
        initial={{ opacity: 0, y: 6, filter: "blur(3px)" }}
        animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
        exit={{ opacity: 0, y: -6, filter: "blur(3px)" }}
        transition={{ duration: 0.35, ease: "easeOut" }}
        className={cn("inline-block", className)}
      >
        {text}
      </motion.span>
    </AnimatePresence>
  )
}
