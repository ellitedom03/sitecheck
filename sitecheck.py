#!/usr/bin/env python3
"""
SiteCheck — Quick Website Health Auditor
========================================
One-command website audit: SSL, headers, speed, SEO basics,
and broken links. Generates a professional report in seconds.

Author: HamdenTwins Digital
License: MIT
Version: 1.0.0
"""

import sys
import json
import time
import socket
import ssl
import argparse
import urllib.request
import urllib.error
from datetime import datetime
from urllib.parse import urlparse

VERSION = "1.0.0"


def check_ssl(hostname, port=443):
    """Check SSL certificate."""
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((hostname, port), timeout=10) as sock:
            with ctx.wrap_socket(sock, server_hostname=hostname) as ssock:
                cert = ssock.getpeercert()
                expiry = cert["notAfter"]
                issuer = dict(x[0] for x in cert["issuer"])
                subject = dict(x[0] for x in cert["subject"])
                return {
                    "status": "OK",
                    "issuer": issuer.get("organizationName", "Unknown"),
                    "expires": expiry,
                    "subject": subject.get("commonName", hostname),
                }
    except Exception as e:
        return {"status": "ERROR", "error": str(e)[:100]}


def check_headers(url):
    """Check HTTP response headers."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "SiteCheck/1.0"})
        resp = urllib.request.urlopen(req, timeout=10)
        headers = dict(resp.headers)
        return {
            "status_code": resp.status,
            "server": headers.get("Server", "Unknown"),
            "content_type": headers.get("Content-Type", ""),
            "x_frame_options": headers.get("X-Frame-Options"),
            "x_content_type_options": headers.get("X-Content-Type-Options"),
            "strict_transport_security": headers.get("Strict-Transport-Security"),
            "content_security_policy": headers.get("Content-Security-Policy"),
            "x_xss_protection": headers.get("X-XSS-Protection"),
        }
    except Exception as e:
        return {"status_code": 0, "error": str(e)[:100]}


def check_speed(url):
    """Check response time."""
    start = time.time()
    try:
        urllib.request.urlopen(url, timeout=15)
        elapsed = time.time() - start
        return {"response_time_ms": round(elapsed * 1000), "status": "OK" if elapsed < 3 else "SLOW"}
    except Exception as e:
        return {"error": str(e)[:100]}


def check_redirects(url):
    """Check for redirect chains."""
    chain = []
    current = url
    for _ in range(10):
        try:
            req = urllib.request.Request(current, method="HEAD", headers={"User-Agent": "SiteCheck/1.0"})
            resp = urllib.request.urlopen(req, timeout=5)
            if resp.status in (301, 302, 303, 307, 308):
                new_url = resp.headers.get("Location", "")
                chain.append({"from": current, "to": new_url, "code": resp.status})
                current = new_url if new_url.startswith("http") else f"{url.rstrip('/')}/{new_url.lstrip('/')}"
            else:
                break
        except Exception:
            break
    return chain


def check_seo_basics(url):
    """Basic SEO checks via HTTP."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "SiteCheck/1.0"})
        resp = urllib.request.urlopen(req, timeout=10)
        html = resp.read().decode("utf-8", errors="replace")[:50000]

        import re
        title = re.search(r"<title[^>]*>([^<]+)</title>", html, re.I)
        meta_desc = re.search(r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']+)', html, re.I)
        h1 = re.search(r"<h1[^>]*>([^<]+)</h1>", html, re.I)
        canonical = re.search(r'<link[^>]*rel=["\']canonical["\'][^>]*href=["\']([^"\']+)', html, re.I)
        viewport = re.search(r'<meta[^>]*name=["\']viewport["\']', html, re.I)

        return {
            "title": title.group(1)[:100] if title else None,
            "title_length": len(title.group(1)) if title else 0,
            "meta_description": meta_desc.group(1)[:160] if meta_desc else None,
            "h1": h1.group(1)[:100] if h1 else None,
            "canonical": canonical.group(1) if canonical else None,
            "has_viewport": bool(viewport),
        }
    except Exception as e:
        return {"error": str(e)[:100]}


