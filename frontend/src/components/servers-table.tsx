import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Link } from "@tanstack/react-router"
import {
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  useReactTable,
} from "@tanstack/react-table"
import {
  ChevronLeft,
  ChevronRight,
  Eye,
  KeyRound,
  MoreHorizontal,
  Pencil,
  SlidersHorizontal,
  Trash2,
} from "lucide-react"
import { useState } from "react"
import { toast } from "sonner"
import { ServerAuthDialog } from "./server-auth-dialog"
import type { ColumnDef, SortingState } from "@tanstack/react-table"

import type { FhirServer } from "@/api/queries"
import { deleteServer, serverKeys } from "@/api/queries"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { cn } from "@/lib/utils"
import { apiErrorMessage } from "@/lib/api-client"

const dateFormatter = new Intl.DateTimeFormat(undefined, {
  year: "numeric",
  month: "short",
  day: "numeric",
  hour: "2-digit",
  minute: "2-digit",
})

interface ServersTableProps {
  data: Array<FhirServer>
  onEdit: (server: FhirServer) => void
}

export function ServersTable({ data, onEdit }: ServersTableProps) {
  const [sorting, setSorting] = useState<SortingState>([])
  const [rowSelection, setRowSelection] = useState({})
  const [globalFilter, setGlobalFilter] = useState("")
  const [deleteTarget, setDeleteTarget] = useState<FhirServer | null>(null)
  const [authTarget, setAuthTarget] = useState<FhirServer | null>(null)

  const queryClient = useQueryClient()

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteServer(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: serverKeys.all })
      queryClient.invalidateQueries({ queryKey: ["validation"] })
      queryClient.invalidateQueries({ queryKey: ["audit-log"] })
      setDeleteTarget(null)
      toast.success("Server deleted", {
        description: "All runs, findings and audit entries were removed.",
      })
    },
    onError: (err) => {
      toast.error("Could not delete server", {
        description: apiErrorMessage(err),
      })
    },
  })

  const columns: Array<ColumnDef<FhirServer>> = [
    /* {
      id: "select",
      header: ({ table }) => (
        <Checkbox
          checked={
            table.getIsAllPageRowsSelected() ||
            (table.getIsSomePageRowsSelected() && "indeterminate")
          }
          onCheckedChange={(value) => table.toggleAllPageRowsSelected(!!value)}
          aria-label="Select all"
        />
      ),
      cell: ({ row }) => (
        <Checkbox
          checked={row.getIsSelected()}
          onCheckedChange={(value) => row.toggleSelected(!!value)}
          aria-label="Select row"
        />
      ),
      enableSorting: false,
      enableHiding: false,
    }, */
    {
      accessorKey: "name",
      header: "Name",
      cell: ({ row }) => (
        <Link
          to="/servers/$id"
          params={{ id: row.original.id }}
          className="font-medium hover:text-primary hover:underline"
        >
          {row.original.name}
        </Link>
      ),
    },
    {
      accessorKey: "project_id",
      header: "Project",
      cell: ({ row }) => (
        <Badge variant="secondary">{row.original.project_id}</Badge>
      ),
    },
    {
      accessorKey: "base_url",
      header: "Base URL",
      cell: ({ row }) => (
        <span className="font-mono text-xs text-muted-foreground">
          {row.original.base_url}
        </span>
      ),
    },
    {
      accessorKey: "is_active",
      header: "Status",
      cell: ({ row }) =>
        row.original.is_active ? (
          <Badge
            variant="outline"
            className="border-0 bg-emerald-500/15 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-400"
          >
            Active
          </Badge>
        ) : (
          <Badge variant="secondary">Inactive</Badge>
        ),
    },
    {
      accessorKey: "created_at",
      header: "Created",
      cell: ({ row }) => (
        <span className="text-xs text-muted-foreground">
          {dateFormatter.format(new Date(row.original.created_at))}
        </span>
      ),
    },
    {
      id: "actions",
      cell: ({ row }) => (
        <div className="text-right">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon" className="h-8 w-8">
                <MoreHorizontal className="h-4 w-4" />
                <span className="sr-only">Open menu</span>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem asChild>
                <Link to="/servers/$id" params={{ id: row.original.id }}>
                  <Eye className="mr-2 h-4 w-4" />
                  View details
                </Link>
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => onEdit(row.original)}>
                <Pencil className="mr-2 h-4 w-4" />
                Edit
              </DropdownMenuItem>
              <DropdownMenuItem asChild>
                <Link to="/servers/$id/config" params={{ id: row.original.id }}>
                  <SlidersHorizontal className="mr-2 h-4 w-4" />
                  Config
                </Link>
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => setAuthTarget(row.original)}>
                <KeyRound className="mr-2 h-4 w-4" />
                Server auth
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem
                className="text-destructive focus:text-destructive"
                onClick={() => setDeleteTarget(row.original)}
              >
                <Trash2 className="mr-2 h-4 w-4" />
                Delete
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      ),
    },
  ]

  const table = useReactTable({
    data,
    columns,
    getCoreRowModel: getCoreRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    onSortingChange: setSorting,
    onRowSelectionChange: setRowSelection,
    onGlobalFilterChange: setGlobalFilter,
    globalFilterFn: "includesString",
    state: {
      sorting,
      rowSelection,
      globalFilter,
    },
    initialState: {
      pagination: { pageSize: 10 },
    },
  })

  const pageCount = table.getPageCount()
  const currentPage = table.getState().pagination.pageIndex + 1
  const filteredRows = table.getFilteredRowModel().rows.length

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <Input
          placeholder="Search a server..."
          value={globalFilter}
          onChange={(e) => setGlobalFilter(e.target.value)}
          className="h-8 w-full sm:w-92"
        />
        <div className="flex items-center gap-2">
          <span className="text-sm text-muted-foreground">Show</span>
          <Select
            value={String(table.getState().pagination.pageSize)}
            onValueChange={(value) => table.setPageSize(Number(value))}
          >
            <SelectTrigger className="h-8 w-16">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {[5, 10, 20, 50].map((size) => (
                <SelectItem key={size} value={String(size)}>
                  {size}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <span className="text-sm text-muted-foreground">entries</span>
        </div>
      </div>

      <div className="rounded-lg border">
        <Table>
          <TableHeader>
            {table.getHeaderGroups().map((headerGroup) => (
              <TableRow key={headerGroup.id}>
                {headerGroup.headers.map((header) => (
                  <TableHead key={header.id}>
                    {header.isPlaceholder
                      ? null
                      : flexRender(
                          header.column.columnDef.header,
                          header.getContext()
                        )}
                  </TableHead>
                ))}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {table.getRowModel().rows.length ? (
              table.getRowModel().rows.map((row) => (
                <TableRow
                  key={row.id}
                  data-state={row.getIsSelected() && "selected"}
                >
                  {row.getVisibleCells().map((cell) => (
                    <TableCell key={cell.id}>
                      {flexRender(
                        cell.column.columnDef.cell,
                        cell.getContext()
                      )}
                    </TableCell>
                  ))}
                </TableRow>
              ))
            ) : (
              <TableRow>
                <TableCell
                  colSpan={columns.length}
                  className="h-24 text-center text-sm text-muted-foreground"
                >
                  {globalFilter
                    ? "No servers match your search"
                    : "No servers registered yet"}
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-sm text-pretty text-muted-foreground">
          {filteredRows === 0
            ? "0 entries"
            : `Showing ${
                table.getState().pagination.pageIndex *
                  table.getState().pagination.pageSize +
                1
              } to ${Math.min(
                (table.getState().pagination.pageIndex + 1) *
                  table.getState().pagination.pageSize,
                filteredRows
              )} of ${filteredRows} entries`}
        </p>
        {pageCount > 1 && (
          <div className="flex items-center gap-1">
            <Button
              variant="outline"
              size="icon"
              className="h-8 w-8"
              onClick={() => table.previousPage()}
              disabled={!table.getCanPreviousPage()}
              aria-label="Previous page"
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>
            {Array.from({ length: pageCount }, (_, i) => i + 1).map((page) => (
              <Button
                key={page}
                variant={currentPage === page ? "default" : "outline"}
                size="icon"
                className={cn("h-8 w-8")}
                onClick={() => table.setPageIndex(page - 1)}
                aria-label={`Go to page ${page}`}
              >
                {page}
              </Button>
            ))}
            <Button
              variant="outline"
              size="icon"
              className="h-8 w-8"
              onClick={() => table.nextPage()}
              disabled={!table.getCanNextPage()}
              aria-label="Next page"
            >
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        )}
      </div>

      <AlertDialog
        open={deleteTarget !== null}
        onOpenChange={(open) => !open && setDeleteTarget(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete server?</AlertDialogTitle>
            <AlertDialogDescription>
              <span className="font-medium text-foreground">
                {deleteTarget?.name}
              </span>{" "}
              will be removed from Verity together with all of its validation
              runs, invalid resources, configuration overrides and audit log
              entries. The FHIR server itself and its data are not touched. This
              cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deleteMutation.isPending}>
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                if (deleteTarget) deleteMutation.mutate(deleteTarget.id)
              }}
              disabled={deleteMutation.isPending}
              className="bg-destructive hover:bg-destructive/90"
            >
              {deleteMutation.isPending ? "Deleting..." : "Delete"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
      <ServerAuthDialog
        open={authTarget !== null}
        onOpenChange={(open) => !open && setAuthTarget(null)}
        server={authTarget}
      />
    </div>
  )
}
