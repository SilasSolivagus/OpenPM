#!/usr/bin/env python3
"""Wiki synchronization CLI (pull / export / push) for OpenPM workspaces.

Zero external dependencies (Python 3 standard library only).
Supports adapters: local-obsidian, confluence, wecom, feishu.
Automatically loads .env.local without ever logging secrets or tokens.
"""

import argparse
import base64
import datetime
import difflib
import hashlib
import html
import json
import os
import re
import shutil
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
import xml.etree.ElementTree as ET
import zipfile
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple


SUPPORTED_ADAPTERS = {"local-obsidian", "confluence", "wecom", "feishu"}
SECRET_KEY_PATTERN = re.compile(
    r"(SECRET|PAT|TOKEN|PASSWORD|PASSWD|WEBHOOK|API_KEY|ACCESS_KEY|AUTH)",
    re.IGNORECASE,
)
XML_ILLEGAL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).astimezone().isoformat(timespec="seconds")


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _parse_dotenv_file(env_path: Path) -> Dict[str, str]:
    """Parse a .env / .env.local file into key-value pairs."""
    values: Dict[str, str] = {}
    if not env_path.is_file():
        return values
    try:
        raw = env_path.read_text(encoding="utf-8")
    except OSError:
        return values

    for raw_line in raw.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, val = line.split("=", 1)
        key = key.strip()
        val = val.strip()
        if not key:
            continue
        if len(val) >= 2 and val[0] == val[-1] and val[0] in ("'", '"'):
            quote = val[0]
            val = val[1:-1]
            if quote == '"':
                val = val.replace('\\"', '"').replace("\\n", "\n")
        else:
            # Strip inline unquoted comment if preceded by whitespace
            comment_idx = val.find(" #")
            if comment_idx >= 0:
                val = val[:comment_idx].rstrip()
        values[key] = val
    return values


def load_env_config(project_dir: Optional[Path] = None) -> Tuple[Dict[str, str], List[str]]:
    """Merge .env.local from repo root, cwd, project_dir, and os.environ.

    Returns (merged_env, sensitive_values_to_redact).
    """
    repo_root = Path(__file__).resolve().parent.parent
    candidate_files: List[Path] = [
        repo_root / ".env.local",
        Path.cwd() / ".env.local",
    ]
    if project_dir is not None:
        candidate_files.append(project_dir.resolve() / ".env.local")
        candidate_files.append(project_dir.resolve().parent / ".env.local")
        candidate_files.append(project_dir.resolve().parent.parent / ".env.local")

    merged: Dict[str, str] = {}
    seen_paths = set()
    for p in candidate_files:
        try:
            rp = p.resolve()
        except OSError:
            continue
        if rp in seen_paths:
            continue
        seen_paths.add(rp)
        merged.update(_parse_dotenv_file(rp))

    # Explicit OS environment variables take highest priority
    for k, v in os.environ.items():
        if v:
            merged[k] = v

    sensitive_values: List[str] = []
    for k, v in merged.items():
        if v and len(v) >= 4 and SECRET_KEY_PATTERN.search(k):
            sensitive_values.append(v)
    # Sort longest first so full webhook URLs redact before substrings
    sensitive_values.sort(key=len, reverse=True)
    return merged, sensitive_values


def redact_text(message: str, sensitive_values: Sequence[str]) -> str:
    """Scrub any known secret values and URL query keys/tokens from log/error text."""
    out = str(message)
    for sec in sensitive_values:
        if sec and sec in out:
            out = out.replace(sec, "***REDACTED***")
    out = re.sub(
        r"([?&](?:key|token|secret|pat|access_token)=)[^&\s\"']+",
        r"\1***REDACTED***",
        out,
        flags=re.IGNORECASE,
    )
    out = re.sub(
        r"(Bearer\s+)[A-Za-z0-9._~+/=-]+",
        r"\1***REDACTED***",
        out,
        flags=re.IGNORECASE,
    )
    out = re.sub(
        r"(Basic\s+)[A-Za-z0-9+/=]+",
        r"\1***REDACTED***",
        out,
        flags=re.IGNORECASE,
    )
    return out


def _strip_yaml_scalar(val: str) -> str:
    v = val.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in ("'", '"'):
        return v[1:-1].strip()
    comment_pos = v.find(" #")
    if comment_pos >= 0:
        v = v[:comment_pos].strip()
    return v


def parse_project_context(project_dir: Path) -> Dict[str, Any]:
    """Parse YAML frontmatter and wiki_config from <project_dir>/project-context.md."""
    ctx: Dict[str, Any] = {
        "project": project_dir.name,
        "title": project_dir.name,
        "wiki_adapter": "local-obsidian",
        "wiki_config": {},
    }
    ctx_path = project_dir / "project-context.md"
    if not ctx_path.is_file():
        return ctx

    text = ctx_path.read_text(encoding="utf-8")
    fm_match = re.match(r"^---\s*\n(.*?)\n---\s*(?:\n|$)", text, re.DOTALL)
    blocks_to_scan: List[str] = []
    if fm_match:
        blocks_to_scan.append(fm_match.group(1))
    # Also scan fenced yaml blocks if wiki_config is placed in markdown body
    for code_match in re.finditer(r"```ya?ml\s*\n(.*?)\n```", text, re.DOTALL):
        blocks_to_scan.append(code_match.group(1))

    for block in blocks_to_scan:
        in_wiki_cfg = False
        wiki_cfg_indent = 0
        for raw_line in block.splitlines():
            if not raw_line.strip() or raw_line.lstrip().startswith("#"):
                continue
            indent = len(raw_line) - len(raw_line.lstrip(" "))
            stripped = raw_line.strip()
            if in_wiki_cfg:
                if indent > wiki_cfg_indent and ":" in stripped:
                    ck, cv = stripped.split(":", 1)
                    ctx["wiki_config"][ck.strip()] = _strip_yaml_scalar(cv)
                    continue
                in_wiki_cfg = False

            if ":" not in stripped:
                continue
            k, v = stripped.split(":", 1)
            k = k.strip()
            v_clean = _strip_yaml_scalar(v)
            if k == "wiki_config" and not v_clean:
                in_wiki_cfg = True
                wiki_cfg_indent = indent
                continue
            if k in ("wiki_adapter", "adapter") and v_clean:
                # Prefer explicit wiki_adapter over fallback adapter
                if k == "wiki_adapter" or ctx.get("_adapter_explicit") is not True:
                    ctx["wiki_adapter"] = v_clean.lower()
                    if k == "wiki_adapter":
                        ctx["_adapter_explicit"] = True
            elif v_clean:
                ctx[k] = v_clean

    ctx.pop("_adapter_explicit", None)
    if ctx["wiki_adapter"] not in SUPPORTED_ADAPTERS:
        ctx["wiki_adapter"] = "local-obsidian"
    return ctx


def load_manifest(project_dir: Path) -> Dict[str, Any]:
    manifest_path = project_dir / "_manifest.json"
    if not manifest_path.is_file():
        return {}
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_manifest(project_dir: Path, data: Dict[str, Any]) -> Path:
    manifest_path = project_dir / "_manifest.json"
    manifest_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest_path


