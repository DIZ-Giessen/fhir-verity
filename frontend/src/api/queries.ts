import { keepPreviousData, queryOptions } from "@tanstack/react-query"

import { api, ApiError } from "@/lib/api-client"
import type { components } from "./schema"
import type { InvalidResourcesParams } from "@/lib/interface"

export type FhirServer = components["schemas"]["FhirServerRead"]
export type FhirServerCreate = components["schemas"]["FhirServerCreate"]
export type FhirServerUpdate = components["schemas"]["FhirServerUpdate"]

// Type Script Schema from the Backend
export type ResourceConfig = components["schemas"]["ResourceConfig"]
export type RuleDefinition = components["schemas"]["RuleDefinition"]
export type RuleUpdate = components["schemas"]["RuleUpdate"]
export type ServerAuthRead = components["schemas"]["ServerAuthRead"]
export type ServerAuthUpdate = components["schemas"]["ServerAuthUpdate"]
export type ServerMetadata = components["schemas"]["ServerMetadata"]
export type ResourceCount = components["schemas"]["ResourceCount"]
export type ValidationRunListItem =
  components["schemas"]["ValidationRunListItem"]
export type RunSummary = components["schemas"]["RunSummary"]
export type ValidationRunDetail = components["schemas"]["ValidationRunDetail"]
export type PerResourceStats = components["schemas"]["PerResourceStats"]
export type ResourceTypeSummary = components["schemas"]["ResourceTypeSummary"]
export type InvalidResourceRead = components["schemas"]["InvalidResourceRead"]
export type IssueDetail = components["schemas"]["IssueDetail"]
export type PaginatedInvalidResources =
  components["schemas"]["PaginatedInvalidResources"]
export type ValidationRunRead = components["schemas"]["ValidationRunRead"]
export type ActionResult = components["schemas"]["ActionResult"]
export type FixableTemplate = components["schemas"]["FixableTemplate"]
export type BulkActionResult = components["schemas"]["BulkActionResult"]
export type BulkDeleteRequest = components["schemas"]["BulkDeleteRequest"]
export type BulkFixRequest = components["schemas"]["BulkFixRequest"]
export type AuditLogListItem = components["schemas"]["AuditLogListItem"]
export type AuditLogDetail = components["schemas"]["AuditLogDetail"]
export type UserRoleUpdate = components["schemas"]["UserRoleUpdate"]

export type UserPreferencesUpdate =
  components["schemas"]["UserPreferencesUpdate"]
export type Role = UserRoleUpdate["role"] // "viewer" | "editor" | "admin"
export type ResourceFilters = components["schemas"]["ResourceFilters"]
export type FiltersUpdate = components["schemas"]["FiltersUpdate"]

// ======================

export const serverKeys = {
  all: ["servers"] as const,
  detail: (id: string) => ["servers", id] as const,
  auth: (id: string) => ["servers", id, "auth"] as const,
  metadata: (id: string) => ["servers", id, "metadata"] as const,
  resourceCounts: (id: string) => ["servers", id, "resource-counts"] as const,
}

export const serversQueryOptions = () =>
  queryOptions({
    queryKey: serverKeys.all,
    queryFn: async () => {
      const { data } = await api.GET("/api/v1/servers")
      return data ?? []
    },
  })

export async function createServer(body: FhirServerCreate) {
  const { data } = await api.POST("/api/v1/servers", { body })
  return data
}

export async function updateServer(id: string, body: FhirServerUpdate) {
  const { data } = await api.PATCH("/api/v1/servers/{server_id}", {
    params: { path: { server_id: id } },
    body,
  })
  return data
}

export async function deleteServer(id: string) {
  await api.DELETE("/api/v1/servers/{server_id}", {
    params: { path: { server_id: id } },
  })
}

// ---------------------------------------------------------------------------
// Validation config
// ---------------------------------------------------------------------------

export const configKeys = {
  all: ["config"] as const,
  resourceTypes: ["config", "resource-types"] as const,
  resource: (serverId: string, resourceType: string) =>
    ["config", "servers", serverId, resourceType] as const,
}

export const resourceTypesQueryOptions = () =>
  queryOptions({
    queryKey: configKeys.resourceTypes,
    queryFn: async () => {
      const { data } = await api.GET("/api/v1/config/resource-types")
      return data ?? []
    },
  })

export const serverResourceConfigQueryOptions = (
  serverId: string,
  resourceType: string
) =>
  queryOptions({
    queryKey: configKeys.resource(serverId, resourceType),
    queryFn: async () => {
      const { data } = await api.GET(
        "/api/v1/config/servers/{server_id}/{resource_type}",
        {
          params: {
            path: { server_id: serverId, resource_type: resourceType },
          },
        }
      )
      return data
    },
  })

