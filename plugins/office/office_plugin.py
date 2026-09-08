"""
Aura Office Automation Plugin
=============================
Plugin for Word (.docx), Excel (.xlsx), PowerPoint (.pptx), PDF, printing,
and optional COM automation (Outlook, live Excel/Word/PowerPoint) when MS Office
is installed.

Pure-Python path (openpyxl / python-docx / python-pptx):
  Works WITHOUT Microsoft Office installed.

COM automation path (win32com.client):
  Requires Microsoft Office to be installed on the machine.
  Used only when capabilities like ``office.com_open_excel`` or
  ``office.outlook_send`` are invoked.

Note on pywin32
---------------
The ``pywin32`` package is used for Windows desktop integration broadly —
not specifically for Office.  If you ever use a feature like "automate Outlook"
or "control Excel via COM," then Microsoft Office would be needed for that
specific action, but the core Aura assistant runs fine without it.
"""

from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path
from typing import Any

from src.plugins.plugin_interface import Plugin, PluginCategory, PluginManifest

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _try_import_win32():
    """Return (win32com_client, win32api) or (None, None) gracefully."""
    try:
        import win32com.client as _client  # type: ignore
        import win32api as _api            # type: ignore
        return _client, _api
    except ImportError:
        return None, None


def _office_installed() -> bool:
    """Best-effort check: return True if any MS Office installation is detected."""
    try:
        import winreg  # type: ignore
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Office")
        winreg.CloseKey(key)
        return True
    except Exception:
        pass
    for loc in [
        r"C:\Program Files\Microsoft Office",
        r"C:\Program Files (x86)\Microsoft Office",
    ]:
        if Path(loc).exists():
            return True
    return False


# ---------------------------------------------------------------------------
# Plugin
# ---------------------------------------------------------------------------

