import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useEffect } from "react"
import { Controller, useForm } from "react-hook-form"
import { z } from "zod"

import {
  type FhirServer,
  createServer,
  serverKeys,
  updateServer,
} from "@/api/queries"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Switch } from "@/components/ui/switch"
import { ApiError } from "@/lib/api-client"
import { Field, FieldDescription, FieldError, FieldLabel } from "./ui/field"

const formSchema = z.object({
  name: z.string().min(1, "Name is required").max(255),
  base_url: z.string().url("Must be a valid URL"),
  project_id: z.string().min(1, "Project is required").max(64),
  is_active: z.boolean(),
})

type FormValues = z.infer<typeof formSchema>

interface ServerFormDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  server?: FhirServer
}

export function ServerFormDialog({
  open,
  onOpenChange,
  server,
}: ServerFormDialogProps) {
  const isEdit = Boolean(server)
  const queryClient = useQueryClient()

  const form = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      name: "",
      base_url: "",
      project_id: "",
      is_active: true,
    },
  })

  // When the dialog opens or the target server changes, sync form values
  useEffect(() => {
    if (open) {
      form.reset({
        name: server?.name ?? "",
        base_url: server?.base_url ?? "",
        project_id: server?.project_id ?? "",
        is_active: server?.is_active ?? true,
      })
    }
  }, [open, server, form])

  const mutation = useMutation({
    mutationFn: async (values: FormValues) => {
      if (isEdit && server) {
        return updateServer(server.id, values)
      }
      return createServer(values)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: serverKeys.all })
      onOpenChange(false)
    },
  })

  const errorMessage =
    mutation.error instanceof ApiError
      ? typeof mutation.error.body === "object" &&
        mutation.error.body !== null &&
        "detail" in mutation.error.body
        ? String((mutation.error.body as { detail: unknown }).detail)
        : mutation.error.message
      : mutation.error?.message

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{isEdit ? "Edit server" : "Add server"}</DialogTitle>
          <DialogDescription>
            {isEdit
              ? "Update the FHIR server configuration."
              : "Register a new FHIR server for validation."}
          </DialogDescription>
        </DialogHeader>

        <form
          onSubmit={form.handleSubmit((values) => mutation.mutate(values))}
          className="space-y-4"
        >
          <Controller
            control={form.control}
            name="name"
            render={({ field, fieldState }) => (
              <Field>
                <FieldLabel htmlFor="name">Name</FieldLabel>

                <Input
                  id="name"
                  aria-invalid={fieldState.invalid}
                  placeholder="HAPI Production"
                  {...field}
                />
                <FieldError errors={[fieldState.error]} />
              </Field>
            )}
          />

          <Controller
            control={form.control}
            name="base_url"
            render={({ field, fieldState }) => (
              <Field>
                <FieldLabel htmlFor="base_url">Base URL</FieldLabel>
                <Input
                  id="base_url"
                  aria-invalid={fieldState.invalid}
                  placeholder="https://fhir.example.com/fhir"
                  {...field}
                />
                <FieldError errors={[fieldState.error]} />
              </Field>
            )}
          />

          <Controller
            control={form.control}
            name="project_id"
            render={({ field, fieldState }) => (
              <Field>
                <FieldLabel htmlFor="project">Project</FieldLabel>

                <Input
                  id="base_url"
                  aria-invalid={fieldState.invalid}
                  placeholder="CALM-QE"
                  {...field}
                />
                <FieldDescription>
                  The MII use case this server belongs to.
                </FieldDescription>
                <FieldError errors={[fieldState.error]} />
              </Field>
            )}
          />

          <Controller
            control={form.control}
            name="is_active"
            render={({ field, fieldState }) => (
              <Field className="flex flex-row items-center justify-between rounded-lg border p-3">
                <div className="space-y-0.5">
                  <FieldLabel htmlFor="is_activate">Active</FieldLabel>
                  <FieldDescription>
                    Enable validation runs against this server
                  </FieldDescription>
                </div>
                <Switch
                  id="is_activate"
                  checked={field.value}
                  onCheckedChange={field.onChange}
                />
                <FieldError errors={[fieldState.error]} />
              </Field>
            )}
          />

          {errorMessage && (
            <p className="text-sm text-destructive">{errorMessage}</p>
          )}

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={mutation.isPending}>
              {mutation.isPending
                ? "Saving..."
                : isEdit
                  ? "Save changes"
                  : "Create"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
