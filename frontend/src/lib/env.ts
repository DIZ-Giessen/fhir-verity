// Empty string => relative, same-origin requests (production behind the reverse proxy).
// Set VITE_API_URL only for split-origin development.
const PROJECT_URL: string =
  import.meta.env.VITE_PROJECT_URL ??
  "https://mirgitlab.med.uni-giessen.de/povoc1/fhir-verity"

export const env = {
  API_URL: import.meta.env.VITE_API_URL ?? "",
  /** Source repository, linked from the home and cleanup pages. */
  PROJECT_URL,
  DOCS_URL: `${PROJECT_URL}/-/tree/main/documentation`,
} as const
