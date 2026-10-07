import createClient from "openapi-fetch"
import { env } from "./env"
import type { Middleware } from "openapi-fetch"

import type { paths } from "@/api/schema"

export class ApiError extends Error {
  constructor(
    public status: number,
    public statusText: string,
    public body: unknown
  ) {
    super(`API ${status}: ${statusText}`)
    this.name = "ApiError"
  }
}

/** Human-readable message for a failed request: FastAPI's `detail` if present. */
export function apiErrorMessage(err: unknown): string {
  if (err instanceof ApiError) {
    const detail = (err.body as { detail?: unknown } | null)?.detail
    if (typeof detail === "string") return detail
    return `HTTP ${err.status} ${err.statusText}`
  }
  return err instanceof Error ? err.message : String(err)
}

const throwOnError: Middleware = {
  async onResponse({ response }) {
    if (response.ok) return undefined

    let body: unknown = null
    try {
      body = await response.clone().json()
    } catch {
      body = await response
        .clone()
        .text()
        .catch(() => null)
    }
    throw new ApiError(response.status, response.statusText, body)
  },
}

export const api = createClient<paths>({
  baseUrl: env.API_URL,
  credentials: "include",
})
api.use(throwOnError)