class _ConfluenceStorageToMdParser(HTMLParser):
    """Lightweight HTML/Storage-XML to Markdown converter for Confluence pull."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.lines: List[str] = []
        self._buf: List[str] = []
        self._in_list_depth = 0
        self._in_table = False
        self._table_rows: List[List[str]] = []
        self._cur_row: List[str] = []
        self._in_cell = False
        self._cell_buf: List[str] = []
        self._in_pre = False

    def _flush_paragraph(self, prefix: str = "", suffix: str = "") -> None:
        txt = "".join(self._buf).strip()
        self._buf = []
        if txt:
            self.lines.append(f"{prefix}{txt}{suffix}")

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        t = tag.lower()
        if t in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self._flush_paragraph()
        elif t == "p":
            if not self._in_cell:
                self._flush_paragraph()
        elif t == "br":
            if self._in_cell:
                self._cell_buf.append(" ")
            else:
                self._buf.append("\n")
        elif t in ("ul", "ol"):
            if not self._in_cell:
                self._flush_paragraph()
            self._in_list_depth += 1
        elif t == "li":
            if self._in_cell:
                self._cell_buf.append("• ")
            else:
                self._flush_paragraph()
        elif t in ("strong", "b"):
            (self._cell_buf if self._in_cell else self._buf).append("**")
        elif t == "code":
            (self._cell_buf if self._in_cell else self._buf).append("`")
        elif t == "pre":
            self._flush_paragraph()
            self._in_pre = True
        elif t == "table":
            if not self._in_cell:
                self._flush_paragraph()
                self._in_table = True
                self._table_rows = []
        elif t == "tr" and self._in_table:
            self._cur_row = []
        elif t in ("th", "td") and self._in_table:
            self._in_cell = True
            self._cell_buf = []
        elif t == "hr" and not self._in_cell:
            self._flush_paragraph()
            self.lines.append("---")

    def handle_endtag(self, tag: str) -> None:
        t = tag.lower()
        if t in ("h1", "h2", "h3", "h4", "h5", "h6"):
            level = int(t[1])
            self._flush_paragraph(prefix="#" * level + " ")
            self.lines.append("")
        elif t == "p":
            if self._in_cell:
                self._cell_buf.append(" ")
            else:
                self._flush_paragraph()
                self.lines.append("")
        elif t == "li":
            if not self._in_cell:
                indent = "  " * max(0, self._in_list_depth - 1)
                self._flush_paragraph(prefix=f"{indent}- ")
        elif t in ("ul", "ol"):
            self._in_list_depth = max(0, self._in_list_depth - 1)
            if self._in_list_depth == 0 and not self._in_cell:
                self.lines.append("")
        elif t in ("strong", "b"):
            (self._cell_buf if self._in_cell else self._buf).append("**")
        elif t == "code":
            (self._cell_buf if self._in_cell else self._buf).append("`")
        elif t == "pre":
            code_txt = "".join(self._buf).strip("\n")
            self._buf = []
            self._in_pre = False
            self.lines.append(f"```\n{code_txt}\n```\n")
        elif t in ("th", "td") and self._in_table and self._in_cell:
            cell_txt = re.sub(r"\s+", " ", "".join(self._cell_buf)).strip().replace("|", "\\|")
            self._cur_row.append(cell_txt)
            self._in_cell = False
            self._cell_buf = []
        elif t == "tr" and self._in_table:
            if self._cur_row:
                self._table_rows.append(self._cur_row)
            self._cur_row = []
        elif t == "table" and self._in_table:
            self._in_table = False
            if self._table_rows:
                col_cnt = max(len(r) for r in self._table_rows)
                for idx, row in enumerate(self._table_rows):
                    padded = row + [""] * (col_cnt - len(row))
                    self.lines.append("| " + " | ".join(padded) + " |")
                    if idx == 0:
                        self.lines.append("| " + " | ".join(["---"] * col_cnt) + " |")
                self.lines.append("")

    def handle_data(self, data: str) -> None:
        if self._in_cell:
            self._cell_buf.append(data)
        elif self._in_pre:
            self._buf.append(data)
        else:
            self._buf.append(re.sub(r"[ \t\r\n]+", " ", data))


def storage_to_markdown(storage_html: str, title: Optional[str] = None) -> str:
    """Convert Confluence storage format XHTML into clean Markdown."""
    cleaned = re.sub(r"<!\[CDATA\[(.*?)\]\]>", lambda m: html.escape(m.group(1)), storage_html, flags=re.DOTALL)
    parser = _ConfluenceStorageToMdParser()
    parser.feed(cleaned)
    parser._flush_paragraph()
    parser.close()

    body = "\n".join(parser.lines)
    body = re.sub(r"\n{3,}", "\n\n", body).strip()
    if title and not body.startswith(f"# {title}"):
        body = f"# {title}\n\n{body}".strip()
    return body + "\n"


def _confluence_headers(env: Dict[str, str], content_type: str = "application/json") -> Dict[str, str]:
    pat = env.get("CONFLUENCE_PAT", "").strip()
    user = (env.get("CONFLUENCE_USER") or env.get("CONFLUENCE_EMAIL") or "").strip()
    if user:
        token = base64.b64encode(f"{user}:{pat}".encode("utf-8")).decode("ascii")
        auth = f"Basic {token}"
    else:
        auth = f"Bearer {pat}"
    headers = {
        "Authorization": auth,
        "Accept": "application/json",
    }
    if content_type:
        headers["Content-Type"] = content_type
    return headers


def _http_json_request(
    url: str,
    method: str,
    headers: Dict[str, str],
    payload: Optional[Dict[str, Any]] = None,
    timeout: int = 20,
) -> Dict[str, Any]:
    body_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url=url, data=body_bytes, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
        return json.loads(raw) if raw.strip() else {}


def _upload_confluence_attachment(
    base_url: str,
    page_id: str,
    file_path: Path,
    env: Dict[str, str],
) -> bool:
    """Best-effort upload/update of an attachment on a Confluence page."""
    boundary = f"----OpenPMBoundary{uuid.uuid4().hex}"
    filename = file_path.name
    file_bytes = file_path.read_bytes()

    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        f"Content-Type: application/octet-stream\r\n\r\n"
    ).encode("utf-8") + file_bytes + f"\r\n--{boundary}--\r\n".encode("utf-8")

    headers = _confluence_headers(env, content_type=f"multipart/form-data; boundary={boundary}")
    headers["X-Atlassian-Token"] = "nocheck"

    url = f"{base_url.rstrip('/')}/rest/api/content/{urllib.parse.quote(str(page_id))}/child/attachment"
    req = urllib.request.Request(url=url, data=body, headers=headers, method="PUT")
    try:
        with urllib.request.urlopen(req, timeout=30):
            return True
    except urllib.error.HTTPError as exc:
        if exc.code in (404, 405):
            # Fallback to POST for older Confluence versions or minimal mock servers
            try:
                req_post = urllib.request.Request(url=url, data=body, headers=headers, method="POST")
                with urllib.request.urlopen(req_post, timeout=30):
                    return True
            except Exception:
                return False
        return False
    except Exception:
        return False


def _pick_latest_md(directory: Path, exclude_names: Optional[set] = None) -> Optional[Path]:
    if not directory.is_dir():
        return None
    excl = exclude_names or set()
    candidates = [
        p for p in directory.iterdir()
        if p.is_file() and p.suffix.lower() == ".md" and p.name not in excl and not p.name.startswith(".")
    ]
    if not candidates:
        return None
    # Sort by mtime ascending, breaking ties with natural version/name ordering
    def _sort_key(p: Path) -> Tuple[float, List[Any]]:
        parts = [int(tok) if tok.isdigit() else tok.lower() for tok in re.split(r"(\d+)", p.name)]
        return (p.stat().st_mtime, parts)

    candidates.sort(key=_sort_key)
    return candidates[-1]


def _write_pull_diff(remote_md_path: Path, local_prd_path: Path, diff_out_path: Path) -> bool:
    """Generate unified diff markdown at history/pull-diff.md using difflib."""
    remote_lines = remote_md_path.read_text(encoding="utf-8").splitlines(keepends=True)
    local_lines = local_prd_path.read_text(encoding="utf-8").splitlines(keepends=True)

    diff_lines = list(
        difflib.unified_diff(
            remote_lines,
            local_lines,
            fromfile="history/prd-remote.md (remote)",
            tofile="prd.md (local)",
        )
    )
    added = sum(1 for ln in diff_lines if ln.startswith("+") and not ln.startswith("+++"))
    removed = sum(1 for ln in diff_lines if ln.startswith("-") and not ln.startswith("---"))

    diff_out_path.parent.mkdir(parents=True, exist_ok=True)
    if not diff_lines:
        content = (
            "# Pull Diff 对比报告\n\n"
            f"- **生成时间**：`{_now_iso()}`\n"
            "- **对比结论**：本地 `prd.md` 与远端基线 `history/prd-remote.md` 完全一致（0 处差异）。\n"
        )
        diff_out_path.write_text(content, encoding="utf-8")
        return False

    diff_body = "".join(diff_lines)
    if not diff_body.endswith("\n"):
        diff_body += "\n"
    content = (
        "# Pull Diff 对比报告\n\n"
        f"- **生成时间**：`{_now_iso()}`\n"
        f"- **变更统计**：本地相对远端新增 `+{added}` 行，移除 `-{removed}` 行\n\n"
        "```diff\n"
        f"{diff_body}"
        "```\n"
    )
    diff_out_path.write_text(content, encoding="utf-8")
    return True


def cmd_pull(project_dir: Path, page_id_override: Optional[str] = None) -> int:
    if not project_dir.is_dir():
        print(f"ERROR: Project directory not found: {project_dir}", file=sys.stderr)
        return 1

    env, secrets = load_env_config(project_dir)
    ctx = parse_project_context(project_dir)
    manifest = load_manifest(project_dir)
    adapter = ctx["wiki_adapter"]
    wiki_cfg = ctx.get("wiki_config") or {}

    base_url = (env.get("WIKI_BASE_URL") or wiki_cfg.get("base_url") or "").strip()
    confluence_pat = env.get("CONFLUENCE_PAT", "").strip()
    page_id = (
        (page_id_override or "").strip()
        or str(wiki_cfg.get("page_id") or "").strip()
        or str(manifest.get("remote_page_id") or "").strip()
        or env.get("CONFLUENCE_PAGE_ID", "").strip()
    )

    history_dir = project_dir / "history"
    history_dir.mkdir(parents=True, exist_ok=True)
    remote_md_path = history_dir / "prd-remote.md"

    try:
        if adapter == "confluence" and base_url and confluence_pat:
            if not page_id:
                print(
                    "ERROR: Confluence pull requires a page ID (--page-id, project-context.md wiki_config.page_id, or _manifest.json).",
                    file=sys.stderr,
                )
                return 1
            api_url = (
                f"{base_url.rstrip('/')}/rest/api/content/"
                f"{urllib.parse.quote(page_id)}?expand=body.storage,version"
            )
            resp = _http_json_request(api_url, "GET", _confluence_headers(env))
            storage_val = (((resp.get("body") or {}).get("storage") or {}).get("value")) or ""
            remote_title = resp.get("title") or ctx.get("title")
            ver_num = int(((resp.get("version") or {}).get("number")) or 1)

            md_text = storage_to_markdown(storage_val, title=remote_title)
            remote_md_path.write_text(md_text, encoding="utf-8")

            manifest.update(
                {
                    "adapter": "confluence",
                    "remote_page_id": str(page_id),
                    "remote_version": ver_num,
                    "pulled_at": _now_iso(),
                }
            )
            save_manifest(project_dir, manifest)
            print(f"[wiki_sync] Pulled Confluence page {page_id} (v{ver_num}) -> {remote_md_path}")
        else:
            wiki_remote_dir = project_dir / "wiki-remote"
            source_md = _pick_latest_md(wiki_remote_dir)
            remote_ver = int(manifest.get("remote_version") or 1)

            remote_meta_path = wiki_remote_dir / "_remote_meta.json"
            if remote_meta_path.is_file():
                try:
                    rmeta = json.loads(remote_meta_path.read_text(encoding="utf-8"))
                    if isinstance(rmeta.get("remote_version"), int):
                        remote_ver = rmeta["remote_version"]
                except Exception:
                    pass
            elif source_md is not None:
                v_match = re.search(r"-v(\d+)\.md$", source_md.name, re.IGNORECASE)
                if v_match:
                    remote_ver = max(remote_ver, int(v_match.group(1)))

            if source_md is None:
                # Fallback to baseline/ or existing history/*.md or local prd.md
                source_md = _pick_latest_md(project_dir / "baseline", exclude_names={"pull-diff.md"})
            if source_md is None:
                source_md = _pick_latest_md(history_dir, exclude_names={"prd-remote.md", "pull-diff.md"})
            if source_md is None and (project_dir / "prd.md").is_file():
                source_md = project_dir / "prd.md"

            if source_md is None:
                print(
                    f"ERROR: No remote/baseline Markdown found in {wiki_remote_dir} or {project_dir}.",
                    file=sys.stderr,
                )
                return 1

            remote_md_path.write_text(source_md.read_text(encoding="utf-8"), encoding="utf-8")
            manifest.update(
                {
                    "adapter": adapter,
                    "remote_page_id": str(page_id or source_md.stem),
                    "remote_version": remote_ver,
                    "pulled_at": _now_iso(),
                }
            )
            save_manifest(project_dir, manifest)
            print(f"[wiki_sync] Pulled baseline from {source_md} (v{remote_ver}) -> {remote_md_path}")

        local_prd = project_dir / "prd.md"
        if local_prd.is_file():
            diff_path = history_dir / "pull-diff.md"
            has_changes = _write_pull_diff(remote_md_path, local_prd, diff_path)
            status_str = "differences recorded" if has_changes else "identical"
            print(f"[wiki_sync] Generated diff ({status_str}) -> {diff_path}")
        return 0

    except Exception as exc:
        safe_err = redact_text(str(exc), secrets)
        print(f"ERROR: Pull failed ({adapter}): {safe_err}", file=sys.stderr)
        return 1


def _xml_escape(text: Any) -> str:
    """Escape text safely for strict XML 1.0 (only built-in XML entities, no illegal control chars)."""
    s = XML_ILLEGAL_CHARS_RE.sub("", str(text if text is not None else ""))
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


SAFE_INLINE_TABLE_TAGS = {"table", "thead", "tbody", "tr", "th", "td", "strong", "b", "code", "br", "span"}


def _sanitize_inline_table_xhtml(raw_table: str) -> Optional[str]:
    """Return normalized well-formed XHTML if raw_table is a safe inline <table>, else None."""
    normalized = re.sub(r"<br\s*/?>", "<br />", raw_table, flags=re.IGNORECASE)
    try:
        elem = ET.fromstring(normalized)
    except ET.ParseError:
        return None
    for node in elem.iter():
        if node.tag.lower() not in SAFE_INLINE_TABLE_TAGS:
            return None
        for attr_k in list(node.attrib.keys()):
            if attr_k.lower().startswith("on") or attr_k.lower() == "style":
                del node.attrib[attr_k]
    return ET.tostring(elem, encoding="unicode", method="xml")


def _format_inline_xhtml(text: str) -> str:
    """Convert inline Markdown (`code`, **bold**, <br>, and well-formed single-line <table>) to strict XHTML."""
    tokens = re.split(
        r"(<table\b[^>]*>.*?</table>|<br\s*/?>|`[^`]+`|\*\*[^*]+\*\*)",
        text,
        flags=re.IGNORECASE,
    )
    parts: List[str] = []
    for tok in tokens:
        if not tok:
            continue
        low = tok.lower()
        if low.startswith("<table") and low.endswith("</table>"):
            safe_tbl = _sanitize_inline_table_xhtml(tok)
            parts.append(safe_tbl if safe_tbl is not None else _xml_escape(tok))
        elif re.fullmatch(r"<br\s*/?>", tok, flags=re.IGNORECASE):
            parts.append("<br />")
        elif len(tok) >= 2 and tok.startswith("`") and tok.endswith("`"):
            parts.append(f"<code>{_xml_escape(tok[1:-1])}</code>")
        elif len(tok) >= 4 and tok.startswith("**") and tok.endswith("**"):
            parts.append(f"<strong>{_xml_escape(tok[2:-2])}</strong>")
        else:
            parts.append(_xml_escape(tok))
    return "".join(parts)


def _split_md_table_row(line: str) -> List[str]:
    """Split a Markdown table row on unescaped pipes outside inline code spans."""
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|") and not s.endswith("\\|"):
        s = s[:-1]

    cells: List[str] = []
    cur: List[str] = []
    in_code = False
    i = 0
    while i < len(s):
        ch = s[i]
        if ch == "\\" and i + 1 < len(s):
            cur.append(s[i + 1])
            i += 2
            continue
        if ch == "`":
            in_code = not in_code
            cur.append(ch)
            i += 1
            continue
        if ch == "|" and not in_code:
            cells.append("".join(cur).strip())
            cur = []
            i += 1
            continue
        cur.append(ch)
        i += 1
    cells.append("".join(cur).strip())
    return cells


def _is_md_table_divider(cells: List[str]) -> bool:
    return bool(cells) and all(bool(re.fullmatch(r":?-{2,}:?", c.strip())) for c in cells)


def _md_block_to_xhtml(md_text: str) -> str:
    """Convert a Markdown section body (headings, lists, code blocks, nested tables) to valid XHTML."""
    lines = md_text.splitlines()
    out: List[str] = []
    i = 0
    n = len(lines)

    while i < n:
        raw = lines[i]
        stripped = raw.strip()

        if not stripped or stripped == "---":
            i += 1
            continue

        # Fenced code block
        if stripped.startswith("```"):
            i += 1
            code_lines: List[str] = []
            while i < n and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            if i < n:
                i += 1
            out.append(f"<pre><code>{_xml_escape(chr(10).join(code_lines))}</code></pre>")
            continue

        # Markdown table
        if "|" in stripped and stripped.startswith("|") and i + 1 < n:
            header_cells = _split_md_table_row(stripped)
            next_cells = _split_md_table_row(lines[i + 1].strip())
            if header_cells and _is_md_table_divider(next_cells):
                col_count = len(header_cells)
                i += 2
                body_rows: List[List[str]] = []
                while i < n and lines[i].strip().startswith("|"):
                    row_cells = _split_md_table_row(lines[i].strip())
                    if not _is_md_table_divider(row_cells):
                        if len(row_cells) < col_count:
                            row_cells.extend([""] * (col_count - len(row_cells)))
                        elif len(row_cells) > col_count:
                            merged_tail = " | ".join(row_cells[col_count - 1 :])
                            row_cells = row_cells[: col_count - 1] + [merged_tail]
                        body_rows.append(row_cells)
                    i += 1

                th_html = "".join(f"<th>{_format_inline_xhtml(c)}</th>" for c in header_cells)
                trs_html = [f"<tr>{th_html}</tr>"]
                for r in body_rows:
                    td_html = "".join(f"<td>{_format_inline_xhtml(c)}</td>" for c in r)
                    trs_html.append(f"<tr>{td_html}</tr>")
                out.append(f'<table class="nested-table"><tbody>{"".join(trs_html)}</tbody></table>')
                continue

        # Sub-headings
        h_match = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if h_match:
            lvl = min(6, max(3, len(h_match.group(1)) + 1))
            out.append(f"<h{lvl}>{_format_inline_xhtml(h_match.group(2).strip())}</h{lvl}>")
            i += 1
            continue

        # Blockquote / GitHub Alert
        if stripped.startswith(">"):
            q_lines: List[str] = []
            while i < n and lines[i].strip().startswith(">"):
                q_line = re.sub(r"^>\s?", "", lines[i].strip())
                q_lines.append(q_line)
                i += 1
            out.append(f"<blockquote><p>{_format_inline_xhtml(' '.join(q_lines))}</p></blockquote>")
            continue

        # Unordered or ordered list
        if re.match(r"^([-*+]|\d+\.)\s+", stripped):
            items: List[str] = []
            while i < n and re.match(r"^\s*([-*+]|\d+\.)\s+", lines[i]):
                item_txt = re.sub(r"^\s*([-*+]|\d+\.)\s+", "", lines[i]).strip()
                items.append(f"<li>{_format_inline_xhtml(item_txt)}</li>")
                i += 1
            out.append(f"<ul>{''.join(items)}</ul>")
            continue

        # Standard paragraph
        para_lines: List[str] = [stripped]
        i += 1
        while i < n:
            nxt = lines[i].strip()
            if (
                not nxt
                or nxt == "---"
                or nxt.startswith("```")
                or nxt.startswith("#")
                or nxt.startswith(">")
                or nxt.startswith("|")
                or re.match(r"^\s*([-*+]|\d+\.)\s+", lines[i])
            ):
                break
            para_lines.append(nxt)
            i += 1
        out.append(f"<p>{_format_inline_xhtml(' '.join(para_lines))}</p>")

    return "\n".join(out) if out else "<p>-</p>"


def _parse_prd_sections(prd_text: str) -> Tuple[str, List[Tuple[str, str]]]:
    """Extract document H1 title and a list of (section_title, section_markdown) from prd.md."""
    # Strip optional YAML frontmatter
    body = re.sub(r"^---\s*\n.*?\n---\s*\n?", "", prd_text, flags=re.DOTALL)
    doc_title = "产品需求文档（PRD）"
    sections: List[Tuple[str, List[str]]] = []
    cur_title = "文档概览"
    cur_lines: List[str] = []

    for line in body.splitlines():
        h1 = re.match(r"^#\s+(.*)$", line.strip())
        if h1:
            doc_title = h1.group(1).strip()
            continue
        h2 = re.match(r"^##\s+(.*)$", line.strip())
        if h2:
            if any(ln.strip() for ln in cur_lines):
                sections.append((cur_title, cur_lines))
            cur_title = h2.group(1).strip()
            cur_lines = []
            continue
        cur_lines.append(line)

    if any(ln.strip() for ln in cur_lines):
        sections.append((cur_title, cur_lines))

    return doc_title, [(t, "\n".join(lns).strip()) for t, lns in sections]


def _find_screenshot(screenshots_dir: Path, candidates: Sequence[str]) -> Optional[Path]:
    if not screenshots_dir.is_dir():
        return None
    exts = (".png", ".jpg", ".jpeg", ".webp", ".svg")
    for name in candidates:
        if not name:
            continue
        for ext in exts:
            p = screenshots_dir / f"{name}{ext}"
            if p.is_file():
                return p
    return None


def _build_export_rows(
    prd_sections: List[Tuple[str, str]],
    spec_data: Optional[Dict[str, Any]],
    screenshots_dir: Path,
) -> List[Dict[str, Any]]:
    """Build unified left-wireframe / right-specification rows for HTML and Confluence XML."""
    rows: List[Dict[str, Any]] = []

    if isinstance(spec_data, dict) and isinstance(spec_data.get("nodes"), dict):
        nodes: Dict[str, Any] = spec_data["nodes"]
        pages: Dict[str, Any] = spec_data.get("pages") or {}
        vars_list: List[Any] = spec_data.get("vars") or []
        spec_cards: List[Any] = spec_data.get("spec_cards") or []

        vars_by_id = {v["id"]: v for v in vars_list if isinstance(v, dict) and v.get("id")}
        cards_by_page: Dict[str, List[Dict[str, Any]]] = {}
        for c in spec_cards:
            if isinstance(c, dict) and c.get("page"):
                cards_by_page.setdefault(str(c["page"]), []).append(c)

        # Row group 1: Flow nodes & mapped pages from spec.json
        shown_cards_pages: set = set()
        for node_id, node_def in nodes.items():
            if not isinstance(node_def, dict):
                continue
            page_id = str(node_def.get("page") or "")
            page_def = pages.get(page_id) if isinstance(pages.get(page_id), dict) else {}
            page_title = str(page_def.get("title") or page_id or node_id)
            frame = str(page_def.get("frame") or "phone")
            node_title = str(node_def.get("title") or node_id)
            is_decision = bool(node_def.get("isDecision"))
            change_tag = str(node_def.get("change") or "unchanged")

            shot = _find_screenshot(screenshots_dir, [node_id, page_id])
            comps = page_def.get("components") if isinstance(page_def.get("components"), list) else []
            comp_labels = [
                f"{c.get('comp_name', '')} ({c.get('comp_id', '')})"
                for c in comps[:6]
                if isinstance(c, dict) and c.get("comp_id")
            ]

            right_parts: List[str] = [
                f"<p><strong>节点标题：</strong>{_xml_escape(node_title)}"
                f"（类型：<code>{'decision' if is_decision else 'process'}</code>"
                f" · 变更状态：<code>{_xml_escape(change_tag)}</code>）</p>"
            ]
            annos = node_def.get("anno")
            if isinstance(annos, list) and annos:
                anno_items = []
                for pair in annos:
                    if isinstance(pair, list) and len(pair) >= 2:
                        anno_items.append(
                            f"<li><strong>{_xml_escape(pair[0])}：</strong>{_xml_escape(pair[1])}</li>"
                        )
                if anno_items:
                    right_parts.append(f"<ul>{''.join(anno_items)}</ul>")

            bvar_id = node_def.get("branchVar")
            if is_decision and isinstance(bvar_id, str) and bvar_id in vars_by_id:
                bvar = vars_by_id[bvar_id]
                opts = bvar.get("options") if isinstance(bvar.get("options"), list) else []
                if opts:
                    opt_rows = [
                        "<tr><th>分支选项 ID</th><th>条件说明</th><th>跳转目标节点</th></tr>"
                    ]
                    for o in opts:
                        if isinstance(o, dict):
                            opt_rows.append(
                                f"<tr><td><code>{_xml_escape(o.get('id', ''))}</code></td>"
                                f"<td>{_xml_escape(o.get('label', ''))}</td>"
                                f"<td><code>{_xml_escape(o.get('target', '-'))}</code></td></tr>"
                            )
                    right_parts.append(
                        f"<p><strong>分支变量：</strong><code>{_xml_escape(bvar_id)}</code></p>"
                        f'<table class="nested-table"><tbody>{"".join(opt_rows)}</tbody></table>'
                    )

            if page_id and page_id in cards_by_page and page_id not in shown_cards_pages:
                shown_cards_pages.add(page_id)
                card_items = []
                for sc in cards_by_page[page_id]:
                    anchor_txt = f" [<code>{_xml_escape(sc.get('anchor'))}</code>]" if sc.get("anchor") else ""
                    card_items.append(
                        f"<li><strong>{_xml_escape(sc.get('title', sc.get('id', '')))}</strong>"
                        f"{anchor_txt}：{_xml_escape(sc.get('body', ''))}</li>"
                    )
                right_parts.append(f"<p><strong>关联改点卡：</strong></p><ul>{''.join(card_items)}</ul>")

            rows.append(
                {
                    "label_id": f"{node_id} / {page_id}" if page_id else node_id,
                    "subtitle": f"{page_title} ({frame})",
                    "screenshot": shot,
                    "components": comp_labels,
                    "right_xhtml": "\n".join(right_parts),
                }
            )

    # Append structured PRD sections so complete PRD narrative & tables are preserved
    for sec_idx, (sec_title, sec_md) in enumerate(prd_sections, start=1):
        id_refs = re.findall(r"\b((?:p-[a-z0-9_-]+|page_[a-z0-9_-]+|[FND]_[A-Za-z0-9_]+))\b", sec_md)
        uniq_refs: List[str] = []
        for r in id_refs:
            if r not in uniq_refs:
                uniq_refs.append(r)
        shot = _find_screenshot(screenshots_dir, uniq_refs + [f"sec-{sec_idx:02d}"])
        label_id = " · ".join(uniq_refs[:3]) if uniq_refs else f"PRD-SEC-{sec_idx:02d}"
        rows.append(
            {
                "label_id": label_id,
                "subtitle": sec_title,
                "screenshot": shot,
                "components": uniq_refs[:5],
                "right_xhtml": f"<h3>{_xml_escape(sec_title)}</h3>\n{_md_block_to_xhtml(sec_md)}",
            }
        )

    return rows


def _render_wiki_html(
    title: str,
    project: str,
    version_str: str,
    sha256_hex: str,
    exported_at: str,
    rows: List[Dict[str, Any]],
) -> str:
    row_chunks: List[str] = []
    for idx, row in enumerate(rows, start=1):
        shot: Optional[Path] = row["screenshot"]
        if shot is not None:
            media_html = (
                f'<img class="wf-shot" src="screenshots/{_xml_escape(shot.name)}" '
                f'alt="{_xml_escape(row["subtitle"])}" />'
            )
        else:
            chips = "".join(
                f'<span class="wf-chip">{_xml_escape(c)}</span>' for c in (row.get("components") or [])
            )
            chips_block = f'<div class="wf-chips">{chips}</div>' if chips else ""
            media_html = (
                '<div class="wf-placeholder">'
                '<div class="wf-ph-bar"><span></span><span></span><span></span></div>'
                f'<div class="wf-ph-title">{_xml_escape(row["subtitle"])}</div>'
                f'<div class="wf-ph-id">{_xml_escape(row["label_id"])}</div>'
                f"{chips_block}"
                "</div>"
            )

        row_chunks.append(
            "<tr>"
            f'<td class="col-idx">{idx:02d}</td>'
            f'<td class="col-left">'
            f'<div class="node-tag">{_xml_escape(row["label_id"])}</div>'
            f"{media_html}"
            "</td>"
            f'<td class="col-right">{row["right_xhtml"]}</td>'
            "</tr>"
        )

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>{_xml_escape(title)} - 图文对照交付版</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; padding: 24px 32px; background: #f7f7f7; color: #222222;
    font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", sans-serif;
    font-size: 14px; line-height: 1.65;
  }}
  .container {{ max-width: 1240px; margin: 0 auto; background: #ffffff; border: 1px solid #d4d4d4; border-radius: 8px; padding: 24px 28px; }}
  h1 {{ margin: 0 0 14px; font-size: 22px; color: #111111; }}
  .meta-box {{
    background: #f5f5f5; border: 1px solid #d4d4d4; border-radius: 6px;
    padding: 12px 16px; margin-bottom: 20px; font-size: 13px; color: #444444;
  }}
  .meta-box a {{ color: #111111; font-weight: 700; text-decoration: underline; }}
  table.main-table {{ width: 100%; border-collapse: collapse; table-layout: fixed; }}
  table.main-table > thead > tr > th,
  table.main-table > tbody > tr > td {{
    border: 1px solid #cccccc; padding: 12px 14px; vertical-align: top; text-align: left;
  }}
  table.main-table > thead > tr > th {{ background: #eeeeee; color: #111111; font-weight: 700; }}
  .col-idx {{ width: 64px; text-align: center !important; font-weight: 700; color: #555555; font-family: ui-monospace, monospace; }}
  .col-left {{ width: 340px; background: #fafafa; }}
  .col-right {{ width: auto; word-break: break-word; }}
  .node-tag {{
    display: inline-block; font-family: ui-monospace, monospace; font-size: 12px;
    background: #ebebeb; border: 1px solid #c8c8c8; border-radius: 4px;
    padding: 2px 8px; margin-bottom: 8px; color: #333333; font-weight: 600;
  }}
  .wf-shot {{ display: block; max-width: 100%; height: auto; border: 1px solid #cccccc; border-radius: 6px; }}
  .wf-placeholder {{
    border: 1px dashed #999999; border-radius: 6px; background: #ffffff;
    padding: 12px; color: #444444;
  }}
  .wf-ph-bar {{ display: flex; gap: 5px; margin-bottom: 10px; padding-bottom: 8px; border-bottom: 1px solid #e5e5e5; }}
  .wf-ph-bar span {{ width: 8px; height: 8px; border-radius: 50%; background: #cccccc; display: inline-block; }}
  .wf-ph-title {{ font-weight: 700; font-size: 13px; color: #222222; margin-bottom: 4px; }}
  .wf-ph-id {{ font-size: 11.5px; color: #666666; font-family: ui-monospace, monospace; margin-bottom: 8px; }}
  .wf-chips {{ display: flex; flex-wrap: wrap; gap: 4px; }}
  .wf-chip {{ font-size: 11px; padding: 1px 6px; background: #f0f0f0; border: 1px solid #d0d0d0; border-radius: 3px; color: #444444; }}
  table.nested-table {{ width: 100%; border-collapse: collapse; margin: 8px 0; font-size: 12.5px; }}
  table.nested-table th, table.nested-table td {{ border: 1px solid #d4d4d4; padding: 6px 8px; text-align: left; }}
  table.nested-table th {{ background: #f2f2f2; }}
  code {{ font-family: ui-monospace, monospace; font-size: 12px; background: #f0f0f0; padding: 1px 5px; border-radius: 3px; }}
  pre {{ background: #f5f5f5; border: 1px solid #dcdcdc; border-radius: 4px; padding: 8px 10px; overflow-x: auto; }}
  pre code {{ background: transparent; padding: 0; }}
  blockquote {{ margin: 8px 0; padding: 6px 12px; border-left: 3px solid #888888; background: #f7f7f7; color: #444444; }}
  h3, h4 {{ margin: 0 0 8px; color: #111111; }}
  p {{ margin: 0 0 8px; }}
  ul {{ margin: 0 0 8px; padding-left: 20px; }}
</style>
</head>
<body>
<div class="container">
  <h1>{_xml_escape(title)}</h1>
  <div class="meta-box">
    <div><strong>项目标识：</strong><code>{_xml_escape(project)}</code> &#183; <strong>版本：</strong><code>{_xml_escape(version_str)}</code> &#183; <strong>导出时间：</strong><code>{_xml_escape(exported_at)}</code></div>
    <div><strong>交互原型附件：</strong><a href="walkthrough.html.zip">walkthrough.html.zip（点击下载单文件离线走查工作台）</a> &#183; <strong>SHA-256：</strong><code>{_xml_escape(sha256_hex[:16])}</code></div>
  </div>
  <table class="main-table">
    <thead>
      <tr>
        <th class="col-idx">序号</th>
        <th class="col-left">页面 / 节点标识（线框对照）</th>
        <th class="col-right">结构化需求说明</th>
      </tr>
    </thead>
    <tbody>
      {"".join(row_chunks)}
    </tbody>
  </table>
</div>
</body>
</html>
"""


