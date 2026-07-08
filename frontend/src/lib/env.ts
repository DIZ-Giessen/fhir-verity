// Leerer String => relative, same-origin Requests (Produktion hinter dem Reverse-Proxy).
// VITE_API_URL nur für Split-Origin-Dev setzen.
export const env = {
  API_URL: import.meta.env.VITE_API_URL ?? "",
} as const