export async function patchRule(
  serverId: string,
  resourceType: string,
  ruleKey: string,
  body: RuleUpdate
) {
  const { data } = await api.PATCH(
    "/api/v1/config/servers/{server_id}/{resource_type}/rules/{rule_key}",
    {
      params: {
        path: {
          server_id: serverId,
          resource_type: resourceType,
          rule_key: ruleKey,
        },
      },
      body,
    }
  )
  return data
}

export async function deleteServerConfig(
  serverId: string,
  resourceType: string
) {
  await api.DELETE("/api/v1/config/servers/{server_id}/{resource_type}", {
    params: { path: { server_id: serverId, resource_type: resourceType } },
  })
}

export const serverAuthQueryOptions = (serverId: string) =>
  queryOptions({
    queryKey: serverKeys.auth(serverId),
    queryFn: async () => {
      const { data } = await api.GET("/api/v1/servers/{server_id}/auth", {
        params: { path: { server_id: serverId } },
      })
      return data
    },
  })

export async function updateServerAuth(
  serverId: string,
  body: ServerAuthUpdate
) {
  const { data } = await api.PATCH("/api/v1/servers/{server_id}/auth", {
    params: { path: { server_id: serverId } },
    body,
  })
  return data
}

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------
export type AuthUser = components["schemas"]["UserRead"]

export const authKeys = {
  me: ["auth", "me"] as const,
}

export const meQueryOptions = () =>
  queryOptions({
    queryKey: authKeys.me,
    queryFn: async (): Promise<AuthUser | null> => {
      try {
        const { data } = await api.GET("/api/v1/auth/me")
        return (data as AuthUser) ?? null
      } catch (err) {
        if (err instanceof ApiError && err.status === 401) return null
        throw err
      }
    },
    retry: false,
    staleTime: 60_000,
  })

export async function logout() {
  await api.POST("/api/v1/auth/logout")
}

// SERVER IDS ====================

export const serverQueryOptions = (serverId: string) =>
  queryOptions({
    queryKey: serverKeys.detail(serverId),
    queryFn: async () => {
      const { data } = await api.GET("/api/v1/servers/{server_id}", {
        params: { path: { server_id: serverId } },
      })
      return data
    },
  })

export const serverMetadataQueryOptions = (serverId: string) =>
  queryOptions({
    queryKey: serverKeys.metadata(serverId),
    queryFn: async () => {
      const { data } = await api.GET("/api/v1/servers/{server_id}/metadata", {
        params: { path: { server_id: serverId } },
      })
      return data
    },
  })

export const serverResourceCountsQueryOptions = (serverId: string) =>
  queryOptions({
    queryKey: serverKeys.resourceCounts(serverId),
    queryFn: async () => {
      const { data } = await api.GET(
        "/api/v1/servers/{server_id}/resource-counts",
        { params: { path: { server_id: serverId } } }
      )
      return data ?? []
    },
  })

export const serverRunsQueryOptions = (serverId: string, limit = 5) =>
  queryOptions({
    queryKey: ["validation", "runs", { serverId, limit }],
    queryFn: async () => {
      const { data } = await api.GET("/api/v1/validation/runs", {
        params: { query: { server_id: serverId, limit, skip: 0 } },
      })
      return data
    },
  })

export const runSummaryQueryOptions = (runId: string) =>
  queryOptions({
    queryKey: ["validation", "runs", runId, "summary"],
    queryFn: async () => {
      const { data } = await api.GET(
        "/api/v1/validation/runs/{run_id}/summary",
        { params: { path: { run_id: runId } } }
      )
      return data
    },
  })

// Run Query

export const runsQueryOptions = (limit = 50) =>
  queryOptions({
    queryKey: ["validation", "runs", "all", { limit }],
    queryFn: async () => {
      const { data } = await api.GET("/api/v1/validation/runs", {
        params: { query: { limit, skip: 0 } },
      })
      return data
    },
  })
export const runQueryOptions = (runId: string) =>
  queryOptions({
    queryKey: ["validation", "runs", runId, "detail"],
    queryFn: async () => {
      const { data } = await api.GET("/api/v1/validation/runs/{run_id}", {
        params: { path: { run_id: runId } },
      })
      return data
    },
  })

