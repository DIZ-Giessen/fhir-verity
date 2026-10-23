import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { ChevronsUpDown, Loader2, X } from "lucide-react"
import { useState } from "react"
import { toast } from "sonner"

import { Avatar, AvatarFallback } from "./ui/avatar"
import type { FhirServer } from "@/api/queries"
import {
  addServerMember,
  removeServerMember,
  serverKeys,
  serverMembersQueryOptions,
  userDirectoryQueryOptions,
} from "@/api/queries"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
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
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"
import { Skeleton } from "@/components/ui/skeleton"
import { apiErrorMessage } from "@/lib/api-client"
import { env } from "@/lib/env"
import { initials } from "@/lib/functions"

interface ServerMembersDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  server: FhirServer | null
}

export function ServerMembersDialog({
  open,
  onOpenChange,
  server,
}: ServerMembersDialogProps) {
  const queryClient = useQueryClient()
  const serverId = server?.id ?? ""
  const [pickerOpen, setPickerOpen] = useState(false)

  const membersQ = useQuery({
    ...serverMembersQueryOptions(serverId),
    enabled: open && Boolean(serverId),
  })
  const directoryQ = useQuery({ ...userDirectoryQueryOptions(), enabled: open })

  const memberIds = new Set((membersQ.data ?? []).map((m) => m.user_id))
  const candidates = (directoryQ.data ?? []).filter(
    (u) => u.id !== server?.owner_id && !memberIds.has(u.id)
  )

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: serverKeys.members(serverId) })

  const addMutation = useMutation({
    mutationFn: (userId: string) => addServerMember(serverId, userId),
    onSuccess: invalidate,
    onError: (err) =>
      toast.error("Could not share the server", {
        description: apiErrorMessage(err),
      }),
  })

  const removeMutation = useMutation({
    mutationFn: (userId: string) => removeServerMember(serverId, userId),
    onSuccess: invalidate,
    onError: (err) =>
      toast.error("Could not remove access", {
        description: apiErrorMessage(err),
      }),
  })

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Share server</DialogTitle>
          <DialogDescription>
            Users you add can see {server?.name ?? "this server"}.{" "}
            <a href={env.DOCS_URL} target="_blank" rel="noopener noreferrer">
              Read more about server sharing
            </a>
          </DialogDescription>
        </DialogHeader>

        <Popover open={pickerOpen} onOpenChange={setPickerOpen}>
          <PopoverTrigger asChild>
            <Button
              variant="outline"
              role="combobox"
              aria-expanded={pickerOpen}
              className="w-full justify-between font-normal text-muted-foreground"
              disabled={addMutation.isPending}
            >
              {addMutation.isPending ? "Sharing…" : "Add a user…"}
              <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
            </Button>
          </PopoverTrigger>
          <PopoverContent
            align="start"
            className="w-(--radix-popover-trigger-width) p-0"
          >
            <Command>
              <CommandInput placeholder="Search user…" />
              <CommandList>
                <CommandEmpty>No user found.</CommandEmpty>
                <CommandGroup>
                  {candidates.map((u) => (
                    <CommandItem
                      key={u.id}
                      value={`${u.username ?? ""} ${u.full_name ?? ""} ${u.id}`}
                      onSelect={() => {
                        addMutation.mutate(u.id)
                        setPickerOpen(false)
                      }}
                    >
                      <div className="flex min-w-0 flex-1 flex-col">
                        <span className="truncate">
                          {u.full_name ?? u.username ?? u.id}
                        </span>
                        {u.full_name && u.username && (
                          <span className="truncate text-xs text-muted-foreground">
                            {u.username}
                          </span>
                        )}
                      </div>
                      <Badge variant="secondary">{u.role}</Badge>
                    </CommandItem>
                  ))}
                </CommandGroup>
              </CommandList>
            </Command>
          </PopoverContent>
        </Popover>

        <div className="space-y-1">
          <p className="text-xs font-medium text-muted-foreground">
            Shared with
          </p>
          {membersQ.isPending ? (
            <Skeleton className="h-9 w-full" />
          ) : (membersQ.data ?? []).length === 0 ? (
            <p className="py-3 text-sm text-muted-foreground">
              Not shared with anyone yet.
            </p>
          ) : (
            <ul className="space-y-2 divide-y px-0">
              {(membersQ.data ?? []).map((m) => (
                <li
                  key={m.user_id}
                  className="flex items-center justify-between gap-2 py-2"
                >
                  <div className="flex min-w-0 items-center gap-2">
                    <Avatar className="h-7 w-7">
                      <AvatarFallback className="text-xs">
                        {initials(m.username)}
                      </AvatarFallback>
                    </Avatar>
                    <p className="truncate text-base">
                      {m.full_name ?? m.username ?? m.user_id}
                    </p>
                  </div>
                  <div className="flex items-center gap-4">
                    <Badge variant="outline">{m.role}</Badge>
                    <Button
                      variant="destructive"
                      size="icon"
                      className="h-7 w-7"
                      aria-label="Remove access"
                      disabled={removeMutation.isPending}
                      onClick={() => removeMutation.mutate(m.user_id)}
                    >
                      {removeMutation.isPending &&
                      removeMutation.variables === m.user_id ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <X className="h-4 w-4" />
                      )}
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}
