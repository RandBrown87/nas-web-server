import re
import urllib.parse
from flask import request, jsonify
from app.database import get_db

# OWASP Core Rule Set Attack Signature Patterns
SQLI_PATTERNS = [
    re.compile(r"(\%27)|(\')|(\-\-)|(\%23)|(#)", re.IGNORECASE),
    re.compile(r"\b(union(\s+all)?\s+select)\b", re.IGNORECASE),
    re.compile(r"\b(select\s+.+\s+from\s+.+)\b", re.IGNORECASE),
    re.compile(r"\b(insert\s+into\s+.+\s+values)\b", re.IGNORECASE),
    re.compile(r"\b(drop\s+table|drop\s+database|truncate\s+table)\b", re.IGNORECASE),
    re.compile(r"\b(sleep\s*\(|benchmark\s*\(|load_file\s*\()\b", re.IGNORECASE),
    re.compile(r"(\bor\b|\band\b)\s+[\'\"]?\w+[\'\"]?\s*=\s*[\'\"]?\w+", re.IGNORECASE)
]

XSS_PATTERNS = [
    re.compile(r"<\s*script[^>]*>", re.IGNORECASE),
    re.compile(r"javascript\s*:", re.IGNORECASE),
    re.compile(r"vbscript\s*:", re.IGNORECASE),
    re.compile(r"on(load|error|click|mouseover|submit|focus|blur)\s*=", re.IGNORECASE),
    re.compile(r"<\s*iframe[^>]*>", re.IGNORECASE),
    re.compile(r"<\s*svg[^>]*onload\s*=", re.IGNORECASE)
]

TRAVERSAL_PATTERNS = [
    re.compile(r"(\.\./|\.\.\\|%2e%2e%2f|%2e%2e\/)", re.IGNORECASE),
    re.compile(r"(/etc/passwd|/etc/shadow|/etc/group|/windows/win.ini)", re.IGNORECASE)
]

RCE_PATTERNS = [
    re.compile(r"(;\s*(/bin/|/usr/bin/)?(sh|bash|cat|rm|whoami|id|curl|wget)\b)", re.IGNORECASE),
    re.compile(r"(\|\s*(/bin/|/usr/bin/)?(sh|bash|curl|wget)\b)", re.IGNORECASE),
    re.compile(r"(\$\(.*\)|`.*`)", re.IGNORECASE)
]

SCANNER_USER_AGENTS = [
    'sqlmap', 'nikto', 'acunetix', 'masscan', 'nessus', 'nmap', 'dirbuster', 'gobuster'
]

def log_waf_attack(ip, endpoint, attack_type, payload_sample):
    """Logs blocked security incident to MySQL waf_logs table."""
    try:
        conn = get_db()
        cursor = conn.cursor()
        sample_truncated = str(payload_sample)[:250] if payload_sample else ''
        cursor.execute(
            "INSERT INTO waf_logs (ip_address, endpoint, attack_type, payload_sample) VALUES (%s, %s, %s, %s)",
            (ip, endpoint, attack_type, sample_truncated)
        )
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"WAF logging error: {e}")

def inspect_value(val):
    """Inspects a string value against WAF signatures."""
    if not isinstance(val, str) or not val:
        return None

    # Unquote URL encoding once
    decoded = urllib.parse.unquote(val)

    # Check RCE
    for pattern in RCE_PATTERNS:
        if pattern.search(decoded):
            return ('Command Injection', val)

    # Check Traversal
    for pattern in TRAVERSAL_PATTERNS:
        if pattern.search(decoded):
            return ('Path Traversal', val)

    # Check XSS
    for pattern in XSS_PATTERNS:
        if pattern.search(decoded):
            return ('Cross-Site Scripting (XSS)', val)

    # Check SQLi
    for pattern in SQLI_PATTERNS:
        if pattern.search(decoded):
            return ('SQL Injection (SQLi)', val)

    return None

def init_waf(app):
    """Registers WAF middleware with Flask application."""
    @app.before_request
    def waf_before_request():
        # Whitelist static assets
        if request.path.startswith('/static/'):
            return None

        client_ip = request.headers.get('X-Forwarded-For', request.remote_addr or '127.0.0.1').split(',')[0].strip()
        user_agent = request.headers.get('User-Agent', '').lower()

        # Check malicious scanners
        for scanner in SCANNER_USER_AGENTS:
            if scanner in user_agent:
                log_waf_attack(client_ip, request.path, 'Malicious Scanner', user_agent)
                return jsonify({
                    'error': 'Request blocked by Web Application Firewall (WAF)',
                    'reason': 'Automated Vulnerability Scanner Blocked',
                    'blocked': True
                }), 403

        # Check URL Query string
        for k, v in request.args.items():
            hit = inspect_value(v)
            if hit:
                log_waf_attack(client_ip, request.path, hit[0], f"{k}={hit[1]}")
                return jsonify({
                    'error': 'Request blocked by Web Application Firewall (WAF)',
                    'attack_type': hit[0],
                    'blocked': True
                }), 403

        # Check Form Body
        if request.form:
            for k, v in request.form.items():
                # Allow standard passwords to have special characters without false positives
                if k in ['password', 'confirm_password']:
                    continue
                hit = inspect_value(v)
                if hit:
                    log_waf_attack(client_ip, request.path, hit[0], f"{k}={hit[1]}")
                    return jsonify({
                        'error': 'Request blocked by Web Application Firewall (WAF)',
                        'attack_type': hit[0],
                        'blocked': True
                    }), 403

        # Check JSON Body
        if request.is_json:
            json_data = request.get_json(silent=True) or {}
            if isinstance(json_data, dict):
                for k, v in json_data.items():
                    if k in ['password', 'confirm_password', 'content']:  # file content editor exempt from WAF rule
                        continue
                    if isinstance(v, str):
                        hit = inspect_value(v)
                        if hit:
                            log_waf_attack(client_ip, request.path, hit[0], f"{k}={hit[1]}")
                            return jsonify({
                                'error': 'Request blocked by Web Application Firewall (WAF)',
                                'attack_type': hit[0],
                                'blocked': True
                            }), 403

        return None
