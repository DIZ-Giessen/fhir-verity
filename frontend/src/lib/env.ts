const API_URL = import.meta.env.VITE_API_URL

if (!API_URL) {
  throw new Error(
    "VITE_API_URL is not set. Create a .env file in the frontend root."
  )
}

export const env = {
  API_URL: API_URL as string,
} as const
