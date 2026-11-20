#!/usr/bin/env python3
"""Left-Prototype / Right-Specification (Confluence & WeCom Online Doc style) Builder.

Zero third-party dependencies (Python 3.9+ stdlib only + local Headless Chrome for auto-screenshots).
Key guarantees:
  1. NO Recursive `原型 | 说明` Sub-Table Nesting: Outer `序号 | 页面 | 需求说明` IS the sole prototype-to-spec
     container. `spec_cards` are never echoed into a redundant inner `原型 | 说明` sub-table.
  2. Single Source of Truth (Zero Duplication): When `prd.md` defines a page's rules, `prd.md` is authoritative;
     `node.anno` items are merged ONLY if non-overlapping, so no rule ever appears twice.
  3. Fail-Fast Screenshot Gate: Raises `ScreenshotCaptureError` (exit code 3) if sandbox blocks Chrome or any
     expected page/variant screenshot is missing, instead of silently producing blank placeholders.
  4. Full `variant_of` Multi-Platform Coverage: Automatically captures & pairs Web, PC, and Mobile App (375px)
     variants under their parent screen entry.
  5. Forced 100% Pure Grayscale: Applies `filter: grayscale(100%) !important` inside Chrome before capture +
     pure neutral `#1f1f1f`/`#d9d9d9` styling in HTML & `.docx` (zero blue tints).
  6. Cross-Page Context Preservation: Sticky left prototype column in HTML, `<w:tblHeader/>` repeating headers
     in `.docx`, and automatic `N-续` continuation splitting with left-column variant/context preview when a
     single screen's specification is extra long.
"""

from __future__ import annotations

import base64
import json
import os
import re
import shutil
import struct
import subprocess
import time
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

XML_ILLEGAL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\ufffe\uffff]")
SCREENSHOT_DPR = 1.5


class ScreenshotCaptureError(RuntimeError):
    """Raised when Headless Chrome cannot capture required prototype screenshots (e.g. restricted sandbox)."""


def _xe(val: Any) -> str:
    s = XML_ILLEGAL_RE.sub("", str(val if val is not None else ""))
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def _find_chrome_binary() -> Optional[str]:
    candidates = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        shutil.which("google-chrome") or "",
        shutil.which("chromium") or "",
        shutil.which("chromium-browser") or "",
    ]
    for c in candidates:
        if c and Path(c).is_file():
            return c
    return None


def _png_dimensions(png_bytes: bytes) -> Tuple[int, int]:
    if len(png_bytes) >= 24 and png_bytes[:8] == b"\x89PNG\r\n\x1a\n":
        w, h = struct.unpack(">II", png_bytes[16:24])
        if w > 0 and h > 0:
            return int(w), int(h)
    return 640, 420


def _collect_expected_pages(spec_data: Optional[Dict[str, Any]]) -> Tuple[List[str], Dict[str, List[str]], Dict[str, str]]:
    """Return (ordered_all_pages_to_capture, variants_by_base_page, node_for_base_page)."""
    if not isinstance(spec_data, dict):
        return [], {}, {}

    pages_dict = spec_data.get("pages") or {}
    nodes_dict = spec_data.get("nodes") or {}
    spec_cards = spec_data.get("spec_cards") or []

    base_pages: List[str] = []
    node_for_page: Dict[str, str] = {}
    for nid, ndef in nodes_dict.items():
        if isinstance(ndef, dict) and ndef.get("page"):
            raw_pid = str(ndef["page"])
            p_obj = pages_dict.get(raw_pid) if isinstance(pages_dict.get(raw_pid), dict) else {}
            bp = str(p_obj.get("variant_of") or raw_pid)
            if bp not in base_pages:
                base_pages.append(bp)
            node_for_page.setdefault(bp, nid)

    for sc in spec_cards:
        if isinstance(sc, dict) and sc.get("page"):
            raw_pid = str(sc["page"])
            p_obj = pages_dict.get(raw_pid) if isinstance(pages_dict.get(raw_pid), dict) else {}
            bp = str(p_obj.get("variant_of") or raw_pid)
            if bp not in base_pages and bp in pages_dict:
                base_pages.append(bp)

    # Also include any standalone base pages in spec.json["pages"] not yet listed
    for cand_pid, pdef in pages_dict.items():
        if not isinstance(pdef, dict):
            continue
        if not pdef.get("variant_of") and cand_pid not in base_pages:
            base_pages.append(cand_pid)

    variants_by_base: Dict[str, List[str]] = {bp: [] for bp in base_pages}
    for cand_pid, pdef in pages_dict.items():
        if not isinstance(pdef, dict):
            continue
        v_of = str(pdef.get("variant_of") or "").strip()
        if v_of and v_of in variants_by_base and cand_pid != v_of:
            variants_by_base[v_of].append(cand_pid)

    ordered_all: List[str] = []
    for bp in base_pages:
        if bp not in ordered_all:
            ordered_all.append(bp)
        for vp in variants_by_base.get(bp, []):
            if vp not in ordered_all:
                ordered_all.append(vp)

    return ordered_all, variants_by_base, node_for_page


