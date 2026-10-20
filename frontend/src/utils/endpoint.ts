/** A review/list label: never repeat URL credentials, queries or fragments. */
export function endpointLabel(value: string | null | undefined): string {
  if (!value) return "No destination configured";
  try {
    const url = new URL(value);
    return `${url.protocol}//${url.host}${url.pathname}`;
  } catch {
    return "Invalid destination URL";
  }
}
