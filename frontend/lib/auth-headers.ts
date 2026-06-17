export function withAuthHeaders(
  base: Record<string, string>,
  token: string | null | undefined
): Record<string, string> {
  if (!token) return base;
  return { ...base, Authorization: `Bearer ${token}` };
}