def auto_capture_screenshots(
    project_dir: Path,
    wt_path: Path,
    spec_data: Optional[Dict[str, Any]],
    screenshots_dir: Path,
    allow_missing: bool = False,
) -> Dict[str, Path]:
    """Capture 100% pure-grayscale PNGs for all base pages and `variant_of` platform variants.

    Raises ScreenshotCaptureError if required page screenshots cannot be rendered and `allow_missing` is False.
    """
    screenshots_dir.mkdir(parents=True, exist_ok=True)
    ordered_pages, _, node_for_page = _collect_expected_pages(spec_data)
    if not ordered_pages or not isinstance(spec_data, dict):
        return {p.stem: p for p in screenshots_dir.glob("*.png")}

    chrome_bin = _find_chrome_binary()
    if not chrome_bin:
        existing = {p.stem: p for p in screenshots_dir.glob("*.png")}
        missing = [pid for pid in ordered_pages if pid not in existing]
        if missing and not allow_missing:
            raise ScreenshotCaptureError(
                f"未检测到本地 Chrome/Chromium 浏览器，且缺少 {len(missing)} 张原型截图（{', '.join(missing[:5])}）。"
            )
        return existing

    pages_dict = spec_data.get("pages") or {}
    captured: Dict[str, Path] = {}

    r_cmd, w_cmd = os.pipe()
    r_res, w_res = os.pipe()

    def _setup_fds() -> None:
        os.dup2(r_cmd, 3)
        os.dup2(w_res, 4)

    prof_dir = f"/tmp/openpm-wiki-shot-{os.getpid()}"
    shutil.rmtree(prof_dir, ignore_errors=True)
    proc: Optional[subprocess.Popen] = None
    stderr_path = Path(f"/tmp/openpm-chrome-err-{os.getpid()}.log")
    err_fh = open(stderr_path, "wb")

    try:
        proc = subprocess.Popen(
            [
                chrome_bin,
                "--headless=new",
                f"--user-data-dir={prof_dir}",
                "--no-sandbox",
                "--disable-gpu",
                "--disable-crash-reporter",
                "--disable-breakpad",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-dev-shm-usage",
                "--hide-scrollbars",
                "--window-size=1600,1500",
                "--remote-debugging-pipe",
                "about:blank",
            ],
            pass_fds=(3, 4),
            preexec_fn=_setup_fds,
            stdout=subprocess.DEVNULL,
            stderr=err_fh,
        )
        os.close(r_cmd)
        os.close(w_res)

        msg_id = 0
        buf = b""
        session_id = ""

        def _cdp(method: str, params: Optional[Dict[str, Any]] = None, use_sess: bool = True) -> Dict[str, Any]:
            nonlocal msg_id, buf
            msg_id += 1
            cid = msg_id
            payload: Dict[str, Any] = {"id": cid, "method": method}
            if params:
                payload["params"] = params
            if use_sess and session_id:
                payload["sessionId"] = session_id
            os.write(w_cmd, (json.dumps(payload) + "\0").encode("utf-8"))
            while True:
                while b"\0" not in buf:
                    chunk = os.read(r_res, 262144)
                    if not chunk:
                        raise RuntimeError("Chrome CDP 管道意外关闭（通常因受限沙箱禁止启动无头浏览器或 Mach 端口）")
                    buf += chunk
                raw, buf = buf.split(b"\0", 1)
                msg = json.loads(raw.decode("utf-8"))
                if msg.get("id") == cid:
                    if "error" in msg:
                        raise RuntimeError(f"CDP {method} error: {msg['error']}")
                    return msg.get("result") or {}

        def _eval(expr: str, await_p: bool = False) -> Any:
            r = _cdp("Runtime.evaluate", {"expression": expr, "returnByValue": True, "awaitPromise": await_p})
            return (r.get("result") or {}).get("value")

        targets = _cdp("Target.getTargets", use_sess=False).get("targetInfos") or []
        page_target = next((t for t in targets if t.get("type") == "page"), None)
        if not page_target:
            raise RuntimeError("Chrome 未能创建页面渲染目标（Target.getTargets 为空）")

        session_id = _cdp(
            "Target.attachToTarget",
            {"targetId": page_target["targetId"], "flatten": True},
            use_sess=False,
        )["sessionId"]
        _cdp("Page.enable")
        _cdp("Runtime.enable")
        _cdp(
            "Emulation.setDeviceMetricsOverride",
            {"width": 1600, "height": 1500, "deviceScaleFactor": SCREENSHOT_DPR, "mobile": False},
        )
        _cdp("Page.navigate", {"url": wt_path.resolve().as_uri()})
        time.sleep(0.65)

        # Force 100% pure grayscale across ALL DOM elements & native OS form controls!
        _eval(
            """
            (() => {
              if (window.toggleDeltaHighlight) window.toggleDeltaHighlight(false);
              const st = document.createElement('style');
              st.id = '__openpm_wiki_grayscale_enforce';
              st.textContent = `
                html, body, .page, .page *, *::before, *::after {
                  filter: grayscale(100%) !important;
                  -webkit-filter: grayscale(100%) !important;
                  accent-color: #262626 !important;
                }
                .insp-body, .stage { overflow: visible !important; max-height: none !important; height: auto !important; }
                .wb-stage, .flow-panel, .inspector-drawer { height: auto !important; min-height: 1400px !important; overflow: visible !important; }
              `;
              document.head.appendChild(st);
            })()
            """
        )

        # Capture every base page AND every `variant_of` page (Web + PC + App 375px)!
        for pid in ordered_pages:
            pdef = pages_dict.get(pid) if isinstance(pages_dict.get(pid), dict) else {}
            plat = str(pdef.get("platform") or "")
            base_ref = str(pdef.get("variant_of") or pid)
            nid = node_for_page.get(pid) or node_for_page.get(base_ref) or ""
            js_switch = f"""
            new Promise(resolve => {{
              if ({json.dumps(plat)} && window.setVar) window.setVar('platform', {json.dumps(plat)});
              if ({json.dumps(nid)} && window.setViewByNode) window.setViewByNode({json.dumps(nid)});
              if (window.showPage) window.showPage({json.dumps(pid)});
              requestAnimationFrame(() => requestAnimationFrame(() => {{
                const el = document.getElementById({json.dumps(pid)}) || document.querySelector('.page.active');
                if (!el) return resolve(null);
                const r = el.getBoundingClientRect();
                if (r.width < 40 || r.height < 30) return resolve(null);
                resolve({{ x: Math.max(0, r.left), y: Math.max(0, r.top), width: r.width, height: r.height }});
              }}));
            }})
            """
            rect = _eval(js_switch, await_p=True)
            if isinstance(rect, dict) and rect.get("width", 0) >= 40:
                shot = _cdp(
                    "Page.captureScreenshot",
                    {
                        "format": "png",
                        "clip": {
                            "x": float(rect["x"]),
                            "y": float(rect["y"]),
                            "width": float(rect["width"]),
                            "height": float(min(rect["height"], 1350.0)),
                            "scale": 1.0,
                        },
                    },
                )
                out_png = screenshots_dir / f"{pid}.png"
                out_png.write_bytes(base64.b64decode(shot["data"]))
                captured[pid] = out_png

    except Exception as exc:
        err_fh.flush()
        chrome_stderr = ""
        if stderr_path.is_file():
            chrome_stderr = stderr_path.read_text(encoding="utf-8", errors="ignore").strip()[-400:]
        if not allow_missing:
            detail = f"{exc}" + (f" | Chrome stderr: {chrome_stderr}" if chrome_stderr else "")
            raise ScreenshotCaptureError(
                f"无头浏览器截图失败（目标共 {len(ordered_pages)} 张页面变体截图）。原因：{detail}。\n"
                f"👉 解决方式：当前受限沙箱环境阻止了 Chrome 截图，请申请放宽运行权限（脱离沙箱/提权）后重新运行 `wiki_sync.py export/push`，严禁直接交付无图残次文档！"
            ) from exc
        return {p.stem: p for p in screenshots_dir.glob("*.png")}
    finally:
        err_fh.close()
        stderr_path.unlink(missing_ok=True)
        for fd in (w_cmd, r_res):
            try:
                os.close(fd)
            except OSError:
                pass
        if proc is not None:
            try:
                proc.terminate()
                proc.wait(timeout=3)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        shutil.rmtree(prof_dir, ignore_errors=True)

    missing_after = [pid for pid in ordered_pages if pid not in captured]
    if missing_after and not allow_missing:
        raise ScreenshotCaptureError(
            f"原型截图覆盖不完整，以下 {len(missing_after)} 个页面/变体未截到图片：{', '.join(missing_after)}。"
        )
    return captured