def _render_confluence_storage_xml(
    title: str,
    project: str,
    version_str: str,
    sha256_hex: str,
    exported_at: str,
    rows: List[Dict[str, Any]],
) -> str:
    """Render Confluence 7.x compatible Storage Format XML and verify well-formedness."""
    tr_chunks: List[str] = []
    for idx, row in enumerate(rows, start=1):
        shot: Optional[Path] = row["screenshot"]
        if shot is not None:
            left_visual = (
                f'<p><ac:image ac:width="300">'
                f'<ri:attachment ri:filename="{_xml_escape(shot.name)}" />'
                f"</ac:image></p>"
            )
        else:
            comp_list = ""
            if row.get("components"):
                lis = "".join(f"<li><code>{_xml_escape(c)}</code></li>" for c in row["components"])
                comp_list = f"<ul>{lis}</ul>"
            left_visual = (
                '<div style="border:1px dashed #999999;padding:8px;background-color:#fafafa;">'
                f"<p><strong>[灰阶线框占位]</strong> {_xml_escape(row['subtitle'])}</p>"
                f"{comp_list}"
                "</div>"
            )

        tr_chunks.append(
            "<tr>"
            f"<td><p><strong>{idx:02d}</strong></p></td>"
            f"<td><p><code>{_xml_escape(row['label_id'])}</code></p>{left_visual}</td>"
            f"<td>{row['right_xhtml']}</td>"
            "</tr>"
        )

    xml_doc = (
        '<div xmlns="http://www.w3.org/1999/xhtml" '
        'xmlns:ac="http://atlassian.com/content" '
        'xmlns:ri="http://atlassian.com/resource/identifier">'
        '<ac:structured-macro ac:name="details" ac:schema-version="1">'
        "<ac:rich-text-body>"
        "<table><tbody>"
        f"<tr><th>项目标识</th><td><code>{_xml_escape(project)}</code></td></tr>"
        f"<tr><th>文档标题</th><td>{_xml_escape(title)}</td></tr>"
        f"<tr><th>文档版本</th><td><code>{_xml_escape(version_str)}</code></td></tr>"
        f"<tr><th>导出时间</th><td><code>{_xml_escape(exported_at)}</code></td></tr>"
        f"<tr><th>原型校验指纹</th><td><code>{_xml_escape(sha256_hex)}</code></td></tr>"
        "<tr><th>交互走查附件</th><td>"
        "<ac:link><ri:attachment ri:filename=\"walkthrough.html.zip\" />"
        "<ac:plain-text-link-body><![CDATA[walkthrough.html.zip（下载离线交互走查工作台）]]></ac:plain-text-link-body>"
        "</ac:link>"
        "</td></tr>"
        "</tbody></table>"
        "</ac:rich-text-body>"
        "</ac:structured-macro>"
        f"<h2>{_xml_escape(title)} - 左图右文需求对照表</h2>"
        "<table>"
        "<colgroup>"
        '<col style="width: 64px;" />'
        '<col style="width: 320px;" />'
        '<col style="width: auto;" />'
        "</colgroup>"
        "<thead>"
        "<tr>"
        "<th>序号</th>"
        "<th>页面 / 节点标识</th>"
        "<th>结构化需求说明</th>"
        "</tr>"
        "</thead>"
        "<tbody>"
        f"{''.join(tr_chunks)}"
        "</tbody>"
        "</table>"
        "</div>"
    )

    # Strict XML 1.0 well-formedness & zero-broken-table gate
    ET.fromstring(xml_doc.encode("utf-8"))
    return xml_doc


