#!/usr/bin/env python3
"""Left-Prototype / Right-Specification (图2 Confluence & WeCom Online Doc style) Builder.

Zero third-party dependencies (Python 3.9+ stdlib only + optional local Headless Chrome for auto-screenshots).
Generates:
  1. Auto-rendered grayscale prototype page PNGs & anchored component close-up PNGs from walkthrough.html;
  2. Unified 3-column (`序号 | 页面 | 需求说明`) + nested 2-column (`原型 | 说明`) data model;
  3. Native Office Open XML `.docx` (`<title>.docx`) that Enterprise WeChat (企微在线文档), Feishu, and Word
     import/open directly as a rich Left-Image / Right-Spec online document;
  4. Confluence 7.4+ Storage XML (`confluence-storage.xml`) with `<ac:image><ri:attachment/></ac:image>`;
  5. Self-contained Base64 `wiki-page.html` with 1-click Rich-Table Copy for pasting into WeCom / Feishu Docs.
"""

from __future__ import annotations

import base64
import html
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


def auto_capture_screenshots(
    project_dir: Path,
    wt_path: Path,
    spec_data: Optional[Dict[str, Any]],
    screenshots_dir: Path,
) -> Dict[str, Path]:
    """Automatically capture clean grayscale PNGs of prototype pages & anchored components via Chrome CDP pipe."""
    captured: Dict[str, Path] = {}
    screenshots_dir.mkdir(parents=True, exist_ok=True)

    # First index any pre-existing screenshots
    for p in screenshots_dir.glob("*.png"):
        captured[p.stem] = p

    if not isinstance(spec_data, dict) or not wt_path.is_file():
        return captured

    chrome_bin = _find_chrome_binary()
    if not chrome_bin:
        return captured

    pages_dict = spec_data.get("pages") or {}
    nodes_dict = spec_data.get("nodes") or {}
    spec_cards = spec_data.get("spec_cards") or []

    # Collect unique base pages used by nodes + spec_cards
    target_pages: List[str] = []
    node_for_page: Dict[str, str] = {}
    for nid, ndef in nodes_dict.items():
        if isinstance(ndef, dict) and ndef.get("page"):
            pid = str(ndef["page"])
            if pid not in target_pages:
                target_pages.append(pid)
            node_for_page.setdefault(pid, nid)
    for sc in spec_cards:
        if isinstance(sc, dict) and sc.get("page"):
            pid = str(sc["page"])
            if pid not in target_pages and pid in pages_dict:
                target_pages.append(pid)

    if not target_pages:
        return captured

    r_cmd, w_cmd = os.pipe()
    r_res, w_res = os.pipe()

    def _setup_fds() -> None:
        os.dup2(r_cmd, 3)
        os.dup2(w_res, 4)

    prof_dir = f"/tmp/openpm-wiki-shot-{os.getpid()}"
    shutil.rmtree(prof_dir, ignore_errors=True)
    proc = None
    try:
        proc = subprocess.Popen(
            [
                chrome_bin,
                "--headless=new",
                f"--user-data-dir={prof_dir}",
                "--no-sandbox",
                "--disable-gpu",
                "--hide-scrollbars",
                "--window-size=1600,1400",
                "--remote-debugging-pipe",
                "about:blank",
            ],
            pass_fds=(3, 4),
            preexec_fn=_setup_fds,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
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
                        raise RuntimeError("CDP pipe closed")
                    buf += chunk
                raw, buf = buf.split(b"\0", 1)
                msg = json.loads(raw.decode("utf-8"))
                if msg.get("id") == cid:
                    if "error" in msg:
                        raise RuntimeError(str(msg["error"]))
                    return msg.get("result") or {}

        def _eval(expr: str, await_p: bool = False) -> Any:
            r = _cdp("Runtime.evaluate", {"expression": expr, "returnByValue": True, "awaitPromise": await_p})
            return (r.get("result") or {}).get("value")

        targets = _cdp("Target.getTargets", use_sess=False).get("targetInfos") or []
        page_target = next(t for t in targets if t.get("type") == "page")
        session_id = _cdp(
            "Target.attachToTarget",
            {"targetId": page_target["targetId"], "flatten": True},
            use_sess=False,
        )["sessionId"]
        _cdp("Page.enable")
        _cdp("Runtime.enable")
        _cdp(
            "Emulation.setDeviceMetricsOverride",
            {"width": 1600, "height": 1400, "deviceScaleFactor": 1.5, "mobile": False},
        )
        _cdp("Page.navigate", {"url": wt_path.resolve().as_uri()})
        time.sleep(0.65)

        # Clean pure grayscale wireframe mode (no orange delta outlines, expand stage so full page height is visible!)
        _eval(
            """
            (() => {
              if (window.toggleDeltaHighlight) window.toggleDeltaHighlight(false);
              const st = document.createElement('style');
              st.textContent = `
                .insp-body, .stage { overflow: visible !important; max-height: none !important; height: auto !important; }
                .wb-stage, .flow-panel, .inspector-drawer { height: auto !important; min-height: 1200px !important; overflow: visible !important; }
              `;
              document.head.appendChild(st);
            })()
            """
        )

        for pid in target_pages:
            pdef = pages_dict.get(pid) if isinstance(pages_dict.get(pid), dict) else {}
            plat = str(pdef.get("platform") or "")
            nid = node_for_page.get(pid, "")
            js_switch = f"""
            new Promise(resolve => {{
              if ({json.dumps(plat)} && window.setVar) window.setVar('platform', {json.dumps(plat)});
              if ({json.dumps(nid)} && window.setViewByNode) window.setViewByNode({json.dumps(nid)});
              if (window.showPage) window.showPage({json.dumps(pid)});
              requestAnimationFrame(() => requestAnimationFrame(() => {{
                const el = document.getElementById({json.dumps(pid)}) || document.querySelector('.page.active');
                if (!el) return resolve(null);
                const r = el.getBoundingClientRect();
                resolve({{ x: Math.max(0, r.left), y: Math.max(0, r.top), width: Math.max(120, r.width), height: Math.max(80, r.height) }});
              }}));
            }})
            """
            rect = _eval(js_switch, await_p=True)
            if isinstance(rect, dict) and rect.get("width", 0) > 40:
                shot = _cdp(
                    "Page.captureScreenshot",
                    {
                        "format": "png",
                        "clip": {
                            "x": float(rect["x"]),
                            "y": float(rect["y"]),
                            "width": float(rect["width"]),
                            "height": float(min(rect["height"], 1250.0)),
                            "scale": 1.0,
                        },
                    },
                )
                out_png = screenshots_dir / f"{pid}.png"
                out_png.write_bytes(base64.b64decode(shot["data"]))
                captured[pid] = out_png

        # Also capture close-up component crops for spec_cards (for the nested `原型 | 说明` sub-table in 图2!)
        for sc in spec_cards:
            if not isinstance(sc, dict):
                continue
            cid = str(sc.get("id") or "").strip()
            pid = str(sc.get("page") or "").strip()
            anchor = str(sc.get("anchor") or "").strip()
            if not (cid and pid and anchor):
                continue
            js_crop = f"""
            new Promise(resolve => {{
              if (window.showPage) window.showPage({json.dumps(pid)});
              requestAnimationFrame(() => requestAnimationFrame(() => {{
                const pg = document.getElementById({json.dumps(pid)}) || document.querySelector('.page.active');
                if (!pg) return resolve(null);
                let target = pg.querySelector('[data-comp-id=' + JSON.stringify({json.dumps(anchor)}) + ']')
                          || pg.querySelector('[data-anchor=' + JSON.stringify({json.dumps(anchor)}) + ']');
                if (!target) return resolve(null);
                // Expand slightly to immediate form-row or card if control is tiny (< 72px tall) so close-up has context like 图2!
                const ctx = target.closest('.wt-card, .wt-modal, .wt-alert, .wt-field, tr');
                const boxEl = (ctx && ctx.getBoundingClientRect().height <= 260) ? ctx : target;
                const pr = pg.getBoundingClientRect();
                const br = boxEl.getBoundingClientRect();
                const pad = 12;
                const x = Math.max(pr.left, br.left - pad);
                const y = Math.max(pr.top, br.top - pad);
                const right = Math.min(pr.right, br.right + pad);
                const bottom = Math.min(pr.bottom, br.bottom + pad);
                resolve({{ x, y, width: Math.max(80, right - x), height: Math.max(36, bottom - y) }});
              }}));
            }})
            """
            crect = _eval(js_crop, await_p=True)
            if isinstance(crect, dict) and crect.get("width", 0) > 40:
                cshot = _cdp(
                    "Page.captureScreenshot",
                    {
                        "format": "png",
                        "clip": {
                            "x": float(crect["x"]),
                            "y": float(crect["y"]),
                            "width": float(crect["width"]),
                            "height": float(min(crect["height"], 400.0)),
                            "scale": 1.0,
                        },
                    },
                )
                safe_cid = re.sub(r"[^A-Za-z0-9_-]", "_", cid)
                comp_png = screenshots_dir / f"comp_{safe_cid}.png"
                comp_png.write_bytes(base64.b64decode(cshot["data"]))
                captured[f"comp_{safe_cid}"] = comp_png
    except Exception:
        pass
    finally:
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

    return captured


def _split_fine_grained_sections(prd_sections: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
    """Split H2 sections further on H3 (`### `) so each page-specific subsection maps cleanly to its own row!"""
    fine: List[Tuple[str, str]] = []
    for h2_title, sec_md in prd_sections:
        cur_t = h2_title
        cur_lines: List[str] = []
        has_h3 = False
        for ln in sec_md.splitlines():
            m3 = re.match(r"^#{2,4}\s+(.*)$", ln.strip())
            if m3:
                has_h3 = True
                if any(x.strip() for x in cur_lines):
                    fine.append((cur_t, "\n".join(cur_lines).strip()))
                cur_t = m3.group(1).strip()
                cur_lines = []
            else:
                cur_lines.append(ln)
        if any(x.strip() for x in cur_lines):
            fine.append((cur_t if has_h3 else h2_title, "\n".join(cur_lines).strip()))
    return fine


def _extract_prd_bullets(sec_md: str) -> List[str]:
    bullets: List[str] = []
    for raw in sec_md.splitlines():
        s = raw.strip()
        if not s or s.startswith("```") or s.startswith("|") or s == "---" or s.startswith("#"):
            continue
        s = re.sub(r"^>\s*(\[!NOTE\]|\[!IMPORTANT\]|\[!WARNING\]|\[!TIP\])?\s*", "", s)
        s = re.sub(r"^([-*+•]|\d+\.)\s+", "", s).strip()
        if s:
            bullets.append(s)
    return bullets


def build_fig2_rows(
    prd_sections: List[Tuple[str, str]],
    spec_data: Optional[Dict[str, Any]],
    screenshots_dir: Path,
    format_inline_xhtml_fn: Any,
    md_block_to_xhtml_fn: Any,
) -> List[Dict[str, Any]]:
    """Build 图2-style rows: 1 screen/module per row, left rendered PNG(s), right clean bullets + nested `原型 | 说明` sub-table."""
    rows: List[Dict[str, Any]] = []
    is_en = bool(
        isinstance(spec_data, dict)
        and str((spec_data.get("meta") or {}).get("lang") or "").lower().startswith("en")
    )

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

        # Map fine-grained H3/H2 PRD sections to a SINGLE specific page (do NOT dump multi-page overview tables into Row 1!)
        fine_sections = _split_fine_grained_sections(prd_sections)
        matched_sec_indices: set = set()
        page_groups: Dict[str, Dict[str, Any]] = {}
        page_order: List[str] = []

        for nid, ndef in nodes.items():
            if not isinstance(ndef, dict):
                continue
            pid = str(ndef.get("page") or nid)
            if pid not in page_groups:
                page_groups[pid] = {"nodes": [], "changes": set()}
                page_order.append(pid)
            page_groups[pid]["nodes"].append((nid, ndef))
            page_groups[pid]["changes"].add(str(ndef.get("change") or "unchanged"))

        all_base_pids = set(page_order)

        for pid in page_order:
            grp = page_groups[pid]
            grp_nodes: List[Tuple[str, Dict[str, Any]]] = grp["nodes"]
            primary_nid, primary_ndef = grp_nodes[0]
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

            # Collect primary screenshot (plus optional mobile companion or state screenshot if present)
            shots: List[Path] = []
            main_shot = screenshots_dir / f"{pid}.png"
            if main_shot.is_file():
                shots.append(main_shot)

            bullets_xhtml: List[str] = []
            bullets_plain: List[str] = []
            sub_rows: List[Dict[str, Any]] = []

            # 1. Node business annotations
            for nid, ndef in grp_nodes:
                annos = ndef.get("anno")
                if isinstance(annos, list):
                    for pair in annos:
                        if isinstance(pair, list) and len(pair) >= 2:
                            k_txt, v_txt = str(pair[0]).strip(), str(pair[1]).strip()
                            bullets_xhtml.append(f"<p>&#183; <strong>{_xe(k_txt)}</strong>：{_xe(v_txt)}</p>")
                            bullets_plain.append(f"· {k_txt}：{v_txt}")

            # 2. Match fine-grained PRD subsections scoped specifically to THIS page!
            match_tokens = {pid} | {nid for nid, _ in grp_nodes}
            other_pids = all_base_pids - {pid}
            extra_xhtml_blocks: List[str] = []
            for s_idx, (s_title, s_md) in enumerate(fine_sections):
                if s_idx in matched_sec_indices:
                    continue
                in_title = any(tok in s_title for tok in match_tokens)
                in_body = any(tok in s_md for tok in match_tokens)
                mentions_other_pages = sum(1 for op in other_pids if op in s_md or op in s_title)
                if (in_title or in_body) and mentions_other_pages == 0:
                    matched_sec_indices.add(s_idx)
                    extra_xhtml_blocks.append(md_block_to_xhtml_fn(s_md))
                    for b in _extract_prd_bullets(s_md)[:6]:
                        plain_b = re.sub(r"\*\*([^*]+)\*\*", r"\1", b)
                        plain_b = re.sub(r"`([^`]+)`", r"\1", plain_b)
                        bullets_plain.append(f"· {plain_b}")

            # 3. Build 图2-style nested `原型 | 说明` sub-table from spec_cards + decision branches!
            for sc in cards_by_page.get(pid, []):
                cid = str(sc.get("id") or "").strip()
                safe_cid = re.sub(r"[^A-Za-z0-9_-]", "_", cid)
                comp_shot = screenshots_dir / f"comp_{safe_cid}.png"
                sc_title = str(sc.get("title") or cid)
                sc_body = str(sc.get("body") or "")
                sub_rows.append(
                    {
                        "shot": comp_shot if comp_shot.is_file() else None,
                        "label": sc_title,
                        "desc_xhtml": f"<p>&#183; <strong>{_xe(sc_title)}</strong>：{_xe(sc_body)}</p>",
                        "desc_plain": f"· {sc_title}：{sc_body}",
                    }
                )

            for nid, ndef in grp_nodes:
                bvar_id = ndef.get("branchVar")
                if ndef.get("isDecision") and isinstance(bvar_id, str) and bvar_id in vars_by_id:
                    bvar = vars_by_id[bvar_id]
                    bvar_label = str(bvar.get("label") or bvar_id)
                    opts = [o for o in (bvar.get("options") or []) if isinstance(o, dict)]
                    if opts:
                        opt_lines_x = []
                        opt_lines_p = []
                        for o in opts:
                            tgt_id = str(o.get("target") or "-")
                            tgt_title = str((nodes.get(tgt_id) or {}).get("title") or tgt_id)
                            lbl = str(o.get("label") or o.get("id") or "")
                            opt_lines_x.append(f"<p>&#183; <strong>{_xe(lbl)}</strong> &#8594; {_xe(tgt_title)}</p>")
                            opt_lines_p.append(f"· {lbl} → {tgt_title}")
                        sub_rows.append(
                            {
                                "shot": None,
                                "label": f"{bvar_label}" + (" (Branch)" if is_en else "（分支判断）"),
                                "desc_xhtml": "".join(opt_lines_x),
                                "desc_plain": "\n".join(opt_lines_p),
                            }
                        )

            # Compose right_xhtml cleanly like 图2
            right_chunks: List[str] = [f"<p><strong>{_xe(heading)}</strong></p>"]
            right_chunks.extend(bullets_xhtml)
            right_chunks.extend(extra_xhtml_blocks)

            if sub_rows:
                th_left = "Prototype / State" if is_en else "原型"
                th_right = "Specification" if is_en else "说明"
                sub_trs_html: List[str] = [f"<tr><th>{th_left}</th><th>{th_right}</th></tr>"]
                sub_trs_xml: List[str] = [f"<tr><th>{th_left}</th><th>{th_right}</th></tr>"]
                for sr in sub_rows:
                    cshot: Optional[Path] = sr["shot"]
                    if cshot is not None:
                        b64_c = base64.b64encode(cshot.read_bytes()).decode("ascii")
                        left_h = f'<img class="sub-shot" src="data:image/png;base64,{b64_c}" alt="{_xe(sr["label"])}" />'
                        left_x = (
                            f'<p><ac:image ac:width="220">'
                            f'<ri:attachment ri:filename="{_xe(cshot.name)}" />'
                            f"</ac:image></p>"
                        )
                    else:
                        left_h = f"<strong>{_xe(sr['label'])}</strong>"
                        left_x = f"<p><strong>{_xe(sr['label'])}</strong></p>"
                    sub_trs_html.append(f"<tr><td class=\"sub-col-proto\">{left_h}</td><td>{sr['desc_xhtml']}</td></tr>")
                    sub_trs_xml.append(f"<tr><td>{left_x}</td><td>{sr['desc_xhtml']}</td></tr>")

                right_chunks_html = list(right_chunks) + [
                    f'<table class="nested-table"><tbody>{"".join(sub_trs_html)}</tbody></table>'
                ]
                right_chunks_xml = list(right_chunks) + [
                    f'<table class="nested-table"><tbody>{"".join(sub_trs_xml)}</tbody></table>'
                ]
            else:
                right_chunks_html = list(right_chunks)
                right_chunks_xml = list(right_chunks)

            rows.append(
                {
                    "label_id": pid,
                    "subtitle": heading,
                    "screenshot": shots[0] if shots else None,
                    "screenshots": shots,
                    "heading": heading,
                    "bullets_plain": bullets_plain,
                    "sub_rows": sub_rows,
                    "right_xhtml_html": "\n".join(right_chunks_html),
                    "right_xhtml": "\n".join(right_chunks_xml),
                }
            )

        # Append only non-redundant global sections (e.g. Data Metrics / Edge Cases / Permissions) at the bottom
        for s_idx, (s_title, s_md) in enumerate(fine_sections):
            if s_idx in matched_sec_indices or not s_md.strip():
                continue
            # Skip front-overview summary tables that already list >= 2 base pages covered above
            if sum(1 for op in all_base_pids if op in s_md) >= 2:
                continue
            b_plain = [
                "· " + re.sub(r"`([^`]+)`", r"\1", re.sub(r"\*\*([^*]+)\*\*", r"\1", b))
                for b in _extract_prd_bullets(s_md)
            ]
            x_body = f"<p><strong>{_xe(s_title)}</strong></p>\n{md_block_to_xhtml_fn(s_md)}"
            rows.append(
                {
                    "label_id": "全局说明" if not is_en else "Global Rules",
                    "subtitle": s_title,
                    "screenshot": None,
                    "screenshots": [],
                    "heading": s_title,
                    "bullets_plain": b_plain or [s_md.strip()[:400]],
                    "sub_rows": [],
                    "right_xhtml_html": x_body,
                    "right_xhtml": x_body,
                }
            )
        return rows

    # Fallback when no spec.json exists
    for sec_idx, (sec_title, sec_md) in enumerate(prd_sections, start=1):
        x_body = f"<p><strong>{_xe(sec_title)}</strong></p>\n{md_block_to_xhtml_fn(sec_md)}"
        b_plain = ["· " + b for b in _extract_prd_bullets(sec_md)]
        rows.append(
            {
                "label_id": f"SEC-{sec_idx}",
                "subtitle": sec_title,
                "screenshot": None,
                "screenshots": [],
                "heading": sec_title,
                "bullets_plain": b_plain,
                "sub_rows": [],
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
    """Render 图2-identical HTML with Base64-inlined PNGs and 1-click Copy Rich Table for WeCom / Feishu Docs."""
    tr_list: List[str] = []
    for idx, row in enumerate(rows, start=1):
        shots: List[Path] = row.get("screenshots") or ([row["screenshot"]] if row.get("screenshot") else [])
        if shots:
            imgs = []
            for sp in shots:
                if sp and sp.is_file():
                    b64 = base64.b64encode(sp.read_bytes()).decode("ascii")
                    imgs.append(f'<img class="wf-shot" src="data:image/png;base64,{b64}" alt="{_xe(row["subtitle"])}" />')
            left_cell = "".join(imgs)
        else:
            left_cell = f'<div class="wf-global-tag">{_xe(row["subtitle"])}</div>'

        right_html = row.get("right_xhtml_html") or row.get("right_xhtml") or ""
        tr_list.append(
            "<tr>"
            f'<td class="col-idx">{idx}</td>'
            f'<td class="col-page">{left_cell}</td>'
            f'<td class="col-spec">{right_html}</td>'
            "</tr>"
        )

    sec_hd = "Product Specification" if is_en else "产品方案"
    proto_lbl = "Interactive Prototype: " if is_en else "交互原型："
    dl_txt = "(Click to Download)" if is_en else "（点击下载）"
    copy_btn = "Copy Rich Table (Paste into WeCom / Feishu Doc)" if is_en else "一键复制左图右文全表（可直接粘贴至企微在线文档 / 飞书）"
    copied_txt = "Copied! Paste directly into WeCom / Feishu Doc" if is_en else "已复制图文表格！请直接 Cmd/Ctrl+V 粘贴到企业微信文档"
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
    margin: 0; padding: 24px 32px; background: #ffffff; color: #172b4d;
    font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", sans-serif;
    font-size: 14px; line-height: 1.65;
  }}
  .doc-wrap {{ max-width: 1320px; margin: 0 auto; }}
  .doc-toolbar {{
    display: flex; align-items: center; justify-content: space-between; gap: 12px;
    padding: 10px 14px; margin-bottom: 18px; background: #f7f7f8; border: 1px solid #dfe1e6; border-radius: 6px;
  }}
  .doc-toolbar button {{
    background: #262626; color: #ffffff; border: none; border-radius: 5px;
    padding: 7px 14px; font-size: 13px; font-weight: 600; cursor: pointer;
  }}
  .doc-toolbar button:hover {{ background: #111111; }}
  h2.scheme-hd {{ margin: 0 0 8px; font-size: 20px; font-weight: 700; color: #172b4d; }}
  .proto-link-line {{ margin: 0 0 14px; font-size: 13.5px; color: #333333; }}
  .proto-link-line a {{ color: #0052cc; text-decoration: none; }}
  .proto-link-line a:hover {{ text-decoration: underline; }}
  table.main-table {{ width: 100%; border-collapse: collapse; table-layout: fixed; border: 1px solid #dfe1e6; }}
  table.main-table > thead > tr > th,
  table.main-table > tbody > tr > td {{
    border: 1px solid #dfe1e6; padding: 12px 14px; vertical-align: top; text-align: left;
  }}
  table.main-table > thead > tr > th {{ background: #f4f5f7; color: #172b4d; font-weight: 700; font-size: 13.5px; }}
  .col-idx {{ width: 56px; color: #172b4d; }}
  .col-page {{ width: 340px; background: #ffffff; }}
  .col-spec {{ width: auto; word-break: break-word; }}
  .wf-shot {{ display: block; width: 100%; height: auto; border: 1px solid #dfe1e6; border-radius: 4px; margin-bottom: 8px; }}
  .wf-shot:last-child {{ margin-bottom: 0; }}
  .wf-global-tag {{
    padding: 10px 12px; background: #f4f5f7; border: 1px solid #dfe1e6; border-radius: 4px;
    font-weight: 600; color: #42526e; font-size: 13px; text-align: center;
  }}
  table.nested-table {{ width: 100%; border-collapse: collapse; margin: 10px 0 4px; font-size: 13px; }}
  table.nested-table th, table.nested-table td {{ border: 1px solid #dfe1e6; padding: 8px 10px; vertical-align: top; text-align: left; }}
  table.nested-table th {{ background: #f4f5f7; font-weight: 700; color: #172b4d; }}
  .sub-col-proto {{ width: 240px; }}
  .sub-shot {{ display: block; max-width: 220px; width: 100%; height: auto; border: 1px solid #dfe1e6; border-radius: 3px; }}
  p {{ margin: 0 0 6px; }}
  ul {{ margin: 0 0 8px; padding-left: 18px; }}
  code {{ font-family: ui-monospace, monospace; font-size: 12px; background: #f4f5f7; padding: 1px 4px; border-radius: 3px; }}
  @media print {{ .doc-toolbar {{ display: none; }} body {{ padding: 0; }} }}
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
    """Render 图2-identical Confluence 7.4+ Storage XML (`产品方案` + 3-col `序号 | 页面 | 需求说明` + nested `原型 | 说明`)."""
    tr_chunks: List[str] = []
    for idx, row in enumerate(rows, start=1):
        shots: List[Path] = row.get("screenshots") or ([row["screenshot"]] if row.get("screenshot") else [])
        valid_shots = [sp for sp in shots if sp and sp.is_file()]
        if valid_shots:
            left_visual = "".join(
                f'<p><ac:image ac:width="310"><ri:attachment ri:filename="{_xe(sp.name)}" /></ac:image></p>'
                for sp in valid_shots
            )
        else:
            left_visual = f"<p><strong>{_xe(row['subtitle'])}</strong></p>"

        tr_chunks.append(
            "<tr>"
            f"<td><p>{idx}</p></td>"
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
        '<col style="width: 56px;" />'
        '<col style="width: 340px;" />'
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
    """Write a zero-dependency Office Open XML `.docx` matching 图2 (`序号 | 页面 | 需求说明` + embedded PNGs + nested `原型 | 说明`).

    Enterprise WeChat (企业微信文档 -> 导入本地文档, or WeDrive click-to-open), Feishu Docs, WPS, and Word
    render this directly as a native collaborative online document with all images & nested tables intact.
    """
    media_entries: List[Tuple[str, str, Path]] = []  # (rId, media_filename, path)
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
        scale = min(1.0, float(max_w_px) / float(max(1, orig_w)))
        cx = int(round(orig_w * scale * 9525))
        cy = int(round(orig_h * scale * 9525))
        return rid, cx, cy

    def _w_p_text(txt: str, bold: bool = False, size_half_pt: int = 20, color: str = "172B4D") -> str:
        b_xml = "<w:b/><w:bCs/>" if bold else ""
        return (
            "<w:p><w:pPr><w:spacing w:before=\"40\" w:after=\"60\"/></w:pPr>"
            f"<w:r><w:rPr>{b_xml}<w:color w:val=\"{color}\"/>"
            f"<w:sz w:val=\"{size_half_pt}\"/><w:szCs w:val=\"{size_half_pt}\"/></w:rPr>"
            f"<w:t xml:space=\"preserve\">{_xe(txt)}</w:t></w:r></w:p>"
        )

    def _w_p_img(p: Path, max_w_px: int, doc_pr_id: int) -> str:
        rid, cx, cy = _register_img(p, max_w_px=max_w_px)
        return (
            "<w:p><w:pPr><w:spacing w:before=\"40\" w:after=\"80\"/></w:pPr><w:r><w:drawing>"
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
        "<w:top w:val=\"single\" w:sz=\"6\" w:space=\"0\" w:color=\"DFE1E6\"/>"
        "<w:left w:val=\"single\" w:sz=\"6\" w:space=\"0\" w:color=\"DFE1E6\"/>"
        "<w:bottom w:val=\"single\" w:sz=\"6\" w:space=\"0\" w:color=\"DFE1E6\"/>"
        "<w:right w:val=\"single\" w:sz=\"6\" w:space=\"0\" w:color=\"DFE1E6\"/>"
        "<w:insideH w:val=\"single\" w:sz=\"6\" w:space=\"0\" w:color=\"DFE1E6\"/>"
        "<w:insideV w:val=\"single\" w:sz=\"6\" w:space=\"0\" w:color=\"DFE1E6\"/>"
        "</w:tblBorders>"
    )
    cell_mar = (
        "<w:tblCellMar>"
        "<w:top w:w=\"120\" w:type=\"dxa\"/>"
        "<w:left w:w=\"150\" w:type=\"dxa\"/>"
        "<w:bottom w:w=\"120\" w:type=\"dxa\"/>"
        "<w:right w:w=\"150\" w:type=\"dxa\"/>"
        "</w:tblCellMar>"
    )

    th_1 = "No." if is_en else "序号"
    th_2 = "Screen" if is_en else "页面"
    th_3 = "Specification" if is_en else "需求说明"
    sub_th_1 = "Prototype" if is_en else "原型"
    sub_th_2 = "Specification" if is_en else "说明"
    sec_hd = "Product Specification" if is_en else "产品方案"
    proto_line = (
        f"Interactive Prototype: {zip_filename} ({version_str})"
        if is_en
        else f"交互原型：{zip_filename}（版本 {version_str}）"
    )

    # Landscape A4 content width = 16838 - 1440 = 15398 dxa (~1026px): col1=800, col2=4800, col3=9798
    doc_pr_seq = 1
    tr_xml_list: List[str] = [
        "<w:tr>"
        f"<w:tc><w:tcPr><w:tcW w:w=\"800\" w:type=\"dxa\"/><w:shd w:val=\"clear\" w:fill=\"F4F5F7\"/></w:tcPr>{_w_p_text(th_1, bold=True)}</w:tc>"
        f"<w:tc><w:tcPr><w:tcW w:w=\"4800\" w:type=\"dxa\"/><w:shd w:val=\"clear\" w:fill=\"F4F5F7\"/></w:tcPr>{_w_p_text(th_2, bold=True)}</w:tc>"
        f"<w:tc><w:tcPr><w:tcW w:w=\"9798\" w:type=\"dxa\"/><w:shd w:val=\"clear\" w:fill=\"F4F5F7\"/></w:tcPr>{_w_p_text(th_3, bold=True)}</w:tc>"
        "</w:tr>"
    ]

    for idx, row in enumerate(rows, start=1):
        shots: List[Path] = row.get("screenshots") or ([row["screenshot"]] if row.get("screenshot") else [])
        valid_shots = [sp for sp in shots if sp and sp.is_file()]
        if valid_shots:
            left_ps = []
            for sp in valid_shots:
                doc_pr_seq += 1
                left_ps.append(_w_p_img(sp, max_w_px=300, doc_pr_id=doc_pr_seq))
            left_cell_xml = "".join(left_ps)
        else:
            left_cell_xml = _w_p_text(str(row.get("subtitle") or "-"), bold=True, color="42526E")

        right_ps: List[str] = [_w_p_text(str(row.get("heading") or row.get("subtitle") or ""), bold=True, size_half_pt=21)]
        for b_line in row.get("bullets_plain") or []:
            right_ps.append(_w_p_text(b_line, bold=False, size_half_pt=19))

        sub_rows = row.get("sub_rows") or []
        if sub_rows:
            sub_trs = [
                "<w:tr>"
                f"<w:tc><w:tcPr><w:tcW w:w=\"3200\" w:type=\"dxa\"/><w:shd w:val=\"clear\" w:fill=\"F4F5F7\"/></w:tcPr>{_w_p_text(sub_th_1, bold=True, size_half_pt=18)}</w:tc>"
                f"<w:tc><w:tcPr><w:tcW w:w=\"6200\" w:type=\"dxa\"/><w:shd w:val=\"clear\" w:fill=\"F4F5F7\"/></w:tcPr>{_w_p_text(sub_th_2, bold=True, size_half_pt=18)}</w:tc>"
                "</w:tr>"
            ]
            for sr in sub_rows:
                cshot: Optional[Path] = sr.get("shot")
                if cshot and cshot.is_file():
                    doc_pr_seq += 1
                    sub_left = _w_p_img(cshot, max_w_px=195, doc_pr_id=doc_pr_seq)
                else:
                    sub_left = _w_p_text(str(sr.get("label") or "-"), bold=True, size_half_pt=18)
                sub_right_ps = [
                    _w_p_text(ln, bold=False, size_half_pt=18)
                    for ln in str(sr.get("desc_plain") or "").splitlines()
                    if ln.strip()
                ] or [_w_p_text("-", size_half_pt=18)]
                sub_trs.append(
                    "<w:tr>"
                    f"<w:tc><w:tcPr><w:tcW w:w=\"3200\" w:type=\"dxa\"/></w:tcPr>{sub_left}</w:tc>"
                    f"<w:tc><w:tcPr><w:tcW w:w=\"6200\" w:type=\"dxa\"/></w:tcPr>{''.join(sub_right_ps)}</w:tc>"
                    "</w:tr>"
                )
            nested_tbl_xml = (
                "<w:tbl>"
                f"<w:tblPr><w:tblW w:w=\"9400\" w:type=\"dxa\"/>{tbl_borders}{cell_mar}</w:tblPr>"
                "<w:tblGrid><w:gridCol w:w=\"3200\"/><w:gridCol w:w=\"6200\"/></w:tblGrid>"
                f"{''.join(sub_trs)}"
                "</w:tbl>"
                "<w:p/>"  # Mandatory trailing paragraph after nested <w:tbl> inside <w:tc> per OOXML spec!
            )
            right_ps.append(nested_tbl_xml)

        tr_xml_list.append(
            "<w:tr>"
            f"<w:tc><w:tcPr><w:tcW w:w=\"800\" w:type=\"dxa\"/></w:tcPr>{_w_p_text(str(idx), bold=False)}</w:tc>"
            f"<w:tc><w:tcPr><w:tcW w:w=\"4800\" w:type=\"dxa\"/></w:tcPr>{left_cell_xml}</w:tc>"
            f"<w:tc><w:tcPr><w:tcW w:w=\"9798\" w:type=\"dxa\"/></w:tcPr>{''.join(right_ps)}</w:tc>"
            "</w:tr>"
        )

    document_xml = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<w:document xmlns:w=\"http://schemas.openxmlformats.org/wordprocessingml/2006/main\" "
        "xmlns:r=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships\" "
        "xmlns:wp=\"http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing\">"
        "<w:body>"
        f"{_w_p_text(title + ' · ' + sec_hd, bold=True, size_half_pt=28)}"
        f"{_w_p_text(proto_line, bold=False, size_half_pt=19, color='42526E')}"
        "<w:tbl>"
        f"<w:tblPr><w:tblW w:w=\"15398\" w:type=\"dxa\"/>{tbl_borders}{cell_mar}</w:tblPr>"
        "<w:tblGrid><w:gridCol w:w=\"800\"/><w:gridCol w:w=\"4800\"/><w:gridCol w:w=\"9798\"/></w:tblGrid>"
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
