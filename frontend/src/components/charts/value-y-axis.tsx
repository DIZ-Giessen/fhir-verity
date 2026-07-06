"use client"

import { memo, useEffect, useMemo, useState } from "react"
import { createPortal } from "react-dom"
import { useChart, useChartStable, useYScale } from "./chart-context"

// useYScale liefert dieselbe Skala, die <Bar> für die Balkenhöhe nutzt.
// Für die Achse brauchen wir zusätzlich .ticks() (visx/d3-Linear-Skala).
type NumericScale = {
  (value: number): number | undefined
  ticks?: (count: number) => number[]
}

const compact = (v: number) =>
  Intl.NumberFormat(undefined, { notation: "compact" }).format(v)

export interface ValueYAxisProps {
  /** Y-Skalen-Gruppe. Muss zu <Bar yAxisId> passen. Default: "left" */
  yAxisId?: string | number
  /** Angestrebte Anzahl Ticks. Default: 5 */
  ticks?: number
  /** Formatter für die Beschriftung. Default: kompakte Zahl (1.2K) */
  formatValue?: (v: number) => string
}

export function ValueYAxis(props: ValueYAxisProps) {
  const { containerRef } = useChartStable()
  const [mounted, setMounted] = useState(false)

  useEffect(() => {
    setMounted(true)
  }, [])

  const container = containerRef.current
  if (!(mounted && container)) {
    return null
  }
  return <ValueYAxisInner {...props} container={container} />
}

const ValueYAxisInner = memo(function ValueYAxisInner({
  yAxisId = "left",
  ticks = 5,
  formatValue = compact,
  container,
}: ValueYAxisProps & { container: HTMLDivElement }) {
  const { margin } = useChart()
  const scale = useYScale(yAxisId) as NumericScale | undefined

  const tickItems = useMemo(() => {
    if (!scale?.ticks) {
      return []
    }
    return scale.ticks(ticks).map((value) => ({
      value,
      // + margin.top: gleiche Verschiebung ins Container-Koordinatensystem
      // wie in BarYAxis (barScale(label) + margin.top)
      y: (scale(value) ?? 0) + margin.top,
    }))
  }, [scale, ticks, margin.top])

  return createPortal(
    <div
      className="pointer-events-none absolute top-0 bottom-0"
      style={{ left: 0, width: margin.left }}
    >
      {tickItems.map((item) => (
        <span
          key={item.value}
          className="absolute right-0 pr-2 text-right text-xs text-muted-foreground tabular-nums"
          style={{ top: item.y, transform: "translateY(-50%)" }}
        >
          {formatValue(item.value)}
        </span>
      ))}
    </div>,
    container
  )
})

ValueYAxis.displayName = "ValueYAxis"

export default ValueYAxis
