// API client — cookie-authenticated fetch wrapper with silent refresh.

let refreshPromise = null;

async function refreshSession() {
  if (!refreshPromise) {
    refreshPromise = fetch("/api/auth/refresh", {
      method: "POST",
      credentials: "include",
    })
      .then((r) => {
        if (!r.ok) throw new Error("refresh failed");
        return r.json();
      })
      .finally(() => {
        refreshPromise = null;
      });
  }
  return refreshPromise;
}

export async function api(path, options = {}) {
  const { body, method = "GET", formData, ...rest } = options;

  const fetchOptions = {
    method,
    credentials: "include",
    headers: {},
    ...rest,
  };

  if (formData) {
    fetchOptions.body = formData;
    // let browser set content-type boundary
  } else if (body !== undefined) {
    fetchOptions.headers["Content-Type"] = "application/json";
    fetchOptions.body = JSON.stringify(body);
  }

  let res = await fetch(path, fetchOptions);

  if (res.status === 401 && !path.includes("/auth/")) {
    try {
      await refreshSession();
      res = await fetch(path, fetchOptions);
    } catch {
      // refresh failed — caller will handle the 401
    }
  }

  if (res.status === 204) return null;

  const contentType = res.headers.get("content-type") || "";
  const data = contentType.includes("application/json")
    ? await res.json()
    : await res.text();

  if (!res.ok) {
    const err = new Error(
      typeof data === "object" && data?.detail ? data.detail : "Request failed"
    );
    err.status = res.status;
    err.data = data;
    throw err;
  }

  return data;
}

export const apiGet = (path, opts) => api(path, opts);
export const apiPost = (path, body, opts) => api(path, { ...opts, method: "POST", body });
export const apiPatch = (path, body, opts) => api(path, { ...opts, method: "PATCH", body });
export const apiPut = (path, body, opts) => api(path, { ...opts, method: "PUT", body });
export const apiDelete = (path, opts) => api(path, { ...opts, method: "DELETE" });
export const apiUpload = (path, formData, opts) => api(path, { ...opts, method: "POST", formData });