def _split_fine_grained_sections(prd_sections: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
    """Split H2 sections further on H3/H4 (`### ` / `#### `) so each page subsection maps cleanly to its own row."""
    fine: List[Tuple[str, str]] = []
    for h2_title, sec_md in prd_sections:
        cur_t = h2_title
        cur_lines: List[str] = []
        has_sub = False
        for ln in sec_md.splitlines():
            m3 = re.match(r"^#{2,4}\s+(.*)$", ln.strip())
            if m3:
                has_sub = True
                if any(x.strip() for x in cur_lines):
                    fine.append((cur_t, "\n".join(cur_lines).strip()))
                cur_t = m3.group(1).strip()
                cur_lines = []
            else:
                cur_lines.append(ln)
        if any(x.strip() for x in cur_lines):
            fine.append((cur_t if has_sub else h2_title, "\n".join(cur_lines).strip()))
    return fine


def _normalize_dedup_key(txt: str) -> str:
    """Create a normalized fingerprint to detect overlapping rules between node.anno and prd.md."""
    s = re.sub(r"[`*_#\s·•:：,，.。;；()（）\[\]【】/-]+", "", txt.lower())
    return s[:28]


def _extract_prd_plain_blocks(sec_md: str) -> List[Dict[str, Any]]:
    """Parse a Markdown section into clean plain-text paragraphs/bullets AND genuine Markdown data tables for .docx."""
    blocks: List[Dict[str, Any]] = []
    lines = sec_md.splitlines()
    i = 0
    n = len(lines)
    while i < n:
        raw = lines[i]
        s = raw.strip()
        if not s or s == "---":
            i += 1
            continue
        if s.startswith("```"):
            i += 1
            code_lns = []
            while i < n and not lines[i].strip().startswith("```"):
                code_lns.append(lines[i])
                i += 1
            if i < n:
                i += 1
            if code_lns:
                blocks.append({"kind": "text", "text": "\n".join(code_lns), "bold": False})
            continue
        # Genuine Markdown data table authored in prd.md (e.g. field dictionary / error codes)
        if s.startswith("|") and i + 1 < n and re.fullmatch(r"[\s|:-]+", lines[i + 1].strip()):
            hdr = [c.strip() for c in s.strip("|").split("|")]
            i += 2
            t_rows = []
            while i < n and lines[i].strip().startswith("|"):
                rc = [
                    re.sub(r"`([^`]+)`", r"\1", re.sub(r"\*\*([^*]+)\*\*", r"\1", c.strip()))
                    for c in lines[i].strip().strip("|").split("|")
                ]
                if not all(re.fullmatch(r":?-{2,}:?", x) for x in rc if x):
                    if len(rc) < len(hdr):
                        rc.extend([""] * (len(hdr) - len(rc)))
                    t_rows.append(rc[: len(hdr)])
                i += 1
            clean_hdr = [re.sub(r"`([^`]+)`", r"\1", re.sub(r"\*\*([^*]+)\*\*", r"\1", c)) for c in hdr]
            if clean_hdr and t_rows:
                blocks.append({"kind": "table", "headers": clean_hdr, "rows": t_rows})
            continue

        clean = re.sub(r"^>\s*(\[!NOTE\]|\[!IMPORTANT\]|\[!WARNING\]|\[!TIP\])?\s*", "", s)
        clean = re.sub(r"^#{1,6}\s+", "", clean)
        clean = re.sub(r"^([-*+•]|\d+\.)\s+", "", clean).strip()
        clean = re.sub(r"`([^`]+)`", r"\1", re.sub(r"\*\*([^*]+)\*\*", r"\1", clean))
        if clean:
            blocks.append({"kind": "text", "text": f"· {clean}", "bold": False})
        i += 1
    return blocks


def _platform_badge(pdef: Dict[str, Any], is_en: bool) -> str:
    plat = str(pdef.get("platform") or "").lower()
    frame = str(pdef.get("frame") or "").lower()
    if plat == "app" or frame == "phone":
        return "Mobile App (375px)" if is_en else "App 端（375px）"
    if plat == "pc":
        return "Desktop Client" if is_en else "PC 客户端"
    if plat in ("web", "web-admin") or frame == "wide":
        return "Web / Desktop" if is_en else "Web / PC 端"
    return str(pdef.get("title") or plat or "")


def build_fig2_rows(
    prd_sections: List[Tuple[str, str]],
    spec_data: Optional[Dict[str, Any]],
    screenshots_dir: Path,
    format_inline_xhtml_fn: Any,
    md_block_to_xhtml_fn: Any,
) -> List[Dict[str, Any]]:
    """Build Single-Source-of-Truth Left-Prototype / Right-Spec rows (ZERO recursive `原型|说明` nesting, ZERO duplicate text)."""
    rows: List[Dict[str, Any]] = []
    is_en = bool(
        isinstance(spec_data, dict)
        and str((spec_data.get("meta") or {}).get("lang") or "").lower().startswith("en")
    )

    if isinstance(spec_data, dict) and isinstance(spec_data.get("nodes"), dict):
        nodes: Dict[str, Any] = spec_data["nodes"]
        pages: Dict[str, Any] = spec_data.get("pages") or {}
        vars_list: List[Any] = spec_data.get("vars") or []

        _, variants_by_base, _ = _collect_expected_pages(spec_data)
        vars_by_id = {v["id"]: v for v in vars_list if isinstance(v, dict) and v.get("id")}

        fine_sections = _split_fine_grained_sections(prd_sections)
        matched_sec_indices: set = set()
        page_groups: Dict[str, Dict[str, Any]] = {}
        page_order: List[str] = []

        for nid, ndef in nodes.items():
            if not isinstance(ndef, dict):
                continue
            raw_pid = str(ndef.get("page") or nid)
            p_obj = pages.get(raw_pid) if isinstance(pages_dict := pages, dict) and isinstance(pages_dict.get(raw_pid), dict) else {}
            pid = str(p_obj.get("variant_of") or raw_pid)
            if pid not in page_groups:
                page_groups[pid] = {"nodes": [], "changes": set()}
                page_order.append(pid)
            page_groups[pid]["nodes"].append((nid, ndef))
            page_groups[pid]["changes"].add(str(ndef.get("change") or "unchanged"))

        all_base_pids = set(page_order)
        seq_num = 0

        for pid in page_order:
            seq_num += 1
            grp = page_groups[pid]
            grp_nodes: List[Tuple[str, Dict[str, Any]]] = grp["nodes"]
            _, primary_ndef = grp_nodes[0]
            pdef = pages.get(pid) if isinstance(pages.get(pid), dict) else {}
            raw_title = str(primary_ndef.get("title") or pdef.get("title") or pid)

            changes = grp["changes"]
            if "new" in changes:
                badge = " (New)" if is_en else "（新增）"
            elif "modified" in changes:
                badge = " (Updated)" if is_en else "（改动）"
            else:
                badge = ""
            heading = raw_title if ("新增" in raw_title or "改动" in raw_title or "New" in raw_title) else f"{raw_title}{badge}"

            # Collect base screenshot + ALL `variant_of` platform screenshots (Web + PC + App 375px)!
            variant_pids = variants_by_base.get(pid, [])
            labeled_shots: List[Tuple[str, Path]] = []
            main_shot = screenshots_dir / f"{pid}.png"
            if main_shot.is_file():
                lbl = _platform_badge(pdef, is_en) if variant_pids else ""
                labeled_shots.append((lbl, main_shot))
            for vpid in variant_pids:
                vshot = screenshots_dir / f"{vpid}.png"
                if vshot.is_file():
                    vpdef = pages.get(vpid) if isinstance(pages.get(vpid), dict) else {}
                    labeled_shots.append((_platform_badge(vpdef, is_en), vshot))

            all_shots = [sp for _, sp in labeled_shots]

            # 1. Match authoritative PRD subsections scoped to THIS page (including its variant_of IDs)
            own_pids = {pid} | set(variant_pids)
            own_nids = {nid for nid, _ in grp_nodes}
            match_tokens = own_pids | own_nids
            other_base_pids = all_base_pids - {pid}
            other_nids = set(nodes.keys()) - own_nids

            matched_md_chunks: List[str] = []
            for s_idx, (s_title, s_md) in enumerate(fine_sections):
                if s_idx in matched_sec_indices:
                    continue
                in_title = any(re.search(rf"(?<![A-Za-z0-9_-]){re.escape(tok)}(?![A-Za-z0-9_-])", s_title) for tok in match_tokens)
                in_body = any(re.search(rf"(?<![A-Za-z0-9_-]){re.escape(tok)}(?![A-Za-z0-9_-])", s_md) for tok in match_tokens)
                mentions_other_pages = sum(
                    1
                    for op in other_base_pids
                    if re.search(rf"(?<![A-Za-z0-9_-]){re.escape(op)}(?![A-Za-z0-9_-])", s_md + " " + s_title)
                )
                mentions_other_nodes = sum(
                    1
                    for on in other_nids
                    if re.search(rf"(?<![A-Za-z0-9_-]){re.escape(on)}(?![A-Za-z0-9_-])", s_md + " " + s_title)
                )
                if (in_title or in_body) and mentions_other_pages == 0 and mentions_other_nodes <= 1:
                    matched_sec_indices.add(s_idx)
                    matched_md_chunks.append(s_md)

            prd_combined_md = "\n\n".join(matched_md_chunks)
            prd_norm_corpus = re.sub(r"[`*_#\s·•:：,，.。;；()（）\[\]【】/-]+", "", prd_combined_md.lower())

            # 2. Single Source of Truth Merging (NO spec_cards echo, NO duplicate anno bullets!):
            #    Only include a `node.anno` item or `branchVar` summary if its key/content is NOT already covered in `prd_combined_md`.
            seen_keys: set = set()
            lead_xhtml: List[str] = []
            lead_docx_blocks: List[Dict[str, Any]] = []

            for _, ndef in grp_nodes:
                annos = ndef.get("anno")
                if isinstance(annos, list):
                    for pair in annos:
                        if isinstance(pair, list) and len(pair) >= 2:
                            k_txt, v_txt = str(pair[0]).strip(), str(pair[1]).strip()
                            k_norm = _normalize_dedup_key(k_txt)
                            v_norm = _normalize_dedup_key(v_txt)[:18]
                            if k_norm in seen_keys:
                                continue
                            # Skip if PRD section for this page already explains this exact topic!
                            if prd_norm_corpus and (
                                (len(k_norm) >= 4 and k_norm in prd_norm_corpus)
                                or (len(v_norm) >= 8 and v_norm in prd_norm_corpus)
                            ):
                                continue
                            seen_keys.add(k_norm)
                            lead_xhtml.append(f"<p>&#183; <strong>{_xe(k_txt)}</strong>：{_xe(v_txt)}</p>")
                            lead_docx_blocks.append({"kind": "text", "text": f"· {k_txt}：{v_txt}", "bold": False})

                # If this page hosts a decision diamond and PRD didn't already spell out the branch options, add 1 concise bullet (NOT a nested table!)
                bvar_id = ndef.get("branchVar")
                if ndef.get("isDecision") and isinstance(bvar_id, str) and bvar_id in vars_by_id:
                    bvar = vars_by_id[bvar_id]
                    bvar_label = str(bvar.get("label") or bvar_id)
                    if _normalize_dedup_key(bvar_label) not in prd_norm_corpus and bvar_id.lower() not in prd_combined_md.lower():
                        opts = [o for o in (bvar.get("options") or []) if isinstance(o, dict)]
                        if opts:
                            parts_str = "；".join(
                                f"{o.get('label', o.get('id', ''))} → {(nodes.get(str(o.get('target') or '')) or {}).get('title', o.get('target', '-'))}"
                                for o in opts
                            )
                            tag_lbl = "Routing" if is_en else "分支流转"
                            lead_xhtml.append(f"<p>&#183; <strong>{_xe(bvar_label)}（{tag_lbl}）</strong>：{_xe(parts_str)}</p>")
                            lead_docx_blocks.append({"kind": "text", "text": f"· {bvar_label}（{tag_lbl}）：{parts_str}", "bold": False})

            prd_xhtml_list = [md_block_to_xhtml_fn(ch) for ch in matched_md_chunks if ch.strip()]
            prd_docx_blocks: List[Dict[str, Any]] = []
            for ch in matched_md_chunks:
                prd_docx_blocks.extend(_extract_prd_plain_blocks(ch))

            all_docx_blocks = lead_docx_blocks + prd_docx_blocks
            all_xhtml_parts = lead_xhtml + prd_xhtml_list

            # 3. Cross-page context split (`N-续`) ONLY when a single page's specification is genuinely huge (> 12 blocks & >= 2 chunks/variants)
            if len(all_docx_blocks) >= 12 and len(matched_md_chunks) >= 2:
                mid_chunk = len(matched_md_chunks) // 2
                part1_md = matched_md_chunks[:mid_chunk]
                part2_md = matched_md_chunks[mid_chunk:]

                p1_blocks = lead_docx_blocks + [b for ch in part1_md for b in _extract_prd_plain_blocks(ch)]
                p2_blocks = [b for ch in part2_md for b in _extract_prd_plain_blocks(ch)]
                p1_xhtml = "\n".join([f"<p><strong>{_xe(heading)}</strong></p>"] + lead_xhtml + [md_block_to_xhtml_fn(c) for c in part1_md])

                primary_labeled = labeled_shots[:1] if len(labeled_shots) >= 2 else labeled_shots
                cont_labeled = labeled_shots[1:] if len(labeled_shots) >= 2 else labeled_shots[:1]

                rows.append(
                    {
                        "display_idx": str(seq_num),
                        "context_tag": f"#{seq_num} · {heading}",
                        "label_id": pid,
                        "subtitle": heading,
                        "screenshot": primary_labeled[0][1] if primary_labeled else None,
                        "screenshots": [sp for _, sp in primary_labeled],
                        "labeled_shots": primary_labeled,
                        "heading": heading,
                        "docx_blocks": p1_blocks,
                        "right_xhtml_html": p1_xhtml,
                        "right_xhtml": p1_xhtml,
                    }
                )

                cont_idx = f"{seq_num}-cont" if is_en else f"{seq_num}-续"
                cont_heading = f"[Cont. #{seq_num}] {raw_title}" if is_en else f"【续 #{seq_num} · {raw_title}】"
                p2_xhtml = "\n".join([f"<p><strong>{_xe(cont_heading)}</strong></p>"] + [md_block_to_xhtml_fn(c) for c in part2_md])
                rows.append(
                    {
                        "display_idx": cont_idx,
                        "context_tag": cont_heading,
                        "label_id": f"{pid}#cont",
                        "subtitle": cont_heading,
                        "screenshot": cont_labeled[0][1] if cont_labeled else None,
                        "screenshots": [sp for _, sp in cont_labeled],
                        "labeled_shots": cont_labeled,
                        "heading": cont_heading,
                        "docx_blocks": p2_blocks,
                        "right_xhtml_html": p2_xhtml,
                        "right_xhtml": p2_xhtml,
                    }
                )
            else:
                full_xhtml = "\n".join([f"<p><strong>{_xe(heading)}</strong></p>"] + all_xhtml_parts)
                rows.append(
                    {
                        "display_idx": str(seq_num),
                        "context_tag": f"#{seq_num} · {heading}",
                        "label_id": pid,
                        "subtitle": heading,
                        "screenshot": all_shots[0] if all_shots else None,
                        "screenshots": all_shots,
                        "labeled_shots": labeled_shots,
                        "heading": heading,
                        "docx_blocks": all_docx_blocks,
                        "right_xhtml_html": full_xhtml,
                        "right_xhtml": full_xhtml,
                    }
                )

        # Append non-redundant global sections (e.g. Non-functional / Audit / Edge Cases — skip front metadata & multi-page summary tables!)
        for s_idx, (s_title, s_md) in enumerate(fine_sections):
            if s_idx in matched_sec_indices or not s_md.strip():
                continue
            if s_title in ("文档概览", "Document Overview"):
                continue
            if sum(1 for op in all_base_pids if op in s_md) >= 2:
                continue
            # Also skip pure topology summary sections if all decision vars were already covered on their pages
            if sum(1 for nid in nodes if nid in s_md) >= 3:
                continue
            seq_num += 1
            g_blocks = _extract_prd_plain_blocks(s_md)
            x_body = f"<p><strong>{_xe(s_title)}</strong></p>\n{md_block_to_xhtml_fn(s_md)}"
            rows.append(
                {
                    "display_idx": str(seq_num),
                    "context_tag": f"#{seq_num} · {s_title}",
                    "label_id": "Global Rules" if is_en else "全局说明",
                    "subtitle": s_title,
                    "screenshot": None,
                    "screenshots": [],
                    "labeled_shots": [],
                    "heading": s_title,
                    "docx_blocks": g_blocks,
                    "right_xhtml_html": x_body,
                    "right_xhtml": x_body,
                }
            )
        return rows

    # Fallback when no spec.json exists
    for sec_idx, (sec_title, sec_md) in enumerate(prd_sections, start=1):
        x_body = f"<p><strong>{_xe(sec_title)}</strong></p>\n{md_block_to_xhtml_fn(sec_md)}"
        rows.append(
            {
                "display_idx": str(sec_idx),
                "context_tag": f"#{sec_idx} · {sec_title}",
                "label_id": f"SEC-{sec_idx}",
                "subtitle": sec_title,
                "screenshot": None,
                "screenshots": [],
                "labeled_shots": [],
                "heading": sec_title,
                "docx_blocks": _extract_prd_plain_blocks(sec_md),
                "right_xhtml_html": x_body,
                "right_xhtml": x_body,
            }
        )
    return rows


def render_fig2_html(
    title: str,
    version_str: str,
    zip_filename: str,
    rows: List[Dict[str, Any]],
    is_en: bool = False,
) -> str:
    """Render 100% pure-grayscale Left-Prototype/Right-Spec HTML with sticky prototype column & 1-click Copy."""
    tr_list: List[str] = []
    for idx, row in enumerate(rows, start=1):
        disp_idx = str(row.get("display_idx") or idx)
        ctx_tag = str(row.get("context_tag") or row.get("subtitle") or "")
        labeled_shots: List[Tuple[str, Path]] = row.get("labeled_shots") or [
            ("", sp) for sp in (row.get("screenshots") or []) if sp
        ]
        valid_labeled = [(lbl, sp) for lbl, sp in labeled_shots if sp and sp.is_file()]

        if valid_labeled:
            blocks = [f'<div class="ctx-pill">{_xe(ctx_tag)}</div>']
            for lbl, sp in valid_labeled:
                b64 = base64.b64encode(sp.read_bytes()).decode("ascii")
                cap = f'<div class="plat-cap">{_xe(lbl)}</div>' if lbl else ""
                blocks.append(
                    f'<div class="shot-card">{cap}'
                    f'<img class="wf-shot" src="data:image/png;base64,{b64}" alt="{_xe(row["subtitle"])}" /></div>'
                )
            left_cell = f'<div class="col-page-sticky">{"".join(blocks)}</div>'
        else:
            left_cell = f'<div class="col-page-sticky"><div class="wf-global-tag">{_xe(ctx_tag)}</div></div>'

        right_html = row.get("right_xhtml_html") or row.get("right_xhtml") or ""
        tr_list.append(
            "<tr>"
            f'<td class="col-idx">{_xe(disp_idx)}</td>'
            f'<td class="col-page">{left_cell}</td>'
            f'<td class="col-spec">{right_html}</td>'
            "</tr>"
        )

    sec_hd = "Product Specification" if is_en else "产品方案"
    proto_lbl = "Interactive Prototype: " if is_en else "交互原型："
    dl_txt = "(Click to Download)" if is_en else "（点击下载）"
    copy_btn = (
        "Copy Rich Table (Paste into WeCom / Feishu Doc)"
        if is_en
        else "一键复制左图右文全表（可直接粘贴至企微在线文档 / 飞书）"
    )
    copied_txt = (
        "Copied! Paste directly into WeCom / Feishu Doc"
        if is_en
        else "已复制图文表格！请直接 Cmd/Ctrl+V 粘贴到企业微信文档"
    )
    th_1 = "No." if is_en else "序号"
    th_2 = "Screen" if is_en else "页面"
    th_3 = "Specification" if is_en else "需求说明"

    return f"""<!DOCTYPE html>
<html lang="{'en' if is_en else 'zh-CN'}">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>{_xe(title)} - {sec_hd}</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; padding: 24px 32px; background: #ffffff; color: #1f1f1f;
    font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", sans-serif;
    font-size: 14px; line-height: 1.68;
  }}
  .doc-wrap {{ max-width: 1320px; margin: 0 auto; }}
  .doc-toolbar {{
    display: flex; align-items: center; justify-content: space-between; gap: 12px;
    padding: 10px 14px; margin-bottom: 18px; background: #f5f5f5; border: 1px solid #d9d9d9; border-radius: 6px;
  }}
  .doc-toolbar button {{
    background: #262626; color: #ffffff; border: none; border-radius: 5px;
    padding: 7px 14px; font-size: 13px; font-weight: 600; cursor: pointer;
  }}
  .doc-toolbar button:hover {{ background: #111111; }}
  h2.scheme-hd {{ margin: 0 0 8px; font-size: 20px; font-weight: 700; color: #141414; }}
  .proto-link-line {{ margin: 0 0 14px; font-size: 13.5px; color: #333333; }}
  .proto-link-line a {{ color: #1f1f1f; font-weight: 600; text-decoration: underline; }}
  table.main-table {{ width: 100%; border-collapse: collapse; table-layout: fixed; border: 1px solid #d9d9d9; }}
  table.main-table > thead {{ display: table-header-group; }}
  table.main-table > thead > tr > th,
  table.main-table > tbody > tr > td {{
    border: 1px solid #d9d9d9; padding: 14px 16px; vertical-align: top; text-align: left;
  }}
  table.main-table > thead > tr > th {{ background: #f2f2f2; color: #141414; font-weight: 700; font-size: 13.5px; }}
  .col-idx {{ width: 62px; color: #262626; font-weight: 700; font-family: ui-monospace, monospace; }}
  .col-page {{ width: 356px; background: #fafafa; }}
  .col-page-sticky {{ position: sticky; top: 14px; }}
  .ctx-pill {{
    font-size: 11.5px; font-weight: 700; color: #333333; background: #ececec;
    border: 1px solid #d4d4d4; border-radius: 4px; padding: 3px 8px; margin-bottom: 8px;
  }}
  .shot-card {{ margin-bottom: 12px; }}
  .shot-card:last-child {{ margin-bottom: 0; }}
  .plat-cap {{
    font-size: 11px; font-weight: 600; color: #595959; margin-bottom: 4px;
    font-family: ui-monospace, monospace;
  }}
  .col-spec {{ width: auto; word-break: break-word; background: #ffffff; }}
  .wf-shot {{
    display: block; max-width: 100%; height: auto; border: 1px solid #d4d4d4;
    border-radius: 4px; filter: grayscale(100%);
  }}
  .wf-global-tag {{
    padding: 10px 12px; background: #f2f2f2; border: 1px solid #d4d4d4; border-radius: 4px;
    font-weight: 600; color: #404040; font-size: 13px; text-align: center;
  }}
  table.nested-table {{ width: 100%; border-collapse: collapse; margin: 10px 0 6px; font-size: 13px; }}
  table.nested-table th, table.nested-table td {{
    border: 1px solid #d9d9d9; padding: 7px 10px; vertical-align: top; text-align: left;
  }}
  table.nested-table th {{ background: #f5f5f5; font-weight: 700; color: #1f1f1f; }}
  p {{ margin: 0 0 6px; }}
  ul {{ margin: 0 0 8px; padding-left: 18px; }}
  li {{ margin-bottom: 4px; }}
  h3, h4, h5 {{ margin: 10px 0 6px; font-size: 14px; color: #141414; }}
  code {{ font-family: ui-monospace, monospace; font-size: 12px; background: #f2f2f2; padding: 1px 4px; border-radius: 3px; color: #262626; }}
  blockquote {{ margin: 8px 0; padding: 6px 12px; border-left: 3px solid #8c8c8c; background: #f7f7f7; color: #404040; }}
  @media print {{
    .doc-toolbar {{ display: none; }}
    body {{ padding: 0; }}
    .col-page-sticky {{ position: static; }}
  }}
</style>
</head>
<body>
<div class="doc-wrap">
  <div class="doc-toolbar">
    <span><strong>{_xe(title)}</strong> &#183; <code>{_xe(version_str)}</code></span>
    <button type="button" id="copy-rich-btn" onclick="copyRichDoc()">{copy_btn}</button>
  </div>
  <div id="copy-target">
    <h2 class="scheme-hd">{sec_hd}</h2>
    <p class="proto-link-line">{proto_lbl}<a href="{_xe(zip_filename)}">{_xe(zip_filename)} {dl_txt}</a></p>
    <table class="main-table">
      <thead>
        <tr>
          <th class="col-idx">{th_1}</th>
          <th class="col-page">{th_2}</th>
          <th class="col-spec">{th_3}</th>
        </tr>
      </thead>
      <tbody>
        {"".join(tr_list)}
      </tbody>
    </table>
  </div>
</div>
<script>
function copyRichDoc() {{
  var target = document.getElementById('copy-target');
  var btn = document.getElementById('copy-rich-btn');
  var sel = window.getSelection();
  var range = document.createRange();
  range.selectNodeContents(target);
  sel.removeAllRanges();
  sel.addRange(range);
  try {{ document.execCommand('copy'); }} catch (e) {{}}
  sel.removeAllRanges();
  if (btn) {{
    var orig = btn.textContent;
    btn.textContent = {json.dumps(copied_txt)};
    setTimeout(function() {{ btn.textContent = orig; }}, 2400);
  }}
}}
</script>
</body>
</html>
"""


def render_fig2_confluence_xml(
    title: str,
    version_str: str,
    zip_filename: str,
    rows: List[Dict[str, Any]],
    is_en: bool = False,
) -> str:
    """Render Confluence 7.4+ Storage XML (clean 3-column `序号 | 页面 | 需求说明`, zero recursive sub-table clutter)."""
    tr_chunks: List[str] = []
    for idx, row in enumerate(rows, start=1):
        disp_idx = str(row.get("display_idx") or idx)
        ctx_tag = str(row.get("context_tag") or row.get("subtitle") or "")
        labeled_shots: List[Tuple[str, Path]] = row.get("labeled_shots") or [
            ("", sp) for sp in (row.get("screenshots") or []) if sp
        ]
        valid_labeled = [(lbl, sp) for lbl, sp in labeled_shots if sp and sp.is_file()]

        if valid_labeled:
            parts = [f"<p><strong>{_xe(ctx_tag)}</strong></p>"]
            for lbl, sp in valid_labeled:
                if lbl:
                    parts.append(f"<p><code>{_xe(lbl)}</code></p>")
                parts.append(f'<p><ac:image ac:width="310"><ri:attachment ri:filename="{_xe(sp.name)}" /></ac:image></p>')
            left_visual = "".join(parts)
        else:
            left_visual = f"<p><strong>{_xe(ctx_tag)}</strong></p>"

        tr_chunks.append(
            "<tr>"
            f"<td><p><strong>{_xe(disp_idx)}</strong></p></td>"
            f"<td>{left_visual}</td>"
            f"<td>{row['right_xhtml']}</td>"
            "</tr>"
        )

    sec_hd = "Product Specification" if is_en else "产品方案"
    proto_lbl = "Interactive Prototype: " if is_en else "交互原型："
    dl_txt = "(Click to Download)" if is_en else "（点击下载）"
    th_1 = "No." if is_en else "序号"
    th_2 = "Screen" if is_en else "页面"
    th_3 = "Specification" if is_en else "需求说明"

    xml_doc = (
        '<div xmlns="http://www.w3.org/1999/xhtml" '
        'xmlns:ac="http://atlassian.com/content" '
        'xmlns:ri="http://atlassian.com/resource/identifier">'
        f"<h2>{sec_hd}</h2>"
        f"<p>{proto_lbl}"
        f'<ac:link><ri:attachment ri:filename="{_xe(zip_filename)}" />'
        f"<ac:plain-text-link-body><![CDATA[{zip_filename} {dl_txt}]]></ac:plain-text-link-body>"
        "</ac:link></p>"
        "<table>"
        "<colgroup>"
        '<col style="width: 62px;" />'
        '<col style="width: 356px;" />'
        '<col style="width: auto;" />'
        "</colgroup>"
        "<thead>"
        "<tr>"
        f"<th>{th_1}</th>"
        f"<th>{th_2}</th>"
        f"<th>{th_3}</th>"
        "</tr>"
        "</thead>"
        "<tbody>"
        f"{''.join(tr_chunks)}"
        "</tbody>"
        "</table>"
        "</div>"
    )
    ET.fromstring(xml_doc.encode("utf-8"))
    return xml_doc


def write_fig2_docx(
    docx_path: Path,
    title: str,
    version_str: str,
    zip_filename: str,
    rows: List[Dict[str, Any]],
    is_en: bool = False,
) -> Path:
    """Write pure-grayscale OOXML `.docx` with `<w:tblHeader/>` repeat, full variants, and zero recursive sub-tables."""
    media_entries: List[Tuple[str, str, Path]] = []
    path_to_rid: Dict[str, Tuple[str, int, int]] = {}

    def _register_img(p: Path, max_w_px: int) -> Tuple[str, int, int]:
        key = str(p.resolve())
        if key in path_to_rid:
            rid, orig_w, orig_h = path_to_rid[key]
        else:
            idx = len(media_entries) + 1
            rid = f"rIdImg{idx}"
            mname = f"image{idx}.png"
            raw = p.read_bytes()
            orig_w, orig_h = _png_dimensions(raw)
            media_entries.append((rid, mname, p))
            path_to_rid[key] = (rid, orig_w, orig_h)
        logical_w = max(1.0, orig_w / SCREENSHOT_DPR)
        logical_h = max(1.0, orig_h / SCREENSHOT_DPR)
        scale = min(1.0, float(max_w_px) / logical_w)
        cx = int(round(logical_w * scale * 9525))
        cy = int(round(logical_h * scale * 9525))
        return rid, cx, cy

    def _w_p_text(txt: str, bold: bool = False, size_half_pt: int = 20, color: str = "1F1F1F") -> str:
        b_xml = "<w:b/><w:bCs/>" if bold else ""
        return (
            "<w:p><w:pPr><w:spacing w:before=\"36\" w:after=\"56\"/></w:pPr>"
            f"<w:r><w:rPr>{b_xml}<w:color w:val=\"{color}\"/>"
            f"<w:sz w:val=\"{size_half_pt}\"/><w:szCs w:val=\"{size_half_pt}\"/></w:rPr>"
            f"<w:t xml:space=\"preserve\">{_xe(txt)}</w:t></w:r></w:p>"
        )

    def _w_p_img(p: Path, max_w_px: int, doc_pr_id: int) -> str:
        rid, cx, cy = _register_img(p, max_w_px=max_w_px)
        return (
            "<w:p><w:pPr><w:spacing w:before=\"36\" w:after=\"72\"/></w:pPr><w:r><w:drawing>"
            "<wp:inline distT=\"0\" distB=\"0\" distL=\"0\" distR=\"0\">"
            f"<wp:extent cx=\"{cx}\" cy=\"{cy}\"/>"
            f"<wp:docPr id=\"{doc_pr_id}\" name=\"Shot{doc_pr_id}\"/>"
            "<wp:cNvGraphicFramePr><a:graphicFrameLocks xmlns:a=\"http://schemas.openxmlformats.org/drawingml/2006/main\" noChangeAspect=\"1\"/></wp:cNvGraphicFramePr>"
            "<a:graphic xmlns:a=\"http://schemas.openxmlformats.org/drawingml/2006/main\">"
            "<a:graphicData uri=\"http://schemas.openxmlformats.org/drawingml/2006/picture\">"
            "<pic:pic xmlns:pic=\"http://schemas.openxmlformats.org/drawingml/2006/picture\">"
            f"<pic:nvPicPr><pic:cNvPr id=\"{doc_pr_id}\" name=\"img{doc_pr_id}.png\"/><pic:cNvPicPr/></pic:nvPicPr>"
            f"<pic:blipFill><a:blip r:embed=\"{rid}\"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>"
            f"<pic:spPr><a:xfrm><a:off x=\"0\" y=\"0\"/><a:ext cx=\"{cx}\" cy=\"{cy}\"/></a:xfrm>"
            "<a:prstGeom prst=\"rect\"><a:avLst/></a:prstGeom></pic:spPr>"
            "</pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing></w:r></w:p>"
        )

    tbl_borders = (
        "<w:tblBorders>"
        "<w:top w:val=\"single\" w:sz=\"6\" w:space=\"0\" w:color=\"D9D9D9\"/>"
        "<w:left w:val=\"single\" w:sz=\"6\" w:space=\"0\" w:color=\"D9D9D9\"/>"
        "<w:bottom w:val=\"single\" w:sz=\"6\" w:space=\"0\" w:color=\"D9D9D9\"/>"
        "<w:right w:val=\"single\" w:sz=\"6\" w:space=\"0\" w:color=\"D9D9D9\"/>"
        "<w:insideH w:val=\"single\" w:sz=\"6\" w:space=\"0\" w:color=\"D9D9D9\"/>"
        "<w:insideV w:val=\"single\" w:sz=\"6\" w:space=\"0\" w:color=\"D9D9D9\"/>"
        "</w:tblBorders>"
    )
    cell_mar = (
        "<w:tblCellMar>"
        "<w:top w:w=\"110\" w:type=\"dxa\"/>"
        "<w:left w:w=\"140\" w:type=\"dxa\"/>"
        "<w:bottom w:w=\"110\" w:type=\"dxa\"/>"
        "<w:right w:w=\"140\" w:type=\"dxa\"/>"
        "</w:tblCellMar>"
    )

    th_1 = "No." if is_en else "序号"
    th_2 = "Screen" if is_en else "页面"
    th_3 = "Specification" if is_en else "需求说明"
    sec_hd = "Product Specification" if is_en else "产品方案"
    proto_line = (
        f"Interactive Prototype: {zip_filename} ({version_str})"
        if is_en
        else f"交互原型：{zip_filename}（版本 {version_str}）"
    )

    doc_pr_seq = 1
    tr_xml_list: List[str] = [
        "<w:tr><w:trPr><w:tblHeader/><w:cantSplit/></w:trPr>"
        f"<w:tc><w:tcPr><w:tcW w:w=\"900\" w:type=\"dxa\"/><w:shd w:val=\"clear\" w:fill=\"F2F2F2\"/></w:tcPr>{_w_p_text(th_1, bold=True)}</w:tc>"
        f"<w:tc><w:tcPr><w:tcW w:w=\"4800\" w:type=\"dxa\"/><w:shd w:val=\"clear\" w:fill=\"F2F2F2\"/></w:tcPr>{_w_p_text(th_2, bold=True)}</w:tc>"
        f"<w:tc><w:tcPr><w:tcW w:w=\"9698\" w:type=\"dxa\"/><w:shd w:val=\"clear\" w:fill=\"F2F2F2\"/></w:tcPr>{_w_p_text(th_3, bold=True)}</w:tc>"
        "</w:tr>"
    ]

    for idx, row in enumerate(rows, start=1):
        disp_idx = str(row.get("display_idx") or idx)
        ctx_tag = str(row.get("context_tag") or row.get("subtitle") or "")
        labeled_shots: List[Tuple[str, Path]] = row.get("labeled_shots") or [
            ("", sp) for sp in (row.get("screenshots") or []) if sp
        ]
        valid_labeled = [(lbl, sp) for lbl, sp in labeled_shots if sp and sp.is_file()]

        if valid_labeled:
            left_ps = [_w_p_text(ctx_tag, bold=True, size_half_pt=18, color="404040")]
            for lbl, sp in valid_labeled:
                if lbl:
                    left_ps.append(_w_p_text(f"[{lbl}]", bold=False, size_half_pt=16, color="595959"))
                doc_pr_seq += 1
                left_ps.append(_w_p_img(sp, max_w_px=295, doc_pr_id=doc_pr_seq))
            left_cell_xml = "".join(left_ps)
        else:
            left_cell_xml = _w_p_text(ctx_tag, bold=True, color="404040")

        right_ps: List[str] = [_w_p_text(str(row.get("heading") or row.get("subtitle") or ""), bold=True, size_half_pt=21)]
        for blk in row.get("docx_blocks") or []:
            if blk.get("kind") == "table":
                hdrs: List[str] = blk.get("headers") or []
                d_rows: List[List[str]] = blk.get("rows") or []
                col_n = max(1, len(hdrs))
                col_w = int(9300 // col_n)
                grid_xml = "".join(f'<w:gridCol w:w="{col_w}"/>' for _ in range(col_n))
                th_cells = "".join(
                    f'<w:tc><w:tcPr><w:tcW w:w="{col_w}" w:type="dxa"/><w:shd w:val="clear" w:fill="F5F5F5"/></w:tcPr>{_w_p_text(h, bold=True, size_half_pt=17)}</w:tc>'
                    for h in hdrs
                )
                d_trs = [f"<w:tr><w:trPr><w:tblHeader/><w:cantSplit/></w:trPr>{th_cells}</w:tr>"]
                for dr in d_rows:
                    td_cells = "".join(
                        f'<w:tc><w:tcPr><w:tcW w:w="{col_w}" w:type="dxa"/></w:tcPr>{_w_p_text(c, bold=False, size_half_pt=17)}</w:tc>'
                        for c in dr
                    )
                    d_trs.append(f"<w:tr><w:trPr><w:cantSplit/></w:trPr>{td_cells}</w:tr>")
                right_ps.append(
                    "<w:tbl>"
                    f"<w:tblPr><w:tblW w:w=\"{col_w * col_n}\" w:type=\"dxa\"/>{tbl_borders}{cell_mar}</w:tblPr>"
                    f"<w:tblGrid>{grid_xml}</w:tblGrid>"
                    f"{''.join(d_trs)}"
                    "</w:tbl><w:p/>"
                )
            else:
                right_ps.append(_w_p_text(str(blk.get("text") or ""), bold=bool(blk.get("bold")), size_half_pt=19))

        tr_xml_list.append(
            "<w:tr>"
            f"<w:tc><w:tcPr><w:tcW w:w=\"900\" w:type=\"dxa\"/></w:tcPr>{_w_p_text(disp_idx, bold=True)}</w:tc>"
            f"<w:tc><w:tcPr><w:tcW w:w=\"4800\" w:type=\"dxa\"/><w:shd w:val=\"clear\" w:fill=\"FAFAFA\"/></w:tcPr>{left_cell_xml}</w:tc>"
            f"<w:tc><w:tcPr><w:tcW w:w=\"9698\" w:type=\"dxa\"/></w:tcPr>{''.join(right_ps)}</w:tc>"
            "</w:tr>"
        )

    document_xml = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<w:document xmlns:w=\"http://schemas.openxmlformats.org/wordprocessingml/2006/main\" "
        "xmlns:r=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships\" "
        "xmlns:wp=\"http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing\">"
        "<w:body>"
        f"{_w_p_text(title + ' · ' + sec_hd, bold=True, size_half_pt=28)}"
        f"{_w_p_text(proto_line, bold=False, size_half_pt=19, color='595959')}"
        "<w:tbl>"
        f"<w:tblPr><w:tblW w:w=\"15398\" w:type=\"dxa\"/>{tbl_borders}{cell_mar}</w:tblPr>"
        "<w:tblGrid><w:gridCol w:w=\"900\"/><w:gridCol w:w=\"4800\"/><w:gridCol w:w=\"9698\"/></w:tblGrid>"
        f"{''.join(tr_xml_list)}"
        "</w:tbl>"
        "<w:sectPr>"
        "<w:pgSz w:w=\"16838\" w:h=\"11906\" w:orient=\"landscape\"/>"
        "<w:pgMar w:top=\"720\" w:right=\"720\" w:bottom=\"720\" w:left=\"720\"/>"
        "</w:sectPr>"
        "</w:body></w:document>"
    )
    ET.fromstring(document_xml.encode("utf-8"))

    rels_items = "".join(
        f'<Relationship Id="{rid}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/{mname}"/>'
        for rid, mname, _ in media_entries
    )
    doc_rels_xml = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">"
        f"{rels_items}"
        "</Relationships>"
    )
    root_rels_xml = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">"
        "<Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument\" Target=\"word/document.xml\"/>"
        "</Relationships>"
    )
    content_types_xml = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<Types xmlns=\"http://schemas.openxmlformats.org/package/2006/content-types\">"
        "<Default Extension=\"rels\" ContentType=\"application/vnd.openxmlformats-package.relationships+xml\"/>"
        "<Default Extension=\"xml\" ContentType=\"application/xml\"/>"
        "<Default Extension=\"png\" ContentType=\"image/png\"/>"
        "<Override PartName=\"/word/document.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml\"/>"
        "</Types>"
    )

    with zipfile.ZipFile(docx_path, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types_xml)
        zf.writestr("_rels/.rels", root_rels_xml)
        zf.writestr("word/document.xml", document_xml)
        zf.writestr("word/_rels/document.xml.rels", doc_rels_xml)
        for _, mname, img_path in media_entries:
            zf.writestr(f"word/media/{mname}", img_path.read_bytes())

    return docx_path
