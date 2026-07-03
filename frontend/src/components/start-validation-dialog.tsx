import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useNavigate } from "@tanstack/react-router"
import { Check, ChevronsUpDown, ExternalLink, Loader2 } from "lucide-react"
import { useEffect, useRef, useState } from "react"
import { toast } from "sonner"

import {
  resourceTypesQueryOptions,
  serversQueryOptions,
  startValidation,
} from "@/api/queries"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"
import { Skeleton } from "@/components/ui/skeleton"
import { Alert, AlertDescription, AlertTitle } from "./ui/alert"
import { DangerTriangle } from "@solar-icons/react-perf/category/style/LineDuotone"

const DEFAULT_UNCHECKED_TYPES = new Set([
  "Condition",
  "Observation",
  "Medication",
  "MedicationAdministration",
  "MedicationStatement",
  "Procedure",
  "DiagnosticReport",
  "MedicationRequest",
  "Patient",
  "Encounter",
])

interface StartValidationDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  /** Fixed-server mode (e.g. server detail). Omit for the picker mode. */
  serverId?: string
  serverName?: string
}

export function StartValidationDialog({
  open,
  onOpenChange,
  serverId,
  serverName,
}: StartValidationDialogProps) {
  const queryClient = useQueryClient()
  const navigate = useNavigate()

  const typesQ = useQuery(resourceTypesQueryOptions())
  const serversQ = useQuery({ ...serversQueryOptions(), enabled: !serverId })

  const allTypes = typesQ.data ?? []
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [pickedServer, setPickedServer] = useState<string>()
  const seededRef = useRef(false)

  // default-select all types except DEFAULT_UNCHECKED_TYPES when the dialog opens
  useEffect(() => {
    if (open && allTypes.length && !seededRef.current) {
      setSelected(
        new Set(allTypes.filter((rt) => !DEFAULT_UNCHECKED_TYPES.has(rt)))
      )
      seededRef.current = true
    }
    if (!open) {
      seededRef.current = false
      setPickedServer(undefined)
    }
  }, [open, allTypes])

  const effectiveServerId = serverId ?? pickedServer
  const effectiveName =
    serverName ?? serversQ.data?.find((s) => s.id === pickedServer)?.name

  const mutation = useMutation({
    mutationFn: (vars: { server_id: string; resource_types: string[] }) =>
      startValidation(vars),
    onSuccess: (run) => {
      if (!run) return
      queryClient.invalidateQueries({ queryKey: ["validation", "runs"] })
      onOpenChange(false)
      const runId = run.id
      const name = effectiveName
      toast.custom((t) => (
        <div className="flex w-[400px] flex-col gap-2 rounded-md border border-border bg-popover p-4 text-popover-foreground shadow-lg">
          <div className="flex items-center gap-2">
            <span className="flex size-2 animate-pulse rounded-full bg-emerald-500" />
            <p className="animate-pulse text-sm font-medium">
              Validation started
            </p>
          </div>
          <div className="space-y-1 text-xs text-muted-foreground">
            <div className="flex items-center justify-between">
              <span>Server</span>
              <span className="font-medium text-foreground">{name ?? "—"}</span>
            </div>
            <div className="flex items-center justify-between">
              <span>Status</span>
              <span className="font-medium text-foreground">{run.status}</span>
            </div>
            <div className="flex items-center justify-between">
              <span>Run</span>
              <span className="font-mono font-medium text-foreground">
                {runId.slice(0, 8)}
              </span>
            </div>
          </div>
          <div className="mt-1 flex gap-2">
            <Button
              size="sm"
              variant="outline"
              className="flex-1"
              onClick={() => {
                navigate({
                  to: "/runs/$runId/invalid-resources",
                  params: { runId },
                })
                toast.dismiss(t)
              }}
            >
              Invalid resources
            </Button>
            <Button
              size="sm"
              className="flex-1 gap-1"
              onClick={() => {
                navigate({ to: "/runs/$runId/live", params: { runId } })
                toast.dismiss(t)
              }}
            >
              <ExternalLink className="size-3" />
              Live view
            </Button>
          </div>
        </div>
      ))
    },
    onError: (err) => {
      toast.error("Failed to start validation", {
        description: err instanceof Error ? err.message : "Unknown error",
      })
    },
  })

  const toggle = (rt: string) =>
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(rt)) next.delete(rt)
      else next.add(rt)
      return next
    })

  function handleStart() {
    if (!effectiveServerId || selected.size === 0) return
    const all = allTypes.length > 0 && selected.size === allTypes.length
    mutation.mutate({
      server_id: effectiveServerId,
      resource_types: all ? ["All"] : Array.from(selected),
    })
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl!">
        <DialogHeader>
          <DialogTitle>Start validation</DialogTitle>
          <DialogDescription>
            {serverName ? (
              <>
                Run validation against{" "}
                <span className="font-medium">{serverName}</span>.
              </>
            ) : (
              "Select a server and the resource types to validate."
            )}
          </DialogDescription>
        </DialogHeader>

        {!serverId && (
          <div className="space-y-1.5">
            <p className="text-xs font-medium text-muted-foreground">Server</p>
            <ServerPicker
              servers={serversQ.data ?? []}
              value={pickedServer}
              onChange={setPickedServer}
            />
          </div>
        )}

        <div className="space-y-1.5">
          <p className="text-xs font-medium text-muted-foreground">
            Resource types
          </p>
          {typesQ.isPending ? (
            <div className="grid grid-cols-2 gap-2">
              {Array.from({ length: 4 }).map((_, i) => (
                <Skeleton key={i} className="h-9 w-full" />
              ))}
            </div>
          ) : (
            <>
              <div className="grid grid-cols-2 gap-1">
                {allTypes.map((rt) => (
                  <label
                    key={rt}
                    className="flex cursor-pointer items-center gap-2 rounded-lg p-2 text-sm hover:bg-muted/50"
                  >
                    <Checkbox
                      checked={selected.has(rt)}
                      onCheckedChange={() => toggle(rt)}
                    />
                    <span>{rt}</span>
                  </label>
                ))}
              </div>
            </>
          )}
        </div>
        {(Array.from(selected).includes("Condition") ||
          Array.from(selected).includes("Observation")) && (
          <Alert className="border-amber-200 bg-amber-50 text-amber-900 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-50">
            <DangerTriangle className="size-5" />
            <AlertTitle>Attention!</AlertTitle>

            <AlertDescription>
              Validation runs for{" "}
              <span className="font-medium text-foreground">Condition</span> and{" "}
              <span className="font-medium text-foreground">Observation</span>{" "}
              can take{" "}
              <span className="font-medium text-foreground">
                significantly longer
              </span>
              . We recommend starting validation for these types{" "}
              <span className="font-medium text-foreground">one at a time</span>
              .
            </AlertDescription>
          </Alert>
        )}
        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={mutation.isPending}
          >
            Cancel
          </Button>
          <Button
            onClick={handleStart}
            disabled={
              !effectiveServerId ||
              selected.size === 0 ||
              mutation.isPending ||
              typesQ.isPending
            }
          >
            {mutation.isPending && (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            )}
            {mutation.isPending ? "Starting…" : "Start"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function ServerPicker({
  servers,
  value,
  onChange,
}: {
  servers: { id: string; name: string; base_url: string }[]
  value?: string
  onChange: (id: string) => void
}) {
  const [open, setOpen] = useState(false)
  const selected = servers.find((s) => s.id === value)

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          role="combobox"
          aria-expanded={open}
          className="w-full justify-between font-normal"
        >
          {selected ? selected.name : "Select server…"}
          <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent
        align="start"
        className="w-(--radix-popover-trigger-width) p-0"
      >
        <Command>
          <CommandInput placeholder="Search server…" />
          <CommandList>
            <CommandEmpty>No server found.</CommandEmpty>
            <CommandGroup>
              {servers.map((s) => (
                <CommandItem
                  key={s.id}
                  value={s.name}
                  onSelect={() => {
                    onChange(s.id)
                    setOpen(false)
                  }}
                >
                  <Check
                    className={`mr-2 h-4 w-4 ${
                      value === s.id ? "opacity-100" : "opacity-0"
                    }`}
                  />
                  <div className="flex flex-col">
                    <span>{s.name}</span>
                    <span className="text-xs text-muted-foreground">
                      {s.base_url}
                    </span>
                  </div>
                </CommandItem>
              ))}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  )
}
