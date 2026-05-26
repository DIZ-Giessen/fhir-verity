import createClient, { type Middleware } from "openapi-fetch"

import type { paths } from "@/api/schema"

import { env } from "./env"

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

export const api = createClient<paths>({ baseUrl: env.API_URL })
api.use(throwOnError)
