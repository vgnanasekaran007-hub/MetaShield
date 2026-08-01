"""
MetaShield – Metadata Exporter
================================
Export extracted metadata to JSON, CSV, TXT and PDF formats.
"""

import csv
import io
import json
import os
from datetime import datetime
from typing import Any, Dict


# ---------------------------------------------------------------------------
# JSON
# ---------------------------------------------------------------------------

def export_json(metadata: Dict, dst_path: str) -> str:
    """Write metadata as pretty-printed JSON."""
    _exclude_binary(metadata)
    with open(dst_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False, default=str)
    return dst_path


# ---------------------------------------------------------------------------
# CSV
# ---------------------------------------------------------------------------

def export_csv(metadata: Dict, dst_path: str) -> str:
    """Write metadata as two-column CSV (Key, Value)."""
    flat = _flatten(metadata)
    with open(dst_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Key", "Value"])
        for k, v in flat.items():
            writer.writerow([k, str(v) if v is not None else ""])
    return dst_path


# ---------------------------------------------------------------------------
# TXT
# ---------------------------------------------------------------------------

def export_txt(metadata: Dict, dst_path: str) -> str:
    """Write metadata as human-readable text report."""
    flat = _flatten(metadata)
    filename = metadata.get("file_info", {}).get("filename", "unknown")
    lines = [
        "=" * 60,
        f"  MetaShield – Metadata Report",
        f"  File: {filename}",
        f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "=" * 60,
        "",
    ]
    for k, v in flat.items():
        lines.append(f"  {k:<40} {v}")
    lines += ["", "=" * 60]
    with open(dst_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return dst_path


# ---------------------------------------------------------------------------
# PDF  (reportlab)
# ---------------------------------------------------------------------------

def export_pdf(metadata: Dict, dst_path: str) -> str:
    """Write metadata as a styled PDF report using reportlab."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
        )

        flat = _flatten(metadata)
        filename = metadata.get("file_info", {}).get("filename", "unknown")

        doc = SimpleDocTemplate(
            dst_path,
            pagesize=A4,
            leftMargin=15 * mm,
            rightMargin=15 * mm,
            topMargin=20 * mm,
            bottomMargin=20 * mm,
        )

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "Title",
            parent=styles["Title"],
            fontSize=20,
            textColor=colors.HexColor("#2563EB"),
            spaceAfter=4,
        )
        sub_style = ParagraphStyle(
            "Sub",
            parent=styles["Normal"],
            fontSize=10,
            textColor=colors.HexColor("#64748B"),
            spaceAfter=12,
        )
        section_style = ParagraphStyle(
            "Section",
            parent=styles["Heading2"],
            fontSize=13,
            textColor=colors.HexColor("#1E293B"),
            spaceBefore=12,
            spaceAfter=4,
        )

        story = []
        story.append(Paragraph("MetaShield – Image Metadata Report", title_style))
        story.append(Paragraph(f"File: {filename}  |  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", sub_style))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#E2E8F0")))
        story.append(Spacer(1, 10))

        # Build table data
        table_data = [["Key", "Value"]]
        for k, v in flat.items():
            val_str = str(v) if v is not None else ""
            if len(val_str) > 120:
                val_str = val_str[:120] + "…"
            table_data.append([k, val_str])

        col_widths = [75 * mm, 95 * mm]
        table = Table(table_data, colWidths=col_widths, repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2563EB")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 10),
            ("ALIGN", (0, 0), (-1, 0), "LEFT"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
            ("FONTSIZE", (0, 1), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
            ("PADDING", (0, 0), (-1, -1), 4),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        story.append(table)

        doc.build(story)
    except ImportError:
        # Fallback: plain text in a .pdf.txt file
        export_txt(metadata, dst_path.replace(".pdf", "_report.txt"))
        # Still create a minimal pdf placeholder
        with open(dst_path, "wb") as f:
            f.write(b"%PDF-1.4\n% reportlab not installed\n")

    return dst_path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _exclude_binary(d: Dict) -> None:
    """Remove or shorten binary/large values in-place."""
    skip = {"histogram", "thumbnail"}
    for k in list(d.keys()):
        if k in skip:
            d.pop(k)
        elif isinstance(d[k], dict):
            _exclude_binary(d[k])


def _flatten(meta: Dict, prefix: str = "", result: Dict = None) -> Dict:
    if result is None:
        result = {}
    skip = {"histogram", "thumbnail", "color_palette"}
    for k, v in meta.items():
        if k in skip:
            continue
        full_key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            _flatten(v, full_key, result)
        elif isinstance(v, list):
            result[full_key] = ", ".join(str(i) for i in v)
        else:
            result[full_key] = v
    return result
