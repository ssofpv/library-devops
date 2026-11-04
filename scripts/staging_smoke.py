"""Check a running staging release through its HTTP interface."""

import argparse
import getpass
import http.cookiejar
import json
import os
import re
import sys
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPCookieProcessor, Request, build_opener


class TableRows(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows = []
        self.current = None

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self.current = []

    def handle_data(self, data):
        if self.current is not None:
            self.current.append(data)

    def handle_endtag(self, tag):
        if tag == "tr" and self.current is not None:
            self.rows.append(" ".join(" ".join(self.current).split()))
            self.current = None


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def check_release(base, revision, username, password):
    cookies = http.cookiejar.CookieJar()
    client = build_opener(HTTPCookieProcessor(cookies))

    def fetch(path, data=None):
        request = Request(base + path, data=data)
        with client.open(request, timeout=10) as response:
            require(response.status == 200, "Unexpected HTTP status")
            return response.geturl(), response.read().decode("utf-8")

    _, body = fetch("/health/")
    require(json.loads(body) == {"status": "ok"}, "Health check failed")
    print("Health: OK")

    _, body = fetch("/version/")
    require(json.loads(body) == {"version": revision}, "Release SHA does not match")
    print(f"Version: {revision}")

    _, body = fetch("/accounts/login/")
    token = next((cookie.value for cookie in cookies if cookie.name == "csrftoken"), None)
    require(token is not None, "Login page did not set a CSRF cookie")
    login_data = urlencode(
        {
            "username": username,
            "password": password,
            "csrfmiddlewaretoken": token,
            "next": "/copies/",
        }
    ).encode("utf-8")
    fetch("/accounts/login/", login_data)
    require(
        any(cookie.name == "sessionid" for cookie in cookies),
        "Login did not create a session; check credentials",
    )

    final_url, body = fetch("/copies/")
    require(final_url == base + "/copies/", "Copies page redirected unexpectedly")
    table = TableRows()
    table.feed(body)
    expected = ["LR6-001", "Проверка релиза ЛР6", "Тестовый филиал ЛР6", "Доступен"]
    require(
        any(all(value in row for value in expected) for row in table.rows),
        "LR6-001 or its expected book, branch or status is missing",
    )
    print("User scenario (login and view LR6-001): OK")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("revision", help="Expected full commit SHA")
    parser.add_argument("--base-url", default="http://192.168.56.10:18000")
    args = parser.parse_args()
    require(re.fullmatch(r"[0-9a-f]{40}", args.revision), "Expected a full lowercase SHA")
    base = args.base_url.rstrip("/")
    url = urlsplit(base)
    require(
        url.scheme in {"http", "https"}
        and url.hostname
        and not url.username
        and not url.password
        and not url.query
        and not url.fragment
        and not url.path,
        "Base URL must contain only a scheme, hostname and optional port",
    )
    username = os.environ.get("STAGING_SMOKE_USER")
    password = os.environ.get("STAGING_SMOKE_PASSWORD")
    if not username:
        require(sys.stdin.isatty(), "STAGING_SMOKE_USER is required")
        username = input("Staging application username: ")
    if not password:
        require(sys.stdin.isatty(), "STAGING_SMOKE_PASSWORD is required")
        password = getpass.getpass("Staging application password: ")
    check_release(base, args.revision, username, password)
    print("RELEASE ACCEPTED")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, ValueError, HTTPError, URLError, TimeoutError, OSError) as error:
        # Do not print response bodies, credentials or session cookies into CD logs.
        detail = str(error) if isinstance(error, RuntimeError) else type(error).__name__
        print(f"RELEASE REJECTED: {detail}", file=sys.stderr)
        sys.exit(1)