export const invalidResourcesQueryOptions = (
  runId: string,
  params: InvalidResourcesParams = {}
) =>
  queryOptions({
    queryKey: ["validation", "runs", runId, "invalid-resources", params],
    queryFn: async () => {
      const { data } = await api.GET(
        "/api/v1/validation/runs/{run_id}/invalid-resources",
        { params: { path: { run_id: runId }, query: params } }
      )
      return data
    },
    placeholderData: keepPreviousData,
  })

//!  START VALIDATION RUNS
export async function startValidation(body: {
  server_id: string
  resource_types: string[]
}) {
  const { data } = await api.POST("/api/v1/validation/start", { body })
  return data
}

export async function resumeValidation(runId: string) {
  const { data } = await api.POST("/api/v1/validation/runs/{run_id}/resume", {
    params: { path: { run_id: runId } },
  })
  return data
}
//!  END VALIDATION RUNS

// ---------------------------------------------------------------------------
// Resource actions
// ----------------------------------------------------------------------

export const fixTemplatesQueryOptions = () =>
  queryOptions({
    queryKey: ["resources", "fix-templates"],
    queryFn: async () => {
      const { data } = await api.GET("/api/v1/resources/fix-templates")
      return data ?? []
    },
    staleTime: 5 * 60_000,
  })

export async function autoFixResource(
  serverId: string,
  resourceType: string,
  resourceId: string,
  reason?: string
) {
  const { data } = await api.POST(
    "/api/v1/resources/{server_id}/{resource_type}/{resource_id}/auto-fix",
    {
      params: {
        path: {
          server_id: serverId,
          resource_type: resourceType,
          resource_id: resourceId,
        },
      },
      body: { reason: reason ?? null },
    }
  )
  return data
}

export async function deleteResource(
  serverId: string,
  resourceType: string,
  resourceId: string,
  reason?: string
) {
  const { data } = await api.DELETE(
    "/api/v1/resources/{server_id}/{resource_type}/{resource_id}",
    {
      params: {
        path: {
          server_id: serverId,
          resource_type: resourceType,
          resource_id: resourceId,
        },
      },
      body: { reason: reason ?? null },
    }
  )
  return data
}

export async function bulkDelete(body: BulkDeleteRequest) {
  const { data } = await api.POST("/api/v1/resources/bulk-delete", { body })
  return data
}

export async function bulkFix(body: BulkFixRequest) {
  const { data } = await api.POST("/api/v1/resources/bulk-fix", { body })
  return data
}

export interface AuditLogParams {
  skip?: number
  limit?: number
  server_id?: string
  resource_type?: string
  action?: string
  status_filter?: string
}

export const auditLogQueryOptions = (params: AuditLogParams = {}) =>
  queryOptions({
    queryKey: ["audit-log", params],
    queryFn: async () => {
      const { data } = await api.GET("/api/v1/audit-log", {
        params: { query: params },
      })
      return data
    },
    placeholderData: keepPreviousData,
  })

export const auditLogDetailQueryOptions = (auditId: string) =>
  queryOptions({
    queryKey: ["audit-log", auditId, "detail"],
    queryFn: async () => {
      const { data } = await api.GET("/api/v1/audit-log/{audit_id}", {
        params: { path: { audit_id: auditId } },
      })
      return data
    },
  })

// ---------------------------------------------------------------------------
// Users & roles (admin)
// ---------------------------------------------------------------------------

const ROLE_ORDER: Record<Role, number> = { viewer: 0, editor: 1, admin: 2 }

/** True if `role` meets or exceeds `min`. Mirrors the backend ROLE_ORDER. */
export function hasRole(role: string | null | undefined, min: Role): boolean {
  if (!role) return false
  return (ROLE_ORDER[role as Role] ?? -1) >= ROLE_ORDER[min]
}

export const userKeys = {
  all: ["users"] as const,
}

export const usersQueryOptions = () =>
  queryOptions({
    queryKey: userKeys.all,
    queryFn: async () => {
      const { data } = await api.GET("/api/v1/users")
      return data ?? []
    },
  })

export async function updateUserRole(userId: string, role: Role) {
  const { data } = await api.PATCH("/api/v1/users/{user_id}/role", {
    params: { path: { user_id: userId } },
    body: { role },
  })
  return data
}

export async function updateMyPreferences(body: UserPreferencesUpdate) {
  const { data } = await api.PATCH("/api/v1/users/me/preferences", { body })
  return data
}

export async function updateServerFilters(
  serverId: string,
  resourceType: string,
  filters: ResourceFilters
) {
  const { data } = await api.PUT(
    "/api/v1/config/servers/{server_id}/{resource_type}/filters",
    {
      params: { path: { server_id: serverId, resource_type: resourceType } },
      body: { filters },
    }
  )
  return data
}
