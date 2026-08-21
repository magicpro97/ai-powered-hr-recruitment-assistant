/**
 * Get CSRF token from cookie for use with fetch()-based requests.
 * Axios requests are handled automatically via interceptor in AuthContext.
 */
export function getCsrfHeaders(): Record<string, string> {
    if (typeof document === "undefined") return {};
    const match = document.cookie.match(/csrf_token=([^;]+)/);
    return match ? { "X-CSRF-Token": match[1] } : {};
}
