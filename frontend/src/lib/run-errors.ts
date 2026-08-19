/**
 * Runs whose crawl exhausted all retries against an unresponsive FHIR server
 * store a message starting with this phrase (see FhirServerUnresponsiveError
 * in backend/app/services/validation_rules.py). Used to give that failure
 * mode its own explanation in the UI instead of a generic "Run failed".
 */
export function isServerUnresponsiveError(
  message: string | null | undefined
): boolean {
  return Boolean(message) && message!.includes("did not respond after")
}