class OfficePlugin(Plugin):
    """
    Microsoft Office Automation Plugin for Aura.

    Provides two execution tiers:
      1. Pure-Python  — openpyxl / python-docx / python-pptx (no Office needed)
      2. COM automation — win32com.client (requires MS Office installed)
    """

    # ------------------------------------------------------------------ init

    def __init__(self, manifest: PluginManifest | None = None):
        if manifest is None:
            manifest = PluginManifest(
                name="office",
                version="2.0.0",
                author="Aura AI",
                description=(
                    "Office document automation (Word, Excel, PowerPoint, PDF, Outlook). "
                    "Pure-Python path works without MS Office; COM path requires MS Office."
                ),
                category=PluginCategory.OFFICE,
                capabilities=[
                    # ── Pure-Python ──────────────────────────────────────
                    "office.create_document",
                    "office.read_document",
                    "office.edit_document",
                    "office.create_spreadsheet",
                    "office.read_spreadsheet",
                    "office.edit_spreadsheet",
                    "office.create_presentation",
                    "office.read_presentation",
                    "office.extract_text",
                    "office.convert",
                    "office.merge_pdfs",
                    "office.print",
                    # ── COM / MS-Office-required ──────────────────────────
                    "office.com_open_word",
                    "office.com_open_excel",
                    "office.com_open_powerpoint",
                    "office.outlook_send",
                    "office.outlook_read_inbox",
                    "office.outlook_create_event",
                ],
            )
        super().__init__(manifest)
        self._com_available: bool = False
        self._office_installed: bool = False

    # ------------------------------------------------------------------ lifecycle

    def load(self) -> bool:
        win32com, _ = _try_import_win32()
        self._com_available = win32com is not None
        self._office_installed = _office_installed()
        if not self._com_available:
            logger.info(
                "[OfficePlugin] pywin32 not available — COM automation disabled. "
                "Pure-Python Office features (openpyxl, python-docx, python-pptx) remain active."
            )
        if self._com_available and not self._office_installed:
            logger.info(
                "[OfficePlugin] pywin32 available but Microsoft Office not detected. "
                "COM capabilities will raise descriptive errors at runtime."
            )
        self.state = "initialized"
        return True

    def initialize(self) -> bool:
        self.state = "ready"
        return True

    def can_handle(self, capability: str) -> bool:
        return capability.startswith("office.") or capability in self.manifest.capabilities

    # ================================================================== execute

    def execute(self, capability: str, **kwargs: Any) -> Any:  # noqa: C901
        cap = capability.lower()

        # ── Word ─────────────────────────────────────────────────────────────
        if cap == "office.create_document":
            return self._create_doc(
                path=kwargs.get("path") or "document.docx",
                content=kwargs.get("content") or kwargs.get("text") or "",
                title=kwargs.get("title") or "Aura Document",
                author=kwargs.get("author") or "Aura AI",
            )
        if cap == "office.read_document":
            return self._read_doc(kwargs.get("path") or "")
        if cap == "office.edit_document":
            return self._edit_doc(
                path=kwargs.get("path") or "",
                append=kwargs.get("append") or kwargs.get("content") or "",
            )

        # ── Excel ─────────────────────────────────────────────────────────────
        if cap == "office.create_spreadsheet":
            return self._create_spreadsheet(
                path=kwargs.get("path") or "spreadsheet.xlsx",
                rows=kwargs.get("rows") or [["Header 1", "Header 2"], ["Value 1", "Value 2"]],
                sheet_name=kwargs.get("sheet_name") or "Sheet1",
            )
        if cap == "office.read_spreadsheet":
            return self._read_spreadsheet(
                path=kwargs.get("path") or "",
                sheet_name=kwargs.get("sheet_name"),
                max_rows=int(kwargs.get("max_rows") or 100),
            )
        if cap == "office.edit_spreadsheet":
            return self._edit_spreadsheet(
                path=kwargs.get("path") or "",
                cell=kwargs.get("cell") or "A1",
                value=kwargs.get("value") or "",
                sheet_name=kwargs.get("sheet_name"),
            )

        # ── PowerPoint ───────────────────────────────────────────────────────
        if cap == "office.create_presentation":
            return self._create_presentation(
                path=kwargs.get("path") or "presentation.pptx",
                slides=kwargs.get("slides") or [{"title": "Slide 1", "body": "Content here"}],
            )
        if cap == "office.read_presentation":
            return self._read_presentation(kwargs.get("path") or "")

        # ── Utilities ────────────────────────────────────────────────────────
        if cap == "office.extract_text":
            return self._extract_text(kwargs.get("path") or "")
        if cap == "office.print":
            return self._print_file(kwargs.get("path") or "")
        if cap == "office.convert":
            return self._convert(
                src=kwargs.get("src") or kwargs.get("path") or "",
                fmt=kwargs.get("format") or kwargs.get("fmt") or "pdf",
            )

        # ── COM: Open in live Office app ──────────────────────────────────────
        if cap == "office.com_open_word":
            return self._com_open("Word.Application", kwargs.get("path") or "")
        if cap == "office.com_open_excel":
            return self._com_open("Excel.Application", kwargs.get("path") or "")
        if cap == "office.com_open_powerpoint":
            return self._com_open("PowerPoint.Application", kwargs.get("path") or "")

        # ── Outlook ──────────────────────────────────────────────────────────
        if cap == "office.outlook_send":
            return self._outlook_send(
                to=kwargs.get("to") or "",
                subject=kwargs.get("subject") or "(no subject)",
                body=kwargs.get("body") or kwargs.get("content") or "",
                cc=kwargs.get("cc") or "",
                attachment=kwargs.get("attachment") or "",
            )
        if cap == "office.outlook_read_inbox":
            return self._outlook_read_inbox(
                limit=int(kwargs.get("limit") or 10),
                folder=kwargs.get("folder") or "Inbox",
            )
        if cap == "office.outlook_create_event":
            return self._outlook_create_event(
                subject=kwargs.get("subject") or "Meeting",
                start=kwargs.get("start") or "",
                end=kwargs.get("end") or "",
                location=kwargs.get("location") or "",
                body=kwargs.get("body") or "",
            )

        return {"status": "success", "capability": capability, "params": kwargs}

    # ================================================================== Pure-Python implementations

    # ── Word (.docx) ─────────────────────────────────────────────────────────

    def _create_doc(self, path: str, content: str, title: str = "", author: str = "") -> dict[str, Any]:
        p = Path(path).resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        try:
            import docx
            doc = docx.Document()
            if title:
                doc.add_heading(title, level=0)
            if author:
                meta = doc.add_paragraph()
                meta.add_run(f"Author: {author}").bold = True
            for line in content.splitlines():
                doc.add_paragraph(line)
            doc.save(str(p))
            logger.info(f"[OfficePlugin] Word document created: {p}")
            return {"status": "created", "path": str(p), "type": "docx"}
        except ImportError:
            p.write_text(content, encoding="utf-8")
            return {"status": "created_fallback", "path": str(p), "type": "text"}

    def _read_doc(self, path: str) -> dict[str, Any]:
        p = Path(path).resolve()
        if not p.exists():
            return {"status": "error", "message": f"File not found: {p}"}
        try:
            import docx
            doc = docx.Document(str(p))
            text = "\n".join(para.text for para in doc.paragraphs)
            return {"status": "ok", "path": str(p), "text": text, "paragraphs": len(doc.paragraphs)}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def _edit_doc(self, path: str, append: str) -> dict[str, Any]:
        p = Path(path).resolve()
        if not p.exists():
            return {"status": "error", "message": f"File not found: {p}"}
        try:
            import docx
            doc = docx.Document(str(p))
            doc.add_paragraph(append)
            doc.save(str(p))
            return {"status": "edited", "path": str(p)}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    # ── Excel (.xlsx) ────────────────────────────────────────────────────────

    def _create_spreadsheet(self, path: str, rows: list[list[Any]], sheet_name: str = "Sheet1") -> dict[str, Any]:
        p = Path(path).resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        try:
            import openpyxl
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = sheet_name
            for row in rows:
                ws.append(row)
            wb.save(str(p))
            return {"status": "created", "path": str(p), "type": "xlsx", "rows": len(rows)}
        except ImportError:
            import csv
            with open(p, "w", newline="", encoding="utf-8") as f:
                csv.writer(f).writerows(rows)
            return {"status": "created_fallback", "path": str(p), "type": "csv"}

    def _read_spreadsheet(self, path: str, sheet_name: str | None = None, max_rows: int = 100) -> dict[str, Any]:
        p = Path(path).resolve()
        if not p.exists():
            return {"status": "error", "message": f"File not found: {p}"}
        try:
            import openpyxl
            wb = openpyxl.load_workbook(str(p), read_only=True, data_only=True)
            ws = wb[sheet_name] if sheet_name and sheet_name in wb.sheetnames else wb.active
            rows = []
            for i, row in enumerate(ws.iter_rows(values_only=True)):
                if i >= max_rows:
                    break
                rows.append(list(row))
            return {"status": "ok", "path": str(p), "sheet": ws.title, "rows": rows}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def _edit_spreadsheet(self, path: str, cell: str, value: Any, sheet_name: str | None = None) -> dict[str, Any]:
        p = Path(path).resolve()
        if not p.exists():
            return {"status": "error", "message": f"File not found: {p}"}
        try:
            import openpyxl
            wb = openpyxl.load_workbook(str(p))
            ws = wb[sheet_name] if sheet_name and sheet_name in wb.sheetnames else wb.active
            ws[cell] = value
            wb.save(str(p))
            return {"status": "edited", "path": str(p), "cell": cell, "value": value}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    # ── PowerPoint (.pptx) ───────────────────────────────────────────────────

    def _create_presentation(self, path: str, slides: list[dict[str, str]]) -> dict[str, Any]:
        p = Path(path).resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        try:
            from pptx import Presentation
            prs = Presentation()
            layout = prs.slide_layouts[1]  # Title and Content
            for slide_data in slides:
                slide = prs.slides.add_slide(layout)
                slide.shapes.title.text = slide_data.get("title") or ""
                slide.placeholders[1].text = slide_data.get("body") or ""
            prs.save(str(p))
            return {"status": "created", "path": str(p), "slides": len(slides)}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def _read_presentation(self, path: str) -> dict[str, Any]:
        p = Path(path).resolve()
        if not p.exists():
            return {"status": "error", "message": f"File not found: {p}"}
        try:
            from pptx import Presentation
            prs = Presentation(str(p))
            slides_out = []
            for i, slide in enumerate(prs.slides):
                texts = [shape.text for shape in slide.shapes if hasattr(shape, "text")]
                slides_out.append({"slide": i + 1, "text": "\n".join(texts)})
            return {"status": "ok", "path": str(p), "slides": slides_out}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    # ── Text extraction ───────────────────────────────────────────────────────

    def _extract_text(self, path: str) -> dict[str, Any]:
        p = Path(path).resolve()
        if not p.exists():
            return {"status": "error", "message": f"File not found: {p}"}
        ext = p.suffix.lower()
        try:
            if ext == ".docx":
                return self._read_doc(path)
            elif ext in (".xlsx", ".xls"):
                return self._read_spreadsheet(path)
            elif ext == ".pptx":
                return self._read_presentation(path)
            elif ext in (".txt", ".md", ".csv"):
                return {"status": "ok", "path": str(p), "text": p.read_text(encoding="utf-8")}
            else:
                return {"status": "error", "message": f"Unsupported file type: {ext}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    # ── Print ─────────────────────────────────────────────────────────────────

    def _print_file(self, path: str) -> dict[str, Any]:
        if not path or not os.path.exists(path):
            return {"status": "error", "message": "File not found"}
        _, win32api = _try_import_win32()
        if win32api:
            try:
                win32api.ShellExecute(0, "print", path, None, ".", 0)
                return {"status": "sent_to_printer", "path": path}
            except Exception as e:
                logger.warning(f"[OfficePlugin] ShellExecute print failed: {e}")
        try:
            os.startfile(path, "print")
            return {"status": "sent_to_printer_fallback", "path": path}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    # ── Convert ───────────────────────────────────────────────────────────────

    def _convert(self, src: str, fmt: str) -> dict[str, Any]:
        """Convert a document to another format (e.g. .docx → PDF)."""
        p = Path(src).resolve()
        if not p.exists():
            return {"status": "error", "message": f"Source file not found: {p}"}
        if fmt.lower() == "pdf":
            # Try LibreOffice first (free, no Office required)
            try:
                result = subprocess.run(
                    ["soffice", "--headless", "--convert-to", "pdf", str(p)],
                    capture_output=True, timeout=30,
                )
                if result.returncode == 0:
                    return {"status": "converted", "src": str(p), "output": str(p.with_suffix(".pdf")), "engine": "libreoffice"}
            except (FileNotFoundError, subprocess.TimeoutExpired):
                pass
            # Fallback: COM Word automation
            win32com, _ = _try_import_win32()
            if win32com and self._office_installed:
                try:
                    word = win32com.Dispatch("Word.Application")
                    word.Visible = False
                    doc = word.Documents.Open(str(p))
                    out = p.with_suffix(".pdf")
                    doc.SaveAs(str(out), FileFormat=17)  # 17 = wdFormatPDF
                    doc.Close()
                    word.Quit()
                    return {"status": "converted", "src": str(p), "output": str(out), "engine": "ms_word_com"}
                except Exception as e:
                    return {"status": "error", "message": f"COM conversion failed: {e}"}
            return {"status": "error", "message": "No PDF engine available (LibreOffice or MS Word required)"}
        return {"status": "unsupported", "message": f"Conversion to '{fmt}' is not yet implemented"}

    # ================================================================== COM / MS-Office implementations

    def _require_com(self, feature_name: str) -> None:
        """Raise a descriptive error if COM or MS Office is unavailable."""
        win32com, _ = _try_import_win32()
        if win32com is None:
            raise RuntimeError(
                f"[OfficePlugin] '{feature_name}' requires pywin32. "
                "Install it with: pip install pywin32"
            )
        if not self._office_installed:
            raise RuntimeError(
                f"[OfficePlugin] '{feature_name}' requires Microsoft Office to be installed. "
                "pywin32 is available but no Office installation was detected. "
                "Note: pywin32 is used for general Windows desktop integration — "
                "MS Office is only needed for COM automation features like Outlook or live Excel control."
            )

    def _com_open(self, prog_id: str, path: str) -> dict[str, Any]:
        """Open a file in the specified COM application."""
        try:
            self._require_com(prog_id)
            win32com, _ = _try_import_win32()
            app = win32com.Dispatch(prog_id)
            app.Visible = True
            if path and os.path.exists(path):
                p = str(Path(path).resolve())
                if "Word" in prog_id:
                    app.Documents.Open(p)
                elif "Excel" in prog_id:
                    app.Workbooks.Open(p)
                elif "PowerPoint" in prog_id:
                    app.Presentations.Open(p)
            return {"status": "opened", "app": prog_id, "path": path}
        except RuntimeError as e:
            return {"status": "error", "message": str(e), "office_required": True}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    # ── Outlook ──────────────────────────────────────────────────────────────

    @staticmethod
    def _outlook_com_error(e: Exception) -> dict[str, Any]:
        """
        Convert a raw COM exception from Outlook into a structured, human-readable error.

        Known MAPI error codes:
          -2147221231 (0x80040111) = MAPI_E_LOGON_FAILED / no profile configured
          -2147352567 (0x80020009) = DISP_E_EXCEPTION (wrapper around the real error)
        """
        msg = str(e)
        # Extract the inner HRESULT from the COM exception tuple if present
        # COM errors look like: (-2147352567, '...', (4096, 'Microsoft Outlook', '<real msg>', ..., <hresult>), None)
        inner_hresult = None
        inner_msg = ""
        try:
            args = e.args  # type: ignore[union-attr]
            if len(args) >= 3 and isinstance(args[2], tuple) and len(args[2]) >= 6:
                inner_msg = str(args[2][2])
                inner_hresult = args[2][5]
        except Exception:
            pass

        NO_PROFILE_HRESULTS = {-2147221231, -2147221227, -2147221228}
        if inner_hresult in NO_PROFILE_HRESULTS or "information store" in msg.lower() or "data file" in msg.lower():
            return {
                "status": "error",
                "error_code": "OUTLOOK_NO_PROFILE",
                "message": (
                    "Outlook is installed but no email profile (MAPI data store) is configured. "
                    "Open Outlook, complete the account setup wizard, then try again. "
                    f"(Outlook said: {inner_msg or msg})"
                ),
                "outlook_profile_required": True,
            }

        return {"status": "error", "message": inner_msg or msg}

    def _outlook_send(self, to: str, subject: str, body: str, cc: str = "", attachment: str = "") -> dict[str, Any]:
        """Send an email via Outlook COM automation (requires Outlook installed)."""
        try:
            self._require_com("Outlook")
            win32com, _ = _try_import_win32()
            outlook = win32com.Dispatch("Outlook.Application")
            mail = outlook.CreateItem(0)  # 0 = olMailItem
            mail.To = to
            mail.Subject = subject
            mail.Body = body
            if cc:
                mail.CC = cc
            if attachment and os.path.exists(attachment):
                mail.Attachments.Add(str(Path(attachment).resolve()))
            mail.Send()
            logger.info(f"[OfficePlugin] Outlook email sent to {to!r}")
            return {"status": "sent", "to": to, "subject": subject}
        except RuntimeError as e:
            return {"status": "error", "message": str(e), "office_required": True}
        except Exception as e:
            logger.error(f"[OfficePlugin] Outlook send failed: {e}")
            return self._outlook_com_error(e)

    def _outlook_read_inbox(self, limit: int = 10, folder: str = "Inbox") -> dict[str, Any]:
        """Read recent emails from Outlook inbox via COM."""
        try:
            self._require_com("Outlook")
            win32com, _ = _try_import_win32()
            outlook = win32com.Dispatch("Outlook.Application")
            ns = outlook.GetNamespace("MAPI")
            inbox = ns.GetDefaultFolder(6)  # 6 = olFolderInbox
            messages = inbox.Items
            messages.Sort("[ReceivedTime]", True)
            results = []
            for i, msg in enumerate(messages):
                if i >= limit:
                    break
                results.append({
                    "from": msg.SenderEmailAddress,
                    "subject": msg.Subject,
                    "received": str(msg.ReceivedTime),
                    "body_preview": (msg.Body or "")[:200],
                })
            return {"status": "ok", "folder": folder, "count": len(results), "messages": results}
        except RuntimeError as e:
            return {"status": "error", "message": str(e), "office_required": True}
        except Exception as e:
            return self._outlook_com_error(e)

    def _outlook_create_event(self, subject: str, start: str, end: str, location: str = "", body: str = "") -> dict[str, Any]:
        """Create a calendar event in Outlook via COM."""
        try:
            self._require_com("Outlook Calendar")
            win32com, _ = _try_import_win32()
            outlook = win32com.Dispatch("Outlook.Application")
            appt = outlook.CreateItem(1)  # 1 = olAppointmentItem
            appt.Subject = subject
            appt.Start = start
            appt.End = end
            if location:
                appt.Location = location
            if body:
                appt.Body = body
            appt.Save()
            logger.info(f"[OfficePlugin] Calendar event created: {subject!r}")
            return {"status": "created", "subject": subject, "start": start, "end": end}
        except RuntimeError as e:
            return {"status": "error", "message": str(e), "office_required": True}
        except Exception as e:
            return self._outlook_com_error(e)

