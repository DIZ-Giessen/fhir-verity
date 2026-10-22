import { Check, ChevronsUpDown } from "lucide-react"
import { useState } from "react"

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
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"

/** Searchable server select; matches on name and base URL. */
export function ServerPicker({
  servers,
  value,
  onChange,
  placeholder = "Select server…",
}: {
  servers: Array<{ id: string; name: string; base_url: string }>
  value?: string
  onChange: (id: string) => void
  placeholder?: string
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
          <span className="truncate">
            {selected ? selected.name : placeholder}
          </span>
          <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent
        align="start"
        className="w-(--radix-popover-trigger-width) min-w-72 p-0"
      >
        <Command>
          <CommandInput placeholder="Search server…" />
          <CommandList className="overflow-y-auto!">
            <CommandEmpty>No server found.</CommandEmpty>
            <CommandGroup className="overflow-y-auto!">
              {servers.map((s) => (
                <CommandItem
                  key={s.id}
                  value={`${s.name} ${s.base_url} ${s.id}`}
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
                  <div className="flex min-w-0 flex-col">
                    <span className="truncate">{s.name}</span>
                    <span className="truncate text-xs text-muted-foreground">
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