def cmd_export(project_dir: Path) -> int:
    if not project_dir.is_dir():
        print(f"ERROR: Project directory not found: {project_dir}", file=sys.stderr)
        return 1

    prd_path = project_dir / "prd.md"
    wt_path = project_dir / "walkthrough.html"
    missing = [p.name for p in (prd_path, wt_path) if not p.is_file()]
    if missing:
        print(
            f"ERROR: Missing required deliverable(s) in {project_dir}: {', '.join(missing)}",
            file=sys.stderr,
        )
        return 1

    export_dir = project_dir / "wiki-export"
    export_dir.mkdir(parents=True, exist_ok=True)

    # 1. Compress walkthrough.html -> wiki-export/walkthrough.html.zip
    zip_path = export_dir / "walkthrough.html.zip"
    with zipfile.ZipFile(zip_path, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.write(wt_path, arcname="walkthrough.html")

    # Copy screenshots if present so relative references in wiki-page.html resolve cleanly
    screenshots_src = project_dir / "screenshots"
    if screenshots_src.is_dir():
        screenshots_dst = export_dir / "screenshots"
        screenshots_dst.mkdir(parents=True, exist_ok=True)
        for img in screenshots_src.iterdir():
            if img.is_file() and img.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp", ".svg"):
                shutil.copy2(img, screenshots_dst / img.name)

    # 2. Parse prd.md and optional spec.json
    prd_text = prd_path.read_text(encoding="utf-8")
    prd_title, prd_sections = _parse_prd_sections(prd_text)

    spec_data: Optional[Dict[str, Any]] = None
    spec_path = project_dir / "spec.json"
    if spec_path.is_file():
        try:
            loaded = json.loads(spec_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                spec_data = loaded
        except Exception as exc:
            print(f"ERROR: Invalid spec.json in {project_dir}: {exc}", file=sys.stderr)
            return 1

    ctx = parse_project_context(project_dir)
    meta = (spec_data or {}).get("meta") if isinstance((spec_data or {}).get("meta"), dict) else {}
    doc_title = str(meta.get("title") or ctx.get("title") or prd_title)
    project_slug = str(meta.get("project") or ctx.get("project") or project_dir.name)
    doc_version = str(meta.get("doc_version") or ctx.get("doc_version") or "v1.0")
    wt_sha256 = _sha256_file(wt_path)
    exported_at = _now_iso()

    rows = _build_export_rows(prd_sections, spec_data, screenshots_src)

    # 3. Generate adapter-appropriate export artifacts (do NOT dump Confluence XML into non-Confluence workspaces!)
    html_content = _render_wiki_html(doc_title, project_slug, doc_version, wt_sha256, exported_at, rows)
    html_out = export_dir / "wiki-page.html"
    html_out.write_text(html_content, encoding="utf-8")

    # Also build clean single-document WeCom / Feishu Markdown body (human-readable PRD + node spec summary)
    wecom_doc_md_lines = [
        f"# {doc_title}",
        "",
        f"> 版本：{doc_version} | 更新时间：{exported_at} | 交互走查原型指纹：{wt_sha256[:12]}",
        "",
        prd_text.strip(),
        "",
    ]
    wecom_md_out = export_dir / f"{doc_title}.md"
    wecom_md_out.write_text("\n".join(wecom_doc_md_lines), encoding="utf-8")

    try:
        storage_xml = _render_confluence_storage_xml(
            doc_title, project_slug, doc_version, wt_sha256, exported_at, rows
        )
        # Always verify XML well-formedness in memory as a structural table gate
        ET.fromstring(storage_xml.encode("utf-8"))
    except ET.ParseError as exc:
        print(f"ERROR: Generated Confluence Storage XML failed well-formedness check: {exc}", file=sys.stderr)
        return 1

    adapter_name = ctx.get("wiki_adapter", "local-obsidian")
    if adapter_name == "confluence":
        xml_out = export_dir / "confluence-storage.xml"
        xml_out.write_text(storage_xml, encoding="utf-8")
        print(f"[wiki_sync] Exported Confluence package to {export_dir}: {zip_path.name}, {xml_out.name}")
    else:
        # Remove stale confluence-storage.xml if present so Agents NEVER upload it to WeCom / Feishu!
        stale_xml = export_dir / "confluence-storage.xml"
        if stale_xml.is_file():
            stale_xml.unlink()
        print(f"[wiki_sync] Exported clean {adapter_name} package to {export_dir}: {wecom_md_out.name}, {zip_path.name}")
    return 0


def _push_wecom_wedoc(
    env: Dict[str, str],
    wiki_cfg: Dict[str, Any],
    doc_title: str,
    doc_body_text: str,
    existing_docid: str,
) -> Tuple[str, str]:
    """Create or update a SINGLE native Enterprise WeChat Online Document (WeDoc doc_type=3/11).

    Returns (docid, doc_url). Never uploads raw engineering files (.xml, project-context.md, etc.).
    """
    corp_id = (env.get("WECOM_CORP_ID") or env.get("WECOM_BOT_ID") or "").strip()
    secret = (env.get("WECOM_CORP_SECRET") or env.get("WECOM_BOT_SECRET") or "").strip()
    if not (corp_id and secret):
        raise ValueError("Missing WECOM_CORP_ID/WECOM_BOT_ID or WECOM_CORP_SECRET/WECOM_BOT_SECRET in .env.local")

    tok_url = (
        "https://qyapi.weixin.qq.com/cgi-bin/gettoken?"
        f"corpid={urllib.parse.quote(corp_id)}&corpsecret={urllib.parse.quote(secret)}"
    )
    tok_resp = _http_json_request(tok_url, "GET", {})
    access_token = str(tok_resp.get("access_token") or "").strip()
    if not access_token:
        raise RuntimeError(f"WeCom gettoken failed: {tok_resp.get('errmsg', tok_resp)}")

    doc_type_cfg = str(wiki_cfg.get("doc_type") or env.get("WECOM_DOC_TYPE") or "3").strip()
    doc_type_num = 11 if doc_type_cfg in ("11", "smartdoc", "智能文档") else 3
    space_id = str(wiki_cfg.get("space_id") or env.get("WECOM_SPACE_ID") or "").strip()
    father_id = str(wiki_cfg.get("father_id") or wiki_cfg.get("space_or_parent") or env.get("WECOM_FOLDER_ID") or "").strip()
    admin_users_raw = str(env.get("WECOM_ADMIN_USERID") or wiki_cfg.get("admin_userid") or "").strip()

    docid = existing_docid.strip()
    if docid.startswith("local:"):
        docid = ""
    doc_url = ""

    if not docid:
        create_url = f"https://qyapi.weixin.qq.com/cgi-bin/wedoc/create_doc?access_token={urllib.parse.quote(access_token)}"
        create_payload: Dict[str, Any] = {
            "doc_type": doc_type_num,
            "doc_name": doc_title,
        }
        if space_id and father_id:
            create_payload["spaceid"] = space_id
            create_payload["fatherid"] = father_id
        if admin_users_raw:
            create_payload["admin_users"] = [u.strip() for u in admin_users_raw.split(",") if u.strip()]

        c_resp = _http_json_request(create_url, "POST", {"Content-Type": "application/json"}, payload=create_payload)
        if int(c_resp.get("errcode", -1)) != 0:
            raise RuntimeError(f"WeCom wedoc/create_doc failed: {c_resp}")
        docid = str(c_resp.get("docid") or "")
        doc_url = str(c_resp.get("url") or "")

    # Write clean PRD content directly into the WeCom online document via wedoc/document/batch_update
    upd_url = f"https://qyapi.weixin.qq.com/cgi-bin/wedoc/document/batch_update?access_token={urllib.parse.quote(access_token)}"
    upd_payload: Dict[str, Any] = {
        "docid": docid,
        "requests": [
            {
                "insert_text": {
                    "text": doc_body_text[:45000],
                    "location": {"index": 0},
                }
            }
        ],
    }
    u_resp = _http_json_request(upd_url, "POST", {"Content-Type": "application/json"}, payload=upd_payload)
    if int(u_resp.get("errcode", 0)) != 0:
        raise RuntimeError(f"WeCom wedoc/document/batch_update failed: {u_resp}")

    if not doc_url and docid:
        share_url = f"https://qyapi.weixin.qq.com/cgi-bin/wedoc/doc_share?access_token={urllib.parse.quote(access_token)}"
        try:
            s_resp = _http_json_request(share_url, "POST", {"Content-Type": "application/json"}, payload={"docid": docid})
            doc_url = str(s_resp.get("share_url") or "")
        except Exception:
            pass
    return docid, doc_url


def cmd_push(project_dir: Path, force: bool = False, page_id_override: Optional[str] = None) -> int:
    # Step 1: Always run export first
    rc = cmd_export(project_dir)
    if rc != 0:
        return rc

    env, secrets = load_env_config(project_dir)
    ctx = parse_project_context(project_dir)
    manifest = load_manifest(project_dir)
    adapter = ctx["wiki_adapter"]
    wiki_cfg = ctx.get("wiki_config") or {}

    wt_path = project_dir / "walkthrough.html"
    export_dir = project_dir / "wiki-export"
    zip_path = export_dir / "walkthrough.html.zip"
    html_path = export_dir / "wiki-page.html"
    xml_path = export_dir / "confluence-storage.xml"

    wt_sha256 = _sha256_file(wt_path)
    doc_title = str(ctx.get("title") or project_dir.name)
    storage_xml = xml_path.read_text(encoding="utf-8") if xml_path.is_file() else ""

    base_url = (env.get("WIKI_BASE_URL") or wiki_cfg.get("base_url") or "").strip()
    confluence_pat = env.get("CONFLUENCE_PAT", "").strip()
    wecom_webhook = env.get("WECOM_WEBHOOK", "").strip()

    page_id = (
        (page_id_override or "").strip()
        or str(wiki_cfg.get("page_id") or "").strip()
        or str(manifest.get("remote_page_id") or "").strip()
        or env.get("CONFLUENCE_PAGE_ID", "").strip()
    )

    recorded_ver_raw = manifest.get("remote_version")
    recorded_ver: Optional[int] = int(recorded_ver_raw) if isinstance(recorded_ver_raw, int) or (
        isinstance(recorded_ver_raw, str) and recorded_ver_raw.isdigit()
    ) else None

    try:
        # Mode 1: Live Confluence REST API push with optimistic locking
        if adapter == "confluence" and base_url and confluence_pat:
            headers = _confluence_headers(env)
            if page_id:
                get_url = (
                    f"{base_url.rstrip('/')}/rest/api/content/"
                    f"{urllib.parse.quote(page_id)}?expand=version,space"
                )
                remote_info = _http_json_request(get_url, "GET", headers)
                remote_ver = int(((remote_info.get("version") or {}).get("number")) or 1)
                remote_title = str(remote_info.get("title") or doc_title)

                if recorded_ver is not None and remote_ver > recorded_ver and not force:
                    print(
                        f"ERROR: Optimistic lock conflict for Confluence page {page_id}: "
                        f"remote version ({remote_ver}) > local manifest version ({recorded_ver}). "
                        f"Please run 'wiki_sync.py pull {project_dir}' first, or pass --force to overwrite.",
                        file=sys.stderr,
                    )
                    return 1

                next_ver = remote_ver + 1
                put_url = f"{base_url.rstrip('/')}/rest/api/content/{urllib.parse.quote(page_id)}"
                put_payload: Dict[str, Any] = {
                    "id": str(page_id),
                    "type": "page",
                    "title": remote_title,
                    "version": {"number": next_ver},
                    "body": {
                        "storage": {
                            "value": storage_xml,
                            "representation": "storage",
                        }
                    },
                }
                put_resp = _http_json_request(put_url, "PUT", headers, payload=put_payload)
                final_ver = int(((put_resp.get("version") or {}).get("number")) or next_ver)
                _upload_confluence_attachment(base_url, page_id, zip_path, env)
            else:
                space_key = (env.get("CONFLUENCE_SPACE_KEY") or wiki_cfg.get("space_key") or "").strip()
                if not space_key:
                    print(
                        "ERROR: Confluence push without page_id requires space_key in project-context.md or CONFLUENCE_SPACE_KEY.",
                        file=sys.stderr,
                    )
                    return 1
                post_url = f"{base_url.rstrip('/')}/rest/api/content"
                post_payload: Dict[str, Any] = {
                    "type": "page",
                    "title": doc_title,
                    "space": {"key": space_key},
                    "body": {
                        "storage": {
                            "value": storage_xml,
                            "representation": "storage",
                        }
                    },
                }
                parent_id = (wiki_cfg.get("parent_page_id") or env.get("CONFLUENCE_PARENT_ID") or "").strip()
                if parent_id:
                    post_payload["ancestors"] = [{"id": str(parent_id)}]
                post_resp = _http_json_request(post_url, "POST", headers, payload=post_payload)
                page_id = str(post_resp.get("id") or "")
                final_ver = int(((post_resp.get("version") or {}).get("number")) or 1)
                if page_id:
                    _upload_confluence_attachment(base_url, page_id, zip_path, env)

            pushed_at = _now_iso()
            manifest.update(
                {
                    "adapter": "confluence",
                    "remote_page_id": str(page_id),
                    "remote_version": final_ver,
                    "pushed_at": pushed_at,
                    "walkthrough_sha256": wt_sha256,
                }
            )
            save_manifest(project_dir, manifest)
            print(f"[wiki_sync] Pushed to Confluence page {page_id} (v{final_ver})")
            return 0

        # Check local simulated remote optimistic lock if wiki-remote/_remote_meta.json exists
        wiki_remote_dir = project_dir / "wiki-remote"
        remote_meta_path = wiki_remote_dir / "_remote_meta.json"
        sim_remote_ver = recorded_ver or 0
        if remote_meta_path.is_file():
            try:
                rmeta = json.loads(remote_meta_path.read_text(encoding="utf-8"))
                if isinstance(rmeta.get("remote_version"), int):
                    sim_remote_ver = rmeta["remote_version"]
            except Exception:
                pass
            if recorded_ver is not None and sim_remote_ver > recorded_ver and not force:
                print(
                    f"ERROR: Optimistic lock conflict: remote version ({sim_remote_ver}) > "
                    f"local manifest version ({recorded_ver}). "
                    f"Please run 'wiki_sync.py pull {project_dir}' first, or pass --force.",
                    file=sys.stderr,
                )
                return 1

        # Mode 2: Native Enterprise WeChat Online Document (WeDoc create_doc + batch_update)
        wecom_id = (env.get("WECOM_CORP_ID") or env.get("WECOM_BOT_ID") or "").strip()
        wecom_sec = (env.get("WECOM_CORP_SECRET") or env.get("WECOM_BOT_SECRET") or "").strip()
        if adapter == "wecom" and wecom_id and wecom_sec:
            prd_body = (project_dir / "prd.md").read_text(encoding="utf-8")
            docid, share_url = _push_wecom_wedoc(env, wiki_cfg, doc_title, prd_body, page_id)
            next_ver = (recorded_ver or 0) + 1
            pushed_at = _now_iso()
            manifest.update(
                {
                    "adapter": "wecom",
                    "remote_page_id": docid,
                    "remote_url": share_url,
                    "remote_version": next_ver,
                    "pushed_at": pushed_at,
                    "walkthrough_sha256": wt_sha256,
                }
            )
            save_manifest(project_dir, manifest)
            if wecom_webhook:
                link_line = f"> **在线文档链接**：[点击打开《{doc_title}》]({share_url})\n" if share_url else ""
                card_md = (
                    f"### 需求定稿更新：{doc_title}\n"
                    f"{link_line}"
                    f"> **版本**：`v{next_ver}` · **更新时间**：`{pushed_at}`"
                )
                _http_json_request(
                    wecom_webhook,
                    "POST",
                    {"Content-Type": "application/json"},
                    payload={"msgtype": "markdown", "markdown": {"content": card_md}},
                )
            print(f"[wiki_sync] Published SINGLE native WeCom online document: docid={docid} url={share_url}")
            return 0

        # Mode 2b: WeCom Webhook group card notification only (when no WeDoc API credentials)
        if wecom_webhook and adapter == "wecom":
            card_md = (
                f"### PRD 与交互走查交付通知\n"
                f"> **项目**：{doc_title} (`{project_dir.name}`)\n"
                f"> **推送时间**：`{_now_iso()}`\n"
                f"> **原型指纹**：`{wt_sha256[:12]}`\n"
                f"> **交付文件**：`wiki-export/wiki-page.html`、`wiki-export/walkthrough.html.zip`"
            )
            _http_json_request(
                wecom_webhook,
                "POST",
                {"Content-Type": "application/json"},
                payload={"msgtype": "markdown", "markdown": {"content": card_md}},
            )
            print("[wiki_sync] Sent WeCom group notification card.")

        # Mode 3: Local / simulated wiki-remote archive sync
        wiki_remote_dir.mkdir(parents=True, exist_ok=True)
        next_ver = max(sim_remote_ver, recorded_ver or 0) + 1
        shutil.copy2(project_dir / "prd.md", wiki_remote_dir / f"{project_dir.name}-v{next_ver}.md")
        shutil.copy2(html_path, wiki_remote_dir / "wiki-page.html")
        shutil.copy2(zip_path, wiki_remote_dir / "walkthrough.html.zip")

        pushed_at = _now_iso()
        remote_page_id = str(page_id or f"local:{project_dir.name}")
        remote_meta_path.write_text(
            json.dumps(
                {
                    "remote_page_id": remote_page_id,
                    "remote_version": next_ver,
                    "updated_at": pushed_at,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        manifest.update(
            {
                "adapter": adapter,
                "remote_page_id": remote_page_id,
                "remote_version": next_ver,
                "pushed_at": pushed_at,
                "walkthrough_sha256": wt_sha256,
            }
        )
        save_manifest(project_dir, manifest)
        print(f"[wiki_sync] Synced package ({adapter}, v{next_ver}) and updated _manifest.json")
        return 0

    except Exception as exc:
        safe_err = redact_text(str(exc), secrets)
        print(f"ERROR: Push failed ({adapter}): {safe_err}", file=sys.stderr)
        return 1


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="wiki_sync.py",
        description=(
            "Synchronize OpenPM PRD & walkthrough deliverables with Confluence, WeCom, Feishu, "
            "or local Obsidian workspaces."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_pull = subparsers.add_parser(
        "pull",
        help="Pull remote/baseline PRD into history/prd-remote.md and generate history/pull-diff.md.",
    )
    p_pull.add_argument("project_dir", type=Path, help="Path to the project workspace directory.")
    p_pull.add_argument("--page-id", default=None, help="Optional remote Wiki/Confluence page ID override.")

    p_export = subparsers.add_parser(
        "export",
        help="Build wiki-export/ package (walkthrough.html.zip, wiki-page.html, confluence-storage.xml).",
    )
    p_export.add_argument("project_dir", type=Path, help="Path to the project workspace directory.")

    p_push = subparsers.add_parser(
        "push",
        help="Export deliverables, check optimistic lock in _manifest.json, and push/archive to target Wiki.",
    )
    p_push.add_argument("project_dir", type=Path, help="Path to the project workspace directory.")
    p_push.add_argument(
        "--force",
        action="store_true",
        help="Force push even when remote_version is newer than local _manifest.json.",
    )
    p_push.add_argument("--page-id", default=None, help="Optional remote Wiki/Confluence page ID override.")

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    if args.command == "pull":
        return cmd_pull(args.project_dir, page_id_override=args.page_id)
    if args.command == "export":
        return cmd_export(args.project_dir)
    if args.command == "push":
        return cmd_push(args.project_dir, force=args.force, page_id_override=args.page_id)
    return 1


if __name__ == "__main__":
    sys.exit(main())