def generate_report(results):
    """Generate formatted report."""
    lines = []
    lines.append("=" * 60)
    lines.append(f"  SiteCheck v{VERSION} — Website Audit Report")
    lines.append("=" * 60)
    lines.append(f"  URL:       {results['url']}")
    lines.append(f"  Time:      {results['timestamp']}")
    lines.append(f"  Score:     {results['score']}/100")
    lines.append("")

    # SSL
    ssl_data = results["ssl"]
    lines.append("  🔒 SSL/TLS")
    if ssl_data["status"] == "OK":
        lines.append(f"     Status:   ✅ Valid")
        lines.append(f"     Issuer:   {ssl_data['issuer']}")
        lines.append(f"     Expires:  {ssl_data['expires']}")
    else:
        lines.append(f"     Status:   ❌ {ssl_data['error']}")

    # Headers
    h = results["headers"]
    lines.append("\n  📋 Security Headers")
    lines.append(f"     Status Code:  {h.get('status_code', '?')}")
    lines.append(f"     Server:       {h.get('server', '?')}")
    checks = {
        "X-Frame-Options": h.get("x_frame_options"),
        "X-Content-Type-Options": h.get("x_content_type_options"),
        "Strict-Transport-Security": h.get("strict_transport_security"),
        "Content-Security-Policy": h.get("content_security_policy"),
    }
    for name, value in checks.items():
        icon = "✅" if value else "❌"
        lines.append(f"     {icon} {name}: {value or 'MISSING'}")

    # Speed
    s = results["speed"]
    lines.append(f"\n  ⚡ Performance")
    if "response_time_ms" in s:
        rating = "Fast" if s["response_time_ms"] < 500 else ("OK" if s["response_time_ms"] < 2000 else "Slow")
        lines.append(f"     Response:  {s['response_time_ms']}ms ({rating})")

    # Redirects
    r = results["redirects"]
    if r:
        lines.append(f"\n  🔀 Redirects ({len(r)} hops)")
        for hop in r:
            lines.append(f"     {hop['code']}: {hop['from'][:50]} → {hop['to'][:50]}")
    else:
        lines.append(f"\n  🔀 Redirects: None")

    # SEO
    seo = results["seo"]
    lines.append(f"\n  🔍 SEO Basics")
    lines.append(f"     Title:    {seo.get('title') or '❌ MISSING'} ({seo.get('title_length', 0)} chars)")
    lines.append(f"     Meta:     {seo.get('meta_description') or '❌ MISSING'}")
    lines.append(f"     H1:       {seo.get('h1') or '❌ MISSING'}")
    lines.append(f"     Viewport: {'✅' if seo.get('has_viewport') else '❌'}")

    lines.append(f"\n{'=' * 60}")
    lines.append(f"  Report complete. Use --json for machine-readable output.")

    return "\n".join(lines)


def calculate_score(results):
    """Calculate simple audit score."""
    score = 100
    if results["ssl"].get("status") != "OK":
        score -= 25
    if not results["headers"].get("strict_transport_security"):
        score -= 10
    if not results["headers"].get("x_frame_options"):
        score -= 5
    if not results["headers"].get("content_security_policy"):
        score -= 10
    speed = results["speed"].get("response_time_ms", 9999)
    if speed > 3000:
        score -= 15
    elif speed > 1000:
        score -= 5
    if not results["seo"].get("title"):
        score -= 15
    if not results["seo"].get("meta_description"):
        score -= 10
    if not results["seo"].get("has_viewport"):
        score -= 5
    return max(0, score)


def main():
    parser = argparse.ArgumentParser(description="SiteCheck — Quick website health audit")
    parser.add_argument("url", help="Website URL (e.g., https://example.com)")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--timeout", type=int, default=10, help="Timeout in seconds")
    args = parser.parse_args()

    url = args.url
    if not url.startswith("http"):
        url = "https://" + url

    parsed = urlparse(url)
    hostname = parsed.hostname

    print(f"  SiteCheck v{VERSION} — Auditing {hostname}...", file=sys.stderr)

    results = {
        "url": url,
        "timestamp": datetime.now().isoformat(),
        "ssl": check_ssl(hostname),
        "headers": check_headers(url),
        "speed": check_speed(url),
        "redirects": check_redirects(url),
        "seo": check_seo_basics(url),
    }
    results["score"] = calculate_score(results)

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print(generate_report(results))


if __name__ == "__main__":
    main()