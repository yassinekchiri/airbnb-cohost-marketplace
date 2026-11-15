#!/usr/bin/env python3
"""Black-box smoke test: public pages, then register -> login -> role dashboard.

Stdlib only so it runs anywhere (CI, the NUC, a laptop). Exit code 1 on first failure.
Usage: smoke.py BASE_URL [--readonly]   (--readonly: skip registration, for production)
"""
import http.cookiejar
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request


def main(base: str, readonly: bool = False) -> int:
    base = base.rstrip("/")
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    failures = []

    def get(path, expect=200):
        try:
            r = opener.open(base + path, timeout=15)
            code, body = r.status, r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            code, body = e.code, e.read().decode("utf-8", "replace")
        ok = code == expect
        print(f"{'ok  ' if ok else 'FAIL'} GET {path} -> {code} (want {expect})")
        if not ok:
            failures.append(path)
        return body

    def csrf():
        return next((c.value for c in jar if c.name == "csrftoken"), "")

    def post(path, data, expect_final=200):
        data = {**data, "csrfmiddlewaretoken": csrf()}
        req = urllib.request.Request(base + path, urllib.parse.urlencode(data).encode(),
                                     {"Referer": base + path})
        try:
            r = opener.open(req, timeout=15)
            code, url, body = r.status, r.geturl(), r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            code, url, body = e.code, base + path, ""
        ok = code == expect_final
        print(f"{'ok  ' if ok else 'FAIL'} POST {path} -> {code} {url.replace(base, '')}")
        if not ok:
            failures.append("POST " + path)
        return url, body

    # 1. public pages
    get("/healthz", expect=404 if readonly else 200)  # must NOT be public in production
    for p in ["/", "/listings/", "/cohosts/", "/login/", "/register/", "/privacy/", "/terms/", "/contact/"]:
        get(p)
    get("/definitely-not-a-page/", expect=404)
    css = re.search(r'/static/[^"\']+\.css', get("/login/"))
    if css:
        get(css.group(0))

    if readonly:
        print("\nSMOKE FAILED: " + ", ".join(failures) if failures else "\nSMOKE PASSED (read-only)")
        return 1 if failures else 0

    # 2. register -> login -> host dashboard
    user = f"smoke{int(time.time())}"
    password = "Smoke-test-pass-9X!"
    get("/register/")
    post("/register/", {"username": user, "first_name": "Smoke", "last_name": "Test",
                        "email": f"{user}@example.com", "password1": password, "password2": password,
                        "role": "host", "phone_number": ""})
    get("/login/")
    url, _ = post("/login/", {"username": user, "password": password})
    if "/host/dashboard" not in url and "/cohosts" not in url:
        print(f"FAIL login did not land on a host page: {url}")
        failures.append("login")
    get("/host/dashboard/")

    print("\nSMOKE FAILED: " + ", ".join(failures) if failures else "\nSMOKE PASSED")
    return 1 if failures else 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1], "--readonly" in sys.argv[2:]))
