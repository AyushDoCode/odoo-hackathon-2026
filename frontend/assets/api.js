// AssetFlow API client. Loaded by every page via <script src="assets/api.js">.
// Exposes a single global, window.AssetFlowAPI, used by each page's inline script.
(function () {
    "use strict";

    // The API is served by the same process as this page (mounted under /api),
    // so a relative path is enough -- no host/port to hardcode. Override by
    // setting `window.ASSETFLOW_API_BASE_URL` in a <script> tag before this file
    // loads if the API is ever split onto a different origin.
    const API_BASE_URL = window.ASSETFLOW_API_BASE_URL || "/api";

    const TOKEN_KEY = "assetflow_token";
    const USER_KEY = "assetflow_user";

    function getToken() {
        return localStorage.getItem(TOKEN_KEY);
    }

    function getUser() {
        const raw = localStorage.getItem(USER_KEY);
        if (!raw) return null;
        try {
            return JSON.parse(raw);
        } catch (err) {
            return null;
        }
    }

    function storeSession(token, user) {
        localStorage.setItem(TOKEN_KEY, token);
        localStorage.setItem(USER_KEY, JSON.stringify(user));
    }

    function clearSession() {
        localStorage.removeItem(TOKEN_KEY);
        localStorage.removeItem(USER_KEY);
    }

    // Redirects to the login page if there's no session. Call at the top of every
    // authenticated page, before rendering any data.
    function requireAuth() {
        if (!getToken()) {
            window.location.href = "login.html";
        }
    }

    function logout() {
        clearSession();
        window.location.href = "login.html";
    }

    // Generic fetch wrapper: prefixes the API base URL, attaches the bearer token,
    // parses JSON, and throws an Error with the backend's `detail` message on failure.
    // `path` is a route like "/dashboard/summary"; `options` matches native fetch().
    async function fetchApi(path, options = {}) {
        const headers = Object.assign({}, options.headers || {});
        const token = getToken();
        if (token) {
            headers["Authorization"] = "Bearer " + token;
        }
        const hasBody = options.body !== undefined && options.body !== null;
        if (hasBody && !headers["Content-Type"] && !(options.body instanceof FormData)) {
            headers["Content-Type"] = "application/json";
        }

        let response;
        try {
            response = await fetch(API_BASE_URL + path, Object.assign({}, options, { headers }));
        } catch (networkError) {
            throw new Error("Could not reach the AssetFlow server. Is the backend running?");
        }

        if (response.status === 401) {
            clearSession();
            window.location.href = "login.html";
            throw new Error("Session expired. Please sign in again.");
        }

        if (response.status === 204) {
            return null;
        }

        const contentType = response.headers.get("content-type") || "";
        const payload = contentType.includes("application/json")
            ? await response.json().catch(() => null)
            : await response.text();

        if (!response.ok) {
            const detail =
                payload && typeof payload === "object" && "detail" in payload
                    ? payload.detail
                    : typeof payload === "string" && payload
                    ? payload
                    : `Request failed (${response.status})`;
            throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
        }

        return payload;
    }

    // POST helper for JSON bodies -- the common case for every mutating call.
    function postJson(path, body) {
        return fetchApi(path, { method: "POST", body: JSON.stringify(body || {}) });
    }

    function patchJson(path, body) {
        return fetchApi(path, { method: "PATCH", body: JSON.stringify(body || {}) });
    }

    async function login(email, password) {
        const token = await fetchApi("/auth/login", {
            method: "POST",
            body: JSON.stringify({ email, password }),
        });
        const user = await fetchApi("/auth/me", {
            headers: { Authorization: "Bearer " + token.access_token },
        });
        storeSession(token.access_token, user);
        return user;
    }

    async function signup(name, email, password) {
        await postJson("/auth/signup", { name, email, password });
        // Signup creates an Employee account with no session -- sign in right away
        // so the user lands in the app instead of back at the login form.
        return login(email, password);
    }

    window.AssetFlowAPI = {
        API_BASE_URL,
        fetchApi,
        postJson,
        patchJson,
        login,
        signup,
        logout,
        requireAuth,
        getUser,
        getToken,
    };
})();
