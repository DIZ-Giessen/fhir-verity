import { queryOptions } from "@tanstack/react-query"

import { api } from "@/lib/api-client"
import type { components } from "./schema"

export type FhirServer = components["schemas"]["FhirServerRead"]
export type FhirServerCreate = components["schemas"]["FhirServerCreate"]
export type FhirServerUpdate = components["schemas"]["FhirServerUpdate"]

export type ResourceConfig = components["schemas"]["ResourceConfig"]
export type RuleDefinition = components["schemas"]["RuleDefinition"]
export type RuleUpdate = components["schemas"]["RuleUpdate"]

export const serverKeys = {
  all: ["servers"] as const,
  detail: (id: string) => ["servers", id] as const,
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
