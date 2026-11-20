#!/usr/bin/env python3
"""Three-Zone Left-Prototype / Right-Specification Document Builder (Confluence & WeCom Online Doc).

Document Architecture (Three-Zone Golden Layout):
  Zone 1 — Pre-Table Global Intro (100% Full-Width):
    - Lead overview, Background & Goals (`背景与目标`), Scope & Non-Goals (`范围边界`),
      Terminology / Roles (`术语解释 / 角色职责`), and End-to-End Flow (`主流程`) with
      auto-rendered 100% pure-grayscale `flow-overview.png` (`flow.svg`) embedded!
  Zone 2 — Center Product Scheme Table (`序号 | 页面 | 需求说明`):
    - Strictly ONLY prototype-backed screen entries (zero empty-screenshot global rows!).
    - Pairs all `variant_of` platform variants (`Web / PC` + `App 375px`) in 100% pure grayscale.
    - Aggregates ALL page-level `F-xx` / `4.x` field & interaction subsections into the matching
      screen's right column (via explicit `page_id` tags + DOM/component vocabulary matching),
      with zero recursive `原型 | 说明` sub-table nesting and zero duplicate rules.
  Zone 3 — Post-Table Global Engineering & Acceptance Appendix (100% Full-Width):
    - Cross-page rules (default memory, historical compatibility, non-prototype layout tweaks),
      telemetry/metrics, non-functional SLAs, acceptance cases (AC), and open items (`待确认`).
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
SCREENSHOT_DPR = 2.0

PRE_CHAPTER_RE = re.compile(
    r"(背景|目标|痛点|概述|价值|定位|范围|不做|术语|名词|定义|缩略语|角色|职责|主流程|业务流程|核心流程|全局流程|端到端|状态流转|"
    r"overview|background|problem|goal|objective|scope|non-goal|glossary|terminology|definition|role|actor|workflow|main\s*flow|end-to-end)",
    re.IGNORECASE,
)
FLOW_CHAPTER_RE = re.compile(
    r"(主流程|业务流程|核心流程|全局流程|端到端|流程与状态|判断路由|workflow|main\s*flow|end-to-end|flow\s*&\s*state)",
    re.IGNORECASE,
)
POST_CHAPTER_RE = re.compile(
    r"(默认配置记忆|配置记忆|历史数据|兼容|迁移|存量|埋点|数据统计|监控|指标|非功能|性能|安全|合规|权限矩阵|异常边界|"
    r"待确认|研发核实|开放问题|风险|排期|里程碑|验收用例|验收标准|测试用例|附录|变更记录|"
    r"compatibility|migration|legacy|telemetry|tracking|analytics|metrics|non-functional|sla|security|"
    r"open\s*question|tbd|risk|acceptance|test\s*case|appendix|changelog)",
    re.IGNORECASE,
)
GENERIC_COMP_WORDS = (
    "按钮", "输入框", "下拉框", "选择框", "复选框", "单选框", "开关", "弹窗", "窗口", "浮层", "抽屉",
    "卡片", "列表", "表格", "标签", "区域", "模块", "页面", "设置页", "详情页", "结果页", "文本",
    "button", "input", "select", "modal", "drawer", "card", "table", "list", "panel", "page", "tab",
)


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


def _infer_platform(pid: str, pdef: Dict[str, Any]) -> str:
    explicit = str(pdef.get("platform") or "").strip().lower()
    if explicit:
        return explicit
    low_id = pid.lower()
    frame = str(pdef.get("frame") or "").strip().lower()
    if low_id.endswith("-app") or "-app-" in low_id or low_id.startswith("p-app-") or frame == "phone":
        return "app"
    if low_id.endswith("-pc") or "-pc-" in low_id or low_id.startswith("p-pc-"):
        return "pc"
    if frame == "wide":
        return "web"
    return ""


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

    for cand_pid, pdef in pages_dict.items():
        if isinstance(pdef, dict) and not pdef.get("variant_of") and cand_pid not in base_pages:
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
    """Capture 100% pure-grayscale PNGs for `flow.svg`, all base pages, and all `variant_of` platform variants."""
    screenshots_dir.mkdir(parents=True, exist_ok=True)
    ordered_pages, _, node_for_page = _collect_expected_pages(spec_data)
    flow_svg_path = project_dir / "flow.svg"
    if not ordered_pages and not flow_svg_path.is_file():
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

    pages_dict = (spec_data or {}).get("pages") or {}
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

        # 1. Capture prototype pages & variants from walkthrough.html
        if wt_path.is_file() and ordered_pages:
            _cdp("Page.navigate", {"url": wt_path.resolve().as_uri()})
            time.sleep(0.65)
            _eval(
                """
                (() => {
                  if (window.setWbTheme) window.setWbTheme('light', false);
                  document.body.classList.remove('wb-dark');
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

            for pid in ordered_pages:
                pdef = pages_dict.get(pid) if isinstance(pages_dict.get(pid), dict) else {}
                plat = _infer_platform(pid, pdef)
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

        # 2. Capture crisp 100% pure-grayscale global flowchart (`flow.svg` -> `flow-overview.png`) for Zone 1 Intro!
        if flow_svg_path.is_file():
            svg_raw = flow_svg_path.read_text(encoding="utf-8", errors="ignore")
            flow_wrapper_html = (
                "<!doctype html><html><head><meta charset='utf-8'><style>"
                "html,body{margin:0;padding:20px;background:#ffffff;display:inline-block;"
                "filter:grayscale(100%) !important;-webkit-filter:grayscale(100%) !important;}"
                "svg{display:block;max-width:1040px;height:auto;background:#ffffff;}"
                "</style></head><body><div id='fwrap'>" + svg_raw + "</div></body></html>"
            )
            data_url = "data:text/html;charset=utf-8," + base64.b64encode(flow_wrapper_html.encode("utf-8")).decode("ascii")
            # Navigate via Page.setDocumentContent for instant zero-URL-length-limit rendering!
            _cdp("Page.navigate", {"url": "about:blank"})
            ftree = _cdp("Page.getFrameTree")
            root_frame_id = ftree["frameTree"]["frame"]["id"]
            _cdp("Page.setDocumentContent", {"frameId": root_frame_id, "html": flow_wrapper_html})
            time.sleep(0.25)
            frect = _eval(
                """
                (() => {
                  const el = document.getElementById('fwrap');
                  if (!el) return null;
                  const r = el.getBoundingClientRect();
                  return { x: 0, y: 0, width: Math.ceil(r.width + 40), height: Math.ceil(r.height + 40) };
                })()
                """
            )
            if isinstance(frect, dict) and frect.get("width", 0) >= 80:
                _cdp(
                    "Emulation.setDeviceMetricsOverride",
                    {
                        "width": max(800, int(frect["width"])),
                        "height": max(600, int(frect["height"])),
                        "deviceScaleFactor": SCREENSHOT_DPR,
                        "mobile": False,
                    },
                )
                time.sleep(0.1)
                fshot = _cdp(
                    "Page.captureScreenshot",
                    {
                        "format": "png",
                        "clip": {
                            "x": 0.0,
                            "y": 0.0,
                            "width": float(frect["width"]),
                            "height": float(min(frect["height"], 1800.0)),
                            "scale": 1.0,
                        },
                    },
                )
                flow_png = screenshots_dir / "flow-overview.png"
                flow_png.write_bytes(base64.b64decode(fshot["data"]))
                captured["flow-overview"] = flow_png

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


def _split_h3_subsections(sec_title: str, sec_md: str) -> List[Tuple[str, str]]:
    """Split a functional H2 chapter on `### ` / `#### ` into individual feature items (`F-01`, `F-02`, `4.1`, etc.)."""
    subs: List[Tuple[str, str]] = []
    cur_t = sec_title
    cur_lines: List[str] = []
    has_sub = False
    for ln in sec_md.splitlines():
        m = re.match(r"^#{3,4}\s+(.*)$", ln.strip())
        if m:
            has_sub = True
            if any(x.strip() for x in cur_lines):
                subs.append((cur_t, "\n".join(cur_lines).strip()))
            cur_t = m.group(1).strip()
            cur_lines = []
        else:
            cur_lines.append(ln)
    if any(x.strip() for x in cur_lines):
        subs.append((cur_t if has_sub else sec_title, "\n".join(cur_lines).strip()))
    return subs


def _clean_display_heading(raw_title: str) -> str:
    """Strip internal page/node ID annotations like `（p-usage-dash / p-app-usage-dash）` from reader-facing titles."""
    cleaned = re.sub(
        r"\s*[（(][^()（）]*\b(?:p-[a-z0-9_-]+|page_[a-z0-9_-]+)\b[^()（）]*[)）]",
        "",
        raw_title,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"<!--.*?-->", "", cleaned).strip()
    return cleaned or raw_title.strip()


def _normalize_dedup_key(txt: str) -> str:
    s = re.sub(r"[`*_#\s·•:：,，.。;；()（）\[\]【】/-]+", "", txt.lower())
    return s[:28]


def _extract_prd_plain_blocks(sec_md: str) -> List[Dict[str, Any]]:
    """Parse a Markdown section into structured blocks (`heading`, `text`, `table`) for `.docx` rendering."""
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

        hm = re.match(r"^(#{2,6})\s+(.*)$", s)
        if hm:
            blocks.append({"kind": "text", "text": _clean_display_heading(hm.group(2)), "bold": True})
            i += 1
            continue

        clean = re.sub(r"^>\s*(\[!NOTE\]|\[!IMPORTANT\]|\[!WARNING\]|\[!TIP\])?\s*", "", s)
        is_bullet = bool(re.match(r"^([-*+•]|\d+\.)\s+", clean))
        clean = re.sub(r"^([-*+•]|\d+\.)\s+", "", clean).strip()
        clean = re.sub(r"`([^`]+)`", r"\1", re.sub(r"\*\*([^*]+)\*\*", r"\1", clean))
        if clean:
            prefix = "· " if is_bullet else ""
            blocks.append({"kind": "text", "text": f"{prefix}{clean}", "bold": False})
        i += 1
    return blocks


def _build_page_vocabulary(
    project_dir: Path,
    base_pid: str,
    variant_pids: List[str],
    pages: Dict[str, Any],
    grp_nodes: List[Tuple[str, Dict[str, Any]]],
    spec_cards: List[Any],
) -> Tuple[List[str], str]:
    """Build (high_signal_phrases, visible_dom_corpus) for a base prototype screen + its variants."""
    phrases: List[str] = []
    dom_texts: List[str] = []

    all_pids = [base_pid] + list(variant_pids)
    for pid in all_pids:
        pdef = pages.get(pid) if isinstance(pages.get(pid), dict) else {}
        ptitle = str(pdef.get("title") or "")
        if ptitle:
            clean_pt = re.sub(r"[（(].*?[)）]", "", ptitle).strip()
            if len(clean_pt) >= 2:
                phrases.append(clean_pt)
        for comp in pdef.get("components") or []:
            if isinstance(comp, dict) and comp.get("comp_name"):
                cname = str(comp["comp_name"]).strip()
                stripped = cname
                for gw in GENERIC_COMP_WORDS:
                    stripped = re.sub(re.escape(gw) + r"$", "", stripped, flags=re.IGNORECASE).strip()
                if len(stripped) >= 2:
                    phrases.append(stripped)
                if len(cname) >= 2:
                    phrases.append(cname)

        # Read actual visible text inside `pages/<pid>.html`!
        html_file = project_dir / "pages" / f"{pid}.html"
        if html_file.is_file():
            raw_h = html_file.read_text(encoding="utf-8", errors="ignore")
            no_script = re.sub(r"<(script|style)\b[^>]*>.*?</\1>", " ", raw_h, flags=re.DOTALL | re.IGNORECASE)
            vis_txt = re.sub(r"<[^>]+>", " ", no_script)
            dom_texts.append(" ".join(vis_txt.split()))

    for _, ndef in grp_nodes:
        nt = str(ndef.get("title") or "").strip()
        if len(nt) >= 2:
            phrases.append(re.sub(r"^判断[:：]\s*", "", nt).rstrip("?？"))
        for pair in ndef.get("anno") or []:
            if isinstance(pair, list) and len(pair) >= 2:
                if len(str(pair[0]).strip()) >= 2:
                    phrases.append(str(pair[0]).strip())
                dom_texts.append(str(pair[1]))

    for sc in spec_cards:
        if isinstance(sc, dict):
            sc_p = str(sc.get("page") or "")
            v_of = str((pages.get(sc_p) or {}).get("variant_of") or "") if isinstance(pages.get(sc_p), dict) else ""
            if (v_of or sc_p) == base_pid:
                if sc.get("title"):
                    phrases.append(str(sc["title"]))
                if sc.get("body"):
                    dom_texts.append(str(sc["body"]))

    # Deduplicate phrases preserving order
    uniq_phrases: List[str] = []
    for ph in phrases:
        if ph and ph not in uniq_phrases:
            uniq_phrases.append(ph)
    return uniq_phrases, " ".join(dom_texts).lower()


def _match_subsection_to_page(
    sub_title: str,
    sub_md: str,
    page_order: List[str],
    page_tokens_map: Dict[str, set],
    page_explicit_refs: Dict[str, set],
    page_vocab_map: Dict[str, Tuple[List[str], str]],
) -> Optional[str]:
    """Match a functional PRD subsection (`F-01`, `4.1`, etc.) to its best base `page_id`, or `None` if non-UI."""
    combined = f"{sub_title}\n{sub_md}"

    # 1. Explicit `prd_sections` list on `spec.json -> pages[pid]` (e.g. "F-01")
    f_code_match = re.search(r"\b(F-\d+(?:\.\d+)?)\b", sub_title, re.IGNORECASE)
    f_code = f_code_match.group(1).upper() if f_code_match else ""
    if f_code:
        for pid in page_order:
            if f_code in page_explicit_refs.get(pid, set()):
                return pid

    # 2. Explicit `p-xxx` or `F_NODE` identifier in title or body (when unambiguous to 1 base page)
    title_hits = [
        pid
        for pid in page_order
        if any(re.search(rf"(?<![A-Za-z0-9_-]){re.escape(tok)}(?![A-Za-z0-9_-])", sub_title) for tok in page_tokens_map[pid])
    ]
    if len(title_hits) == 1:
        return title_hits[0]

    body_hits = [
        pid
        for pid in page_order
        if any(re.search(rf"(?<![A-Za-z0-9_-]){re.escape(tok)}(?![A-Za-z0-9_-])", combined) for tok in page_tokens_map[pid])
    ]
    if len(body_hits) == 1:
        return body_hits[0]

    # 3. Semantic Prototype Vocabulary & Visible DOM Text Scoring!
    #    Extract meaningful terms from `sub_title` (stripped of `F-xx` prefix) and `sub_md`
    clean_sub_t = re.sub(r"^(?:F-\d+(?:\.\d+)?|\d+(?:\.\d+)*)\s*[·.、:：-]?\s*", "", sub_title, flags=re.IGNORECASE).strip()
    title_terms = [t.strip() for t in re.split(r"[/、与及和\s·()（）-]+", clean_sub_t) if len(t.strip()) >= 2]
    bold_terms = [m.strip() for m in re.findall(r"\*\*([^*]{2,14})\*\*", sub_md) if m.strip() not in ("AC", "触发", "页面", "状态", "边界", "端差异")]

    best_pid: Optional[str] = None
    best_score = 0.0
    low_title = clean_sub_t.lower()
    low_md = sub_md.lower()

    for pid in page_order:
        phrases, dom_corpus = page_vocab_map[pid]
        score = 0.0

        # Check page's component/node phrases appearing in subsection title or body
        for ph in phrases:
            ph_low = ph.lower()
            if len(ph_low) < 2:
                continue
            if ph_low in low_title:
                score += 6.0
            elif ph_low in low_md:
                score += 2.2

        # Check subsection's title terms appearing in prototype page's visible HTML DOM!
        for tt in title_terms:
            tt_low = tt.lower()
            if len(tt_low) >= 2 and tt_low in dom_corpus:
                score += 5.0

        # Check bold field labels from subsection appearing in prototype page's visible HTML DOM
        for bt in bold_terms[:8]:
            bt_low = bt.lower()
            if len(bt_low) >= 2 and bt_low in dom_corpus:
                score += 1.8

        if score > best_score:
            best_score = score
            best_pid = pid

    # Require meaningful overlap (>= 4.0) so non-prototype items (e.g. `F-14 分享菜单布局` with no prototype screen)
    # don't get forced onto an unrelated screen and instead flow cleanly to Zone 3!
    return best_pid if best_score >= 4.0 else None


def _platform_badge(pdef: Dict[str, Any], pid: str, is_en: bool) -> str:
    plat = _infer_platform(pid, pdef)
    if plat == "app":
        return "Mobile App (375px)" if is_en else "App 端（375px）"
    if plat == "pc":
        return "Desktop Client" if is_en else "PC 客户端"
    if plat in ("web", "web-admin"):
        return "Web / Desktop" if is_en else "Web / PC 端"
    return str(pdef.get("title") or plat or "")


def build_document_model(
    project_dir: Path,
    prd_sections: List[Tuple[str, str]],
    spec_data: Optional[Dict[str, Any]],
    screenshots_dir: Path,
    format_inline_xhtml_fn: Any,
    md_block_to_xhtml_fn: Any,
) -> Dict[str, Any]:
    """Build the 3-Zone Document Model (`pre_sections`, `table_rows`, `post_sections`)."""
    is_en = bool(
        isinstance(spec_data, dict)
        and str((spec_data.get("meta") or {}).get("lang") or "").lower().startswith("en")
    )
    flow_shot = screenshots_dir / "flow-overview.png"
    has_flow_shot = flow_shot.is_file()

    pre_sections: List[Dict[str, Any]] = []
    post_sections: List[Dict[str, Any]] = []
    middle_h2_sections: List[Tuple[str, str]] = []
    flow_attached = False

    # 1. Partition top-level H2 chapters of prd.md into Pre-Table, Middle (Functional), and Post-Table!
    for sec_title, sec_md in prd_sections:
        if not sec_md.strip():
            continue
        if sec_title in ("文档概览", "Document Overview"):
            prose_lines = [
                ln for ln in sec_md.splitlines()
                if ln.strip()
                and ln.strip() != "---"
                and not re.match(r"^>\s*\*\*(?:文档版本|项目代号|Version|Project)\*\*", ln.strip())
            ]
            clean_lead = "\n".join(prose_lines).strip()
            if clean_lead:
                pre_sections.insert(
                    0,
                    {
                        "title": "",
                        "xhtml": md_block_to_xhtml_fn(clean_lead),
                        "docx_blocks": _extract_prd_plain_blocks(clean_lead),
                        "flow_shot": None,
                    },
                )
            continue

        # Skip multi-page Delta summary tables (`## 2. 本期目标与核心改点概览`) if they list >= 2 `p-xxx` page IDs
        # so we don't duplicate rules that appear in Zone 2's screen table!
        if len(set(re.findall(r"\bp-[a-z0-9_-]+\b", sec_md))) >= 2 and re.search(r"(改点概览|delta|summary)", sec_title, re.I):
            continue

        if POST_CHAPTER_RE.search(sec_title):
            post_sections.append(
                {
                    "title": _clean_display_heading(sec_title),
                    "xhtml": md_block_to_xhtml_fn(sec_md),
                    "docx_blocks": _extract_prd_plain_blocks(sec_md),
                }
            )
        elif PRE_CHAPTER_RE.search(sec_title):
            attach_flow_here = False
            if has_flow_shot and not flow_attached and FLOW_CHAPTER_RE.search(sec_title):
                attach_flow_here = True
                flow_attached = True
            # If this Pre-Table flow chapter merely lists raw `D_XXX` / `F_XXX` engineering IDs already shown on the
            # embedded flow.svg diagram & screen rows, keep prose clean and attach the visual flowchart!
            pre_sections.append(
                {
                    "title": _clean_display_heading(sec_title),
                    "xhtml": md_block_to_xhtml_fn(sec_md),
                    "docx_blocks": _extract_prd_plain_blocks(sec_md),
                    "flow_shot": flow_shot if attach_flow_here else None,
                }
            )
        else:
            middle_h2_sections.append((sec_title, sec_md))

    # If `flow-overview.png` exists and `prd.md` didn't have a dedicated `主流程` H2 chapter, add a crisp flow block at end of Zone 1!
    if has_flow_shot and not flow_attached:
        flow_sec_title = "End-to-End Flow Topology" if is_en else "端到端主流程拓扑"
        pre_sections.append(
            {
                "title": flow_sec_title,
                "xhtml": "",
                "docx_blocks": [],
                "flow_shot": flow_shot,
            }
        )

    # 2. Build Zone 2: Prototype-Backed Screen Rows (`序号 | 页面 | 需求说明`)
    table_rows: List[Dict[str, Any]] = []
    if isinstance(spec_data, dict) and isinstance(spec_data.get("nodes"), dict):
        nodes: Dict[str, Any] = spec_data["nodes"]
        pages: Dict[str, Any] = spec_data.get("pages") or {}
        vars_list: List[Any] = spec_data.get("vars") or []
        spec_cards: List[Any] = spec_data.get("spec_cards") or []

        _, variants_by_base, _ = _collect_expected_pages(spec_data)
        vars_by_id = {v["id"]: v for v in vars_list if isinstance(v, dict) and v.get("id")}

        page_groups: Dict[str, Dict[str, Any]] = {}
        page_order: List[str] = []
        for nid, ndef in nodes.items():
            if not isinstance(ndef, dict):
                continue
            raw_pid = str(ndef.get("page") or nid)
            p_obj = pages.get(raw_pid) if isinstance(pages.get(raw_pid), dict) else {}
            pid = str(p_obj.get("variant_of") or raw_pid)
            if pid not in page_groups:
                page_groups[pid] = {"nodes": [], "changes": set()}
                page_order.append(pid)
            page_groups[pid]["nodes"].append((nid, ndef))
            page_groups[pid]["changes"].add(str(ndef.get("change") or "unchanged"))

        # Prepare per-page token sets & DOM vocabulary for 2.A subsection aggregation!
        page_tokens_map: Dict[str, set] = {}
        page_explicit_refs: Dict[str, set] = {}
        page_vocab_map: Dict[str, Tuple[List[str], str]] = {}
        for pid in page_order:
            vpids = variants_by_base.get(pid, [])
            gnodes = page_groups[pid]["nodes"]
            page_tokens_map[pid] = {pid} | set(vpids) | {nid for nid, _ in gnodes}
            pdef = pages.get(pid) if isinstance(pages.get(pid), dict) else {}
            exp_refs = pdef.get("prd_sections") or []
            page_explicit_refs[pid] = {str(r).strip().upper() for r in exp_refs if r}
            page_vocab_map[pid] = _build_page_vocabulary(project_dir, pid, vpids, pages, gnodes, spec_cards)

        # Split all middle functional chapters into H3/H4 subsections and route each to its best screen (or Zone 3 if non-UI)
        subs_by_page: Dict[str, List[Tuple[str, str]]] = {pid: [] for pid in page_order}
        unmapped_func_subs: List[Tuple[str, str]] = []

        for h2_t, h2_md in middle_h2_sections:
            for sub_t, sub_md in _split_h3_subsections(h2_t, h2_md):
                if not sub_md.strip():
                    continue
                target_pid = _match_subsection_to_page(
                    sub_t,
                    sub_md,
                    page_order,
                    page_tokens_map,
                    page_explicit_refs,
                    page_vocab_map,
                )
                if target_pid is not None:
                    subs_by_page[target_pid].append((sub_t, sub_md))
                else:
                    unmapped_func_subs.append((sub_t, sub_md))

        if unmapped_func_subs:
            sup_title = "Additional Functional Rules" if is_en else "其他功能与补充约定"
            sup_md = "\n\n".join(f"### {t}\n\n{m}" for t, m in unmapped_func_subs)
            post_sections.insert(
                0,
                {
                    "title": sup_title,
                    "xhtml": md_block_to_xhtml_fn(sup_md),
                    "docx_blocks": _extract_prd_plain_blocks(sup_md),
                },
            )

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

            variant_pids = variants_by_base.get(pid, [])
            labeled_shots: List[Tuple[str, Path]] = []
            main_shot = screenshots_dir / f"{pid}.png"
            if main_shot.is_file():
                lbl = _platform_badge(pdef, pid, is_en) if variant_pids else ""
                labeled_shots.append((lbl, main_shot))
            for vpid in variant_pids:
                vshot = screenshots_dir / f"{vpid}.png"
                if vshot.is_file():
                    vpdef = pages.get(vpid) if isinstance(pages.get(vpid), dict) else {}
                    labeled_shots.append((_platform_badge(vpdef, vpid, is_en), vshot))

            all_shots = [sp for _, sp in labeled_shots]
            matched_subs = subs_by_page.get(pid, [])

            # Format matched subsections: if multiple `F-xx` subsections belong to this screen, preserve their clean H4 titles!
            formatted_sub_mds: List[str] = []
            norm_heading = _normalize_dedup_key(raw_title)
            for sub_t, sub_md in matched_subs:
                clean_st = _clean_display_heading(sub_t)
                stripped_num_st = re.sub(r"^\d+(?:\.\d+)*\s*", "", clean_st).strip()
                if len(matched_subs) >= 2 or (
                    _normalize_dedup_key(stripped_num_st) != norm_heading
                    and _normalize_dedup_key(stripped_num_st) not in norm_heading
                    and norm_heading not in _normalize_dedup_key(stripped_num_st)
                ):
                    formatted_sub_mds.append(f"#### {clean_st}\n{sub_md}")
                else:
                    formatted_sub_mds.append(sub_md)

            prd_combined_md = "\n\n".join(formatted_sub_mds)
            prd_norm_corpus = re.sub(r"[`*_#\s·•:：,，.。;；()（）\[\]【】/-]+", "", prd_combined_md.lower())

            # Single Source of Truth Merging: only include `node.anno` items if NOT already covered by matched `F-xx` subsections!
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
                            v_norm = _normalize_dedup_key(v_txt)[:16]
                            if k_norm in seen_keys:
                                continue
                            if prd_norm_corpus and (
                                (len(k_norm) >= 3 and k_norm in prd_norm_corpus)
                                or (len(v_norm) >= 7 and v_norm in prd_norm_corpus)
                            ):
                                continue
                            seen_keys.add(k_norm)
                            lead_xhtml.append(f"<p>&#183; <strong>{_xe(k_txt)}</strong>：{_xe(v_txt)}</p>")
                            lead_docx_blocks.append({"kind": "text", "text": f"· {k_txt}：{v_txt}", "bold": False})

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

            # Smart continuation split (`N` + `N-续`) when a dense config page aggregates >= 4 `F-xx` subsections!
            if len(formatted_sub_mds) >= 4:
                mid = (len(formatted_sub_mds) + 1) // 2
                part1_mds = formatted_sub_mds[:mid]
                part2_mds = formatted_sub_mds[mid:]

                p1_blocks = lead_docx_blocks + [b for ch in part1_mds for b in _extract_prd_plain_blocks(ch)]
                p2_blocks = [b for ch in part2_mds for b in _extract_prd_plain_blocks(ch)]
                p1_xhtml = "\n".join([f"<p><strong>{_xe(heading)}</strong></p>"] + lead_xhtml + [md_block_to_xhtml_fn(c) for c in part1_mds])

                primary_labeled = labeled_shots[:1] if len(labeled_shots) >= 2 else labeled_shots
                cont_labeled = labeled_shots[1:] if len(labeled_shots) >= 2 else labeled_shots[:1]

                table_rows.append(
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
                p2_xhtml = "\n".join([f"<p><strong>{_xe(cont_heading)}</strong></p>"] + [md_block_to_xhtml_fn(c) for c in part2_mds])
                table_rows.append(
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
                prd_xhtml_list = [md_block_to_xhtml_fn(ch) for ch in formatted_sub_mds if ch.strip()]
                prd_docx_blocks = [b for ch in formatted_sub_mds for b in _extract_prd_plain_blocks(ch)]
                full_xhtml = "\n".join([f"<p><strong>{_xe(heading)}</strong></p>"] + lead_xhtml + prd_xhtml_list)
                table_rows.append(
                    {
                        "display_idx": str(seq_num),
                        "context_tag": f"#{seq_num} · {heading}",
                        "label_id": pid,
                        "subtitle": heading,
                        "screenshot": all_shots[0] if all_shots else None,
                        "screenshots": all_shots,
                        "labeled_shots": labeled_shots,
                        "heading": heading,
                        "docx_blocks": lead_docx_blocks + prd_docx_blocks,
                        "right_xhtml_html": full_xhtml,
                        "right_xhtml": full_xhtml,
                    }
                )
    else:
        # Fallback when no spec.json exists: render remaining middle sections in post_sections
        for sec_t, sec_m in middle_h2_sections:
            post_sections.append(
                {
                    "title": _clean_display_heading(sec_t),
                    "xhtml": md_block_to_xhtml_fn(sec_m),
                    "docx_blocks": _extract_prd_plain_blocks(sec_m),
                }
            )

    return {
        "is_en": is_en,
        "pre_sections": pre_sections,
        "table_rows": table_rows,
        "post_sections": post_sections,
    }


def render_fig2_html(
    title: str,
    version_str: str,
    zip_filename: str,
    doc_model: Dict[str, Any],
    is_en: bool = False,
) -> str:
    """Render Three-Zone HTML: Zone 1 Full-Width Intro + Zone 2 Prototype Table + Zone 3 Full-Width Appendix."""
    pre_sections: List[Dict[str, Any]] = doc_model.get("pre_sections") or []
    rows: List[Dict[str, Any]] = doc_model.get("table_rows") or []
    post_sections: List[Dict[str, Any]] = doc_model.get("post_sections") or []

    pre_html_parts: List[str] = []
    for psec in pre_sections:
        stitle = str(psec.get("title") or "").strip()
        sxhtml = str(psec.get("xhtml") or "").strip()
        fshot: Optional[Path] = psec.get("flow_shot")
        flow_img_html = ""
        if fshot and fshot.is_file():
            fb64 = base64.b64encode(fshot.read_bytes()).decode("ascii")
            cap = "End-to-End Flow Topology (Top-Down)" if is_en else "全局业务主流程拓扑图"
            zoom_tip = "Click to zoom" if is_en else "点击放大查看高清流程图"
            flow_img_html = (
                f'<div class="flow-overview-box">'
                f'<div class="flow-overview-cap">{cap}</div>'
                f'<img class="flow-overview-img zoomable-shot" data-caption="{_xe(cap)}" title="{zoom_tip}" '
                f'src="data:image/png;base64,{fb64}" alt="{cap}" />'
                f"</div>"
            )
        hd_tag = f'<h2 class="zone-sec-hd">{_xe(stitle)}</h2>' if stitle else ""
        pre_html_parts.append(f'<section class="zone-block">{hd_tag}{sxhtml}{flow_img_html}</section>')

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
            zoom_tip = "Click to zoom high-res prototype" if is_en else "点击放大查看高清原型图"
            for lbl, sp in valid_labeled:
                b64 = base64.b64encode(sp.read_bytes()).decode("ascii")
                cap = f'<div class="plat-cap">{_xe(lbl)}</div>' if lbl else ""
                full_cap = f"{ctx_tag} · {lbl}" if lbl else ctx_tag
                blocks.append(
                    f'<div class="shot-card">{cap}'
                    f'<img class="wf-shot zoomable-shot" data-caption="{_xe(full_cap)}" title="{zoom_tip}" '
                    f'src="data:image/png;base64,{b64}" alt="{_xe(row["subtitle"])}" /></div>'
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

    post_html_parts: List[str] = []
    for asec in post_sections:
        stitle = str(asec.get("title") or "").strip()
        sxhtml = str(asec.get("xhtml") or "").strip()
        hd_tag = f'<h2 class="zone-sec-hd">{_xe(stitle)}</h2>' if stitle else ""
        post_html_parts.append(f'<section class="zone-block">{hd_tag}{sxhtml}</section>')

    sec_hd = "Product Specification (Screen-by-Screen)" if is_en else "产品方案（页面与交互对照）"
    proto_lbl = "Interactive Prototype: " if is_en else "交互原型："
    dl_txt = "(Click to Download)" if is_en else "（点击下载）"
    copy_btn = (
        "Copy Full Document (Paste into WeCom / Feishu Doc)"
        if is_en
        else "一键复制整篇图文方案（可直接粘贴至企微在线文档 / 飞书）"
    )
    copied_txt = (
        "Copied! Paste directly into WeCom / Feishu Doc"
        if is_en
        else "已复制整篇图文方案！请直接 Cmd/Ctrl+V 粘贴到企业微信文档"
    )
    th_1 = "No." if is_en else "序号"
    th_2 = "Screen" if is_en else "页面"
    th_3 = "Specification" if is_en else "需求说明"

    pre_zone_html = f'<div class="zone-pre">{"".join(pre_html_parts)}</div>' if pre_html_parts else ""
    post_zone_html = f'<div class="zone-post">{"".join(post_html_parts)}</div>' if post_html_parts else ""

    return f"""<!DOCTYPE html>
<html lang="{'en' if is_en else 'zh-CN'}">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>{_xe(title)}</title>
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
    padding: 10px 14px; margin-bottom: 20px; background: #f5f5f5; border: 1px solid #d9d9d9; border-radius: 6px;
  }}
  .doc-toolbar button {{
    background: #262626; color: #ffffff; border: none; border-radius: 5px;
    padding: 7px 14px; font-size: 13px; font-weight: 600; cursor: pointer;
  }}
  .doc-toolbar button:hover {{ background: #111111; }}
  h1.doc-main-title {{ margin: 0 0 16px; font-size: 24px; font-weight: 800; color: #141414; padding-bottom: 12px; border-bottom: 1px solid #e5e5e5; }}
  .zone-pre {{ margin-bottom: 26px; }}
  .zone-post {{ margin-top: 28px; padding-top: 8px; border-top: 1px solid #e5e5e5; }}
  .zone-block {{ margin-bottom: 20px; }}
  h2.zone-sec-hd, h2.scheme-hd {{
    margin: 18px 0 10px; font-size: 18px; font-weight: 700; color: #141414;
    padding-left: 10px; border-left: 3px solid #262626; line-height: 1.35;
  }}
  .flow-overview-box {{
    margin: 12px 0 6px; padding: 14px; background: #fafafa; border: 1px solid #d9d9d9; border-radius: 6px; text-align: center;
  }}
  .flow-overview-cap {{
    font-size: 12px; font-weight: 700; color: #595959; margin-bottom: 10px; text-align: left;
  }}
  .flow-overview-img {{
    display: inline-block; max-width: 780px; width: 100%; height: auto; border: 1px solid #e0e0e0; border-radius: 4px; background: #ffffff; filter: grayscale(100%);
    cursor: zoom-in; transition: border-color 0.15s ease, box-shadow 0.15s ease;
  }}
  .flow-overview-img:hover {{ border-color: #595959; box-shadow: 0 2px 10px rgba(0,0,0,0.08); }}
  .proto-link-line {{ margin: 0 0 14px; font-size: 13.5px; color: #333333; }}
  a, .proto-link-line a {{ color: #0052cc; font-weight: 500; text-decoration: none; }}
  a:hover, .proto-link-line a:hover {{ text-decoration: underline; }}
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
  .shot-card {{ margin-bottom: 12px; position: relative; }}
  .shot-card:last-child {{ margin-bottom: 0; }}
  .plat-cap {{
    font-size: 11px; font-weight: 600; color: #595959; margin-bottom: 4px;
    font-family: ui-monospace, monospace;
  }}
  .col-spec {{ width: auto; word-break: break-word; background: #ffffff; }}
  .wf-shot {{
    display: block; max-width: 100%; height: auto; border: 1px solid #d4d4d4;
    border-radius: 4px; filter: grayscale(100%); cursor: zoom-in;
    transition: border-color 0.15s ease, box-shadow 0.15s ease;
  }}
  .wf-shot:hover {{ border-color: #404040; box-shadow: 0 3px 12px rgba(0,0,0,0.10); }}
  /* Full-screen High-Res Prototype Lightbox (outside #copy-target so clipboard stays clean) */
  .lb-mask {{
    display: none; position: fixed; inset: 0; z-index: 99999;
    background: rgba(18, 18, 20, 0.88); backdrop-filter: blur(3px);
    flex-direction: column; user-select: none;
  }}
  .lb-mask.open {{ display: flex; }}
  .lb-topbar {{
    display: flex; align-items: center; justify-content: space-between; gap: 12px;
    padding: 10px 18px; background: rgba(24, 24, 27, 0.96); border-bottom: 1px solid #333;
    color: #f4f4f5; font-size: 13px; flex-shrink: 0;
  }}
  .lb-caption {{ font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
  .lb-controls {{ display: flex; align-items: center; gap: 6px; flex-shrink: 0; }}
  .lb-btn {{
    background: #27272a; color: #f4f4f5; border: 1px solid #3f3f46; border-radius: 5px;
    padding: 4px 10px; font-size: 12.5px; font-weight: 600; cursor: pointer;
  }}
  .lb-btn:hover {{ background: #3f3f46; }}
  .lb-zoom-lbl {{ min-width: 48px; text-align: center; font-family: ui-monospace, monospace; font-size: 12px; color: #d4d4d8; }}
  .lb-stage {{
    flex: 1; overflow: auto; display: flex; align-items: flex-start; justify-content: center;
    padding: 28px; cursor: zoom-out;
  }}
  .lb-img {{
    display: block; max-width: none; height: auto; background: #ffffff;
    border-radius: 6px; box-shadow: 0 12px 42px rgba(0,0,0,0.55);
    filter: grayscale(100%); cursor: default; transform-origin: top center;
  }}
  .wf-global-tag {{
    padding: 10px 12px; background: #f2f2f2; border: 1px solid #d4d4d4; border-radius: 4px;
    font-weight: 600; color: #404040; font-size: 13px; text-align: center;
  }}
  table.nested-table {{ width: 100%; border-collapse: collapse; margin: 10px 0 8px; font-size: 13px; }}
  table.nested-table th, table.nested-table td {{
    border: 1px solid #d9d9d9; padding: 7px 10px; vertical-align: top; text-align: left;
  }}
  table.nested-table th {{ background: #f5f5f5; font-weight: 700; color: #1f1f1f; }}
  p {{ margin: 0 0 6px; }}
  ul {{ margin: 0 0 8px; padding-left: 18px; }}
  li {{ margin-bottom: 4px; }}
  h3, h4, h5 {{ margin: 12px 0 6px; font-size: 14px; font-weight: 700; color: #141414; }}
  code {{ font-family: ui-monospace, monospace; font-size: 12px; background: #f2f2f2; padding: 1px 4px; border-radius: 3px; color: #262626; }}
  blockquote {{ margin: 8px 0; padding: 6px 12px; border-left: 3px solid #8c8c8c; background: #f7f7f7; color: #404040; }}
  @media print {{
    .doc-toolbar, .lb-mask {{ display: none !important; }}
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
    <h1 class="doc-main-title">{_xe(title)}</h1>
    {pre_zone_html}
    <h2 class="scheme-hd">{sec_hd}</h2>
    <p class="proto-link-line">{proto_lbl}{_xe(zip_filename)} （<a href="{_xe(zip_filename)}">{'Click to Download' if is_en else '点击下载'}</a>）</p>
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
    {post_zone_html}
  </div>
</div>

<div class="lb-mask" id="img-lightbox" aria-hidden="true">
  <div class="lb-topbar">
    <div class="lb-caption" id="lb-caption"></div>
    <div class="lb-controls">
      <button type="button" class="lb-btn" onclick="lbStep(-1)">{'← Prev' if is_en else '← 上一张'}</button>
      <button type="button" class="lb-btn" onclick="lbStep(1)">{'Next →' if is_en else '下一张 →'}</button>
      <button type="button" class="lb-btn" onclick="lbZoomBy(-0.2)">&#65293;</button>
      <span class="lb-zoom-lbl" id="lb-zoom-lbl">100%</span>
      <button type="button" class="lb-btn" onclick="lbZoomBy(0.2)">&#65291;</button>
      <button type="button" class="lb-btn" onclick="lbFit()">{'Fit' if is_en else '适屏'}</button>
      <button type="button" class="lb-btn" onclick="lbClose()">{'Close (Esc)' if is_en else '关闭 (Esc)'}</button>
    </div>
  </div>
  <div class="lb-stage" id="lb-stage" onclick="if(event.target===this)lbClose()">
    <img class="lb-img" id="lb-img" alt="" />
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

(function() {{
  var shots = Array.prototype.slice.call(document.querySelectorAll('img.zoomable-shot'));
  var mask = document.getElementById('img-lightbox');
  var lbImg = document.getElementById('lb-img');
  var lbCap = document.getElementById('lb-caption');
  var lbZoomLbl = document.getElementById('lb-zoom-lbl');
  var lbStage = document.getElementById('lb-stage');
  var curIdx = 0;
  var baseWidth = 800;
  var zoom = 1;

  function applyZoom() {{
    lbImg.style.width = Math.round(baseWidth * zoom) + 'px';
    lbZoomLbl.textContent = Math.round(zoom * 100) + '%';
  }}

  window.lbFit = function() {{
    var natW = (lbImg.naturalWidth || 1200) / {SCREENSHOT_DPR};
    var natH = (lbImg.naturalHeight || 900) / {SCREENSHOT_DPR};
    var availW = Math.max(320, lbStage.clientWidth - 64);
    var availH = Math.max(240, lbStage.clientHeight - 56);
    baseWidth = natW;
    zoom = Math.min(1.35, availW / natW, (availH / natH) * 1.15);
    if (zoom < 0.4) zoom = 0.4;
    applyZoom();
  }};

  window.lbZoomBy = function(delta) {{
    zoom = Math.max(0.35, Math.min(3.5, zoom + delta));
    applyZoom();
  }};

  function openAt(idx) {{
    if (!shots.length) return;
    curIdx = (idx + shots.length) % shots.length;
    var target = shots[curIdx];
    lbImg.onload = function() {{ window.lbFit(); }};
    lbImg.src = target.src;
    var cap = target.getAttribute('data-caption') || target.alt || '';
    lbCap.textContent = '[' + (curIdx + 1) + '/' + shots.length + '] ' + cap;
    mask.classList.add('open');
    mask.setAttribute('aria-hidden', 'false');
    document.body.style.overflow = 'hidden';
    if (lbImg.complete && lbImg.naturalWidth) window.lbFit();
  }}

  window.lbStep = function(dir) {{ openAt(curIdx + dir); }};

  window.lbClose = function() {{
    mask.classList.remove('open');
    mask.setAttribute('aria-hidden', 'true');
    document.body.style.overflow = '';
  }};

  shots.forEach(function(el, i) {{
    el.addEventListener('click', function() {{ openAt(i); }});
  }});

  lbStage.addEventListener('wheel', function(e) {{
    if (!mask.classList.contains('open')) return;
    e.preventDefault();
    window.lbZoomBy(e.deltaY < 0 ? 0.12 : -0.12);
  }}, {{ passive: false }});

  document.addEventListener('keydown', function(e) {{
    if (!mask.classList.contains('open')) return;
    if (e.key === 'Escape') window.lbClose();
    else if (e.key === 'ArrowLeft') window.lbStep(-1);
    else if (e.key === 'ArrowRight') window.lbStep(1);
    else if (e.key === '+' || e.key === '=') window.lbZoomBy(0.2);
    else if (e.key === '-') window.lbZoomBy(-0.2);
  }});
}})();
</script>
</body>
</html>
"""


def render_fig2_confluence_xml(
    title: str,
    version_str: str,
    zip_filename: str,
    doc_model: Dict[str, Any],
    is_en: bool = False,
) -> str:
    """Render Three-Zone Confluence 7.4+ Storage XML (Zone 1 Intro + Zone 2 Screen Table + Zone 3 Appendix)."""
    pre_sections: List[Dict[str, Any]] = doc_model.get("pre_sections") or []
    rows: List[Dict[str, Any]] = doc_model.get("table_rows") or []
    post_sections: List[Dict[str, Any]] = doc_model.get("post_sections") or []

    pre_xml_parts: List[str] = []
    for psec in pre_sections:
        stitle = str(psec.get("title") or "").strip()
        sxhtml = str(psec.get("xhtml") or "").strip()
        fshot: Optional[Path] = psec.get("flow_shot")
        if stitle:
            pre_xml_parts.append(f"<h2>{_xe(stitle)}</h2>")
        if sxhtml:
            pre_xml_parts.append(sxhtml)
        if fshot and fshot.is_file():
            pre_xml_parts.append(
                f'<p><ac:image ac:width="720"><ri:attachment ri:filename="{_xe(fshot.name)}" /></ac:image></p>'
            )

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

    post_xml_parts: List[str] = []
    for asec in post_sections:
        stitle = str(asec.get("title") or "").strip()
        sxhtml = str(asec.get("xhtml") or "").strip()
        if stitle:
            post_xml_parts.append(f"<h2>{_xe(stitle)}</h2>")
        if sxhtml:
            post_xml_parts.append(sxhtml)

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
        f"{''.join(pre_xml_parts)}"
        f"<h2>{sec_hd}</h2>"
        f"<p>{proto_lbl}{_xe(zip_filename)} （"
        f'<ac:link><ri:attachment ri:filename="{_xe(zip_filename)}" />'
        f"<ac:plain-text-link-body><![CDATA[{'Click to Download' if is_en else '点击下载'}]]></ac:plain-text-link-body>"
        "</ac:link>）</p>"
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
        f"{''.join(post_xml_parts)}"
        "</div>"
    )
    ET.fromstring(xml_doc.encode("utf-8"))
    return xml_doc


def write_fig2_docx(
    docx_path: Path,
    title: str,
    version_str: str,
    zip_filename: str,
    doc_model: Dict[str, Any],
    is_en: bool = False,
) -> Path:
    """Write Three-Zone pure-grayscale OOXML `.docx` (Zone 1 Intro + Zone 2 Screen Table + Zone 3 Appendix)."""
    pre_sections: List[Dict[str, Any]] = doc_model.get("pre_sections") or []
    rows: List[Dict[str, Any]] = doc_model.get("table_rows") or []
    post_sections: List[Dict[str, Any]] = doc_model.get("post_sections") or []

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

    def _w_p_text(txt: str, bold: bool = False, size_half_pt: int = 20, color: str = "1F1F1F", space_before: int = 36) -> str:
        b_xml = "<w:b/><w:bCs/>" if bold else ""
        return (
            f"<w:p><w:pPr><w:spacing w:before=\"{space_before}\" w:after=\"56\"/></w:pPr>"
            f"<w:r><w:rPr>{b_xml}<w:color w:val=\"{color}\"/>"
            f"<w:sz w:val=\"{size_half_pt}\"/><w:szCs w:val=\"{size_half_pt}\"/></w:rPr>"
            f"<w:t xml:space=\"preserve\">{_xe(txt)}</w:t></w:r></w:p>"
        )

    def _w_p_img(p: Path, max_w_px: int, doc_pr_id: int) -> str:
        rid, cx, cy = _register_img(p, max_w_px=max_w_px)
        return (
            "<w:p><w:pPr><w:spacing w:before=\"48\" w:after=\"80\"/></w:pPr><w:r><w:drawing>"
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

    def _render_blocks_xml(blocks: List[Dict[str, Any]], total_tbl_w_dxa: int, inside_tc: bool = False) -> List[str]:
        parts: List[str] = []
        for blk in blocks:
            if blk.get("kind") == "table":
                hdrs: List[str] = blk.get("headers") or []
                d_rows: List[List[str]] = blk.get("rows") or []
                col_n = max(1, len(hdrs))
                col_w = int(total_tbl_w_dxa // col_n)
                grid_xml = "".join(f'<w:gridCol w:w="{col_w}"/>' for _ in range(col_n))
                th_cells = "".join(
                    f'<w:tc><w:tcPr><w:tcW w:w="{col_w}" w:type="dxa"/><w:shd w:val="clear" w:fill="F5F5F5"/></w:tcPr>{_w_p_text(h, bold=True, size_half_pt=18)}</w:tc>'
                    for h in hdrs
                )
                d_trs = [f"<w:tr><w:trPr><w:tblHeader/><w:cantSplit/></w:trPr>{th_cells}</w:tr>"]
                for dr in d_rows:
                    td_cells = "".join(
                        f'<w:tc><w:tcPr><w:tcW w:w="{col_w}" w:type="dxa"/></w:tcPr>{_w_p_text(c, bold=False, size_half_pt=18)}</w:tc>'
                        for c in dr
                    )
                    d_trs.append(f"<w:tr><w:trPr><w:cantSplit/></w:trPr>{td_cells}</w:tr>")
                trail = "<w:p/>" if inside_tc else ""
                parts.append(
                    "<w:tbl>"
                    f"<w:tblPr><w:tblW w:w=\"{col_w * col_n}\" w:type=\"dxa\"/>{tbl_borders}{cell_mar}</w:tblPr>"
                    f"<w:tblGrid>{grid_xml}</w:tblGrid>"
                    f"{''.join(d_trs)}"
                    f"</w:tbl>{trail}"
                )
            else:
                is_b = bool(blk.get("bold"))
                parts.append(
                    _w_p_text(
                        str(blk.get("text") or ""),
                        bold=is_b,
                        size_half_pt=20 if is_b else 19,
                        space_before=100 if is_b else 36,
                    )
                )
        return parts

    doc_pr_seq = 1
    body_xml_parts: List[str] = [_w_p_text(title, bold=True, size_half_pt=30, space_before=0)]

    # Zone 1: Full-Width Pre-Table Global Intro + Global Flowchart
    for psec in pre_sections:
        stitle = str(psec.get("title") or "").strip()
        if stitle:
            body_xml_parts.append(_w_p_text(stitle, bold=True, size_half_pt=24, space_before=160))
        body_xml_parts.extend(_render_blocks_xml(psec.get("docx_blocks") or [], total_tbl_w_dxa=15398, inside_tc=False))
        fshot: Optional[Path] = psec.get("flow_shot")
        if fshot and fshot.is_file():
            doc_pr_seq += 1
            body_xml_parts.append(_w_p_img(fshot, max_w_px=680, doc_pr_id=doc_pr_seq))

    # Zone 2: Prototype-Backed Screen Table (`序号 | 页面 | 需求说明`)
    sec_hd = "Product Specification" if is_en else "产品方案（页面与交互对照）"
    dl_word = "Click to Download" if is_en else "点击下载"
    proto_prefix = f"Interactive Prototype: {zip_filename} (" if is_en else f"交互原型：{zip_filename}（"
    proto_suffix = f" · {version_str})" if is_en else f" · 版本 {version_str}）"
    body_xml_parts.append(_w_p_text(sec_hd, bold=True, size_half_pt=24, space_before=180))
    body_xml_parts.append(
        "<w:p><w:pPr><w:spacing w:before=\"36\" w:after=\"64\"/></w:pPr>"
        f"<w:r><w:rPr><w:color w:val=\"333333\"/><w:sz w:val=\"19\"/><w:szCs w:val=\"19\"/></w:rPr><w:t xml:space=\"preserve\">{_xe(proto_prefix)}</w:t></w:r>"
        f"<w:r><w:rPr><w:color w:val=\"0052CC\"/><w:u w:val=\"single\"/><w:sz w:val=\"19\"/><w:szCs w:val=\"19\"/></w:rPr><w:t>{_xe(dl_word)}</w:t></w:r>"
        f"<w:r><w:rPr><w:color w:val=\"595959\"/><w:sz w:val=\"19\"/><w:szCs w:val=\"19\"/></w:rPr><w:t xml:space=\"preserve\">{_xe(proto_suffix)}</w:t></w:r>"
        "</w:p>"
    )

    th_1 = "No." if is_en else "序号"
    th_2 = "Screen" if is_en else "页面"
    th_3 = "Specification" if is_en else "需求说明"

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
        right_ps.extend(_render_blocks_xml(row.get("docx_blocks") or [], total_tbl_w_dxa=9300, inside_tc=True))

        tr_xml_list.append(
            "<w:tr>"
            f"<w:tc><w:tcPr><w:tcW w:w=\"900\" w:type=\"dxa\"/></w:tcPr>{_w_p_text(disp_idx, bold=True)}</w:tc>"
            f"<w:tc><w:tcPr><w:tcW w:w=\"4800\" w:type=\"dxa\"/><w:shd w:val=\"clear\" w:fill=\"FAFAFA\"/></w:tcPr>{left_cell_xml}</w:tc>"
            f"<w:tc><w:tcPr><w:tcW w:w=\"9698\" w:type=\"dxa\"/></w:tcPr>{''.join(right_ps)}</w:tc>"
            "</w:tr>"
        )

    body_xml_parts.append(
        "<w:tbl>"
        f"<w:tblPr><w:tblW w:w=\"15398\" w:type=\"dxa\"/>{tbl_borders}{cell_mar}</w:tblPr>"
        "<w:tblGrid><w:gridCol w:w=\"900\"/><w:gridCol w:w=\"4800\"/><w:gridCol w:w=\"9698\"/></w:tblGrid>"
        f"{''.join(tr_xml_list)}"
        "</w:tbl>"
    )

    # Zone 3: Full-Width Post-Table Global Engineering & Acceptance Appendix
    for asec in post_sections:
        stitle = str(asec.get("title") or "").strip()
        if stitle:
            body_xml_parts.append(_w_p_text(stitle, bold=True, size_half_pt=24, space_before=180))
        body_xml_parts.extend(_render_blocks_xml(asec.get("docx_blocks") or [], total_tbl_w_dxa=15398, inside_tc=False))

    document_xml = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<w:document xmlns:w=\"http://schemas.openxmlformats.org/wordprocessingml/2006/main\" "
        "xmlns:r=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships\" "
        "xmlns:wp=\"http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing\">"
        "<w:body>"
        f"{''.join(body_xml_parts)}"
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
