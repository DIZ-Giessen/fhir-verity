import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useEffect } from "react"
import { Controller, useForm } from "react-hook-form"
import { z } from "zod"

import {
  type FhirServer,
  type ServerAuthUpdate,
  serverAuthQueryOptions,
  serverKeys,
  updateServerAuth,
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { ApiError } from "@/lib/api-client"
import { Field, FieldDescription, FieldError, FieldLabel } from "./ui/field"

const schema = z
  .object({
    type: z.enum(["none", "basic", "oauth2_client_credentials"]),
    username: z.string().optional(),
    password: z.string().optional(),
    token_url: z.string().optional(),
    client_id: z.string().optional(),
    client_secret: z.string().optional(),
    scope: z.string().optional(),
  })
  .superRefine((val, ctx) => {
    if (val.type === "basic" && !val.username?.trim()) {
      ctx.addIssue({
        code: "custom",
        path: ["username"],
        message: "Username is required",
      })
    }
    if (val.type === "oauth2_client_credentials") {
      if (!val.token_url?.trim())
        ctx.addIssue({
          code: "custom",
          path: ["token_url"],
          message: "Token URL is required",
        })
      if (!val.client_id?.trim())
        ctx.addIssue({
          code: "custom",
          path: ["client_id"],
          message: "Client ID is required",
        })
    }
  })

type FormValues = z.infer<typeof schema>

interface ServerAuthDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  server: FhirServer | null
}

export function ServerAuthDialog({
  open,
  onOpenChange,
  server,
}: ServerAuthDialogProps) {
  const queryClient = useQueryClient()
  const serverId = server?.id

  const { data, isPending } = useQuery({
    ...serverAuthQueryOptions(serverId ?? ""),
    enabled: open && Boolean(serverId),
  })

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      type: "none",
      username: "",
      password: "",
      token_url: "",
      client_id: "",
      client_secret: "",
      scope: "",
    },
  })

  const authType = form.watch("type")

  useEffect(() => {
    if (open && data) {
      form.reset({
        type: data.type,
        username: data.username ?? "",
        password: "",
        token_url: data.token_url ?? "",
        client_id: data.client_id ?? "",
        client_secret: "",
        scope: data.scope ?? "",
      })
    }
  }, [open, data, form])

  const mutation = useMutation({
    mutationFn: (values: FormValues) => {
      if (!serverId) throw new Error("No server selected")
      const body: ServerAuthUpdate = { type: values.type }
      if (values.type === "basic") {
        body.username = values.username?.trim()
        if (values.password) body.password = values.password
      } else if (values.type === "oauth2_client_credentials") {
        body.token_url = values.token_url?.trim()
        body.client_id = values.client_id?.trim()
        if (values.client_secret) body.client_secret = values.client_secret
        if (values.scope?.trim()) body.scope = values.scope.trim()
      }
      return updateServerAuth(serverId, body)
    },
    onSuccess: () => {
      if (serverId)
        queryClient.invalidateQueries({ queryKey: serverKeys.auth(serverId) })
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

  const keepHint = data?.type === authType

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Server authentication</DialogTitle>
          <DialogDescription>
            {server?.name
              ? `How FHIR Verity authenticates against ${server.name}.`
              : "How FHIR Verity authenticates against this server."}
          </DialogDescription>
        </DialogHeader>

        {isPending ? (
          <div className="py-6 text-sm text-muted-foreground">Loading…</div>
        ) : (
          <form
            onSubmit={form.handleSubmit((values) => mutation.mutate(values))}
            className="space-y-4"
          >
            <Controller
              control={form.control}
              name="type"
              render={({ field }) => (
                <Field>
                  <FieldLabel htmlFor="auth-type">Method</FieldLabel>
                  <Select value={field.value} onValueChange={field.onChange}>
                    <SelectTrigger id="auth-type">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="none">No authentication</SelectItem>
                      <SelectItem value="basic">Basic auth</SelectItem>
                      <SelectItem value="oauth2_client_credentials">
                        OAuth2 (client credentials)
                      </SelectItem>
                    </SelectContent>
                  </Select>
                </Field>
              )}
            />

            {authType === "basic" && (
              <>
                <Controller
                  control={form.control}
                  name="username"
                  render={({ field, fieldState }) => (
                    <Field>
                      <FieldLabel htmlFor="username">Username</FieldLabel>
                      <Input
                        id="username"
                        aria-invalid={fieldState.invalid}
                        {...field}
                      />
                      <FieldError errors={[fieldState.error]} />
                    </Field>
                  )}
                />
                <Controller
                  control={form.control}
                  name="password"
                  render={({ field, fieldState }) => (
                    <Field>
                      <FieldLabel htmlFor="password">Password</FieldLabel>
                      <Input
                        id="password"
                        type="password"
                        autoComplete="new-password"
                        placeholder={
                          keepHint ? "Leave blank to keep current" : ""
                        }
                        aria-invalid={fieldState.invalid}
                        {...field}
                      />
                      <FieldDescription>
                        Leave blank to keep the existing password.
                      </FieldDescription>
                      <FieldError errors={[fieldState.error]} />
                    </Field>
                  )}
                />
              </>
            )}

            {authType === "oauth2_client_credentials" && (
              <>
                <Controller
                  control={form.control}
                  name="token_url"
                  render={({ field, fieldState }) => (
                    <Field>
                      <FieldLabel htmlFor="token_url">Token URL</FieldLabel>
                      <Input
                        id="token_url"
                        placeholder="https://…/protocol/openid-connect/token"
                        aria-invalid={fieldState.invalid}
                        {...field}
                      />
                      <FieldError errors={[fieldState.error]} />
                    </Field>
                  )}
                />
                <Controller
                  control={form.control}
                  name="client_id"
                  render={({ field, fieldState }) => (
                    <Field>
                      <FieldLabel htmlFor="client_id">Client ID</FieldLabel>
                      <Input
                        id="client_id"
                        placeholder="blaze-test"
                        aria-invalid={fieldState.invalid}
                        {...field}
                      />
                      <FieldError errors={[fieldState.error]} />
                    </Field>
                  )}
                />
                <Controller
                  control={form.control}
                  name="client_secret"
                  render={({ field, fieldState }) => (
                    <Field>
                      <FieldLabel htmlFor="client_secret">
                        Client secret
                      </FieldLabel>
                      <Input
                        id="client_secret"
                        type="password"
                        autoComplete="new-password"
                        placeholder={
                          keepHint ? "Leave blank to keep current" : ""
                        }
                        aria-invalid={fieldState.invalid}
                        {...field}
                      />
                      <FieldDescription>
                        Leave blank to keep the existing secret.
                      </FieldDescription>
                      <FieldError errors={[fieldState.error]} />
                    </Field>
                  )}
                />
                <Controller
                  control={form.control}
                  name="scope"
                  render={({ field }) => (
                    <Field>
                      <FieldLabel htmlFor="scope">Scope (optional)</FieldLabel>
                      <Input id="scope" {...field} />
                    </Field>
                  )}
                />
              </>
            )}

            {authType === "none" && (
              <p className="text-sm text-muted-foreground">
                Requests to this server will be sent without authentication.
              </p>
            )}

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
                {mutation.isPending ? "Saving…" : "Save"}
              </Button>
            </DialogFooter>
          </form>
        )}
      </DialogContent>
    </Dialog>
  )
}
