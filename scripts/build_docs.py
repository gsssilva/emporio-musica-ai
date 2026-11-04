"""Generate the delivery PDF from an explicit, versioned Markdown source list."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import subprocess
import textwrap
from pathlib import Path
from urllib.parse import quote

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    BaseDocTemplate, Frame, LongTable, PageBreak, PageTemplate, Paragraph,
    Spacer, TableStyle, XPreformatted,
)
from reportlab.platypus.tableofcontents import TableOfContents

ROOT = Path(__file__).resolve().parents[1]
DOCUMENTS = ["README.md", "docs/arquitetura.md", "docs/ingestao.md", "docs/consultas.md",
             "docs/retrieval.md", "docs/agente.md", "docs/api-local.md", "docs/interface.md", "docs/avaliacao.md",
             "docs/entendimento.md", "examples/01-catalogo.md", "examples/02-promocao-pix.md",
             "examples/03-devolucao.md", "examples/04-pedido-demo.md", "examples/05-fora-de-escopo.md"]
GREEN, INK, MUTED = colors.HexColor("#173e32"), colors.HexColor("#20322b"), colors.HexColor("#5a6861")


def clean(text: str) -> str:
    text = re.sub(r"[\U0001f000-\U0001ffff\ufe0f]", "", text)
    for dash in "‐‑‒–—−":
        text = text.replace(dash, "-")
    return text.replace("→", "->").replace("\u00a0", " ").replace("\u200b", "")


def register_fonts() -> tuple[str, str, str]:
    candidates = [
        (Path("C:/Windows/Fonts/arial.ttf"), Path("C:/Windows/Fonts/arialbd.ttf"), Path("C:/Windows/Fonts/consola.ttf")),
        (Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"), Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"), Path("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf")),
    ]
    for regular, bold, mono in candidates:
        if all(path.exists() for path in (regular, bold, mono)):
            for name, path in [("Body", regular), ("BodyBold", bold), ("Mono", mono)]:
                pdfmetrics.registerFont(TTFont(name, str(path)))
            pdfmetrics.registerFontFamily("Body", normal="Body", bold="BodyBold", italic="Body", boldItalic="BodyBold")
            return "Body", "BodyBold", "Mono"
    return "Helvetica", "Helvetica-Bold", "Courier"


def git_value(*args: str) -> str:
    try:
        return subprocess.check_output(["git", "-C", str(ROOT), *args], text=True,
                                       stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        return "not available"


class DeliveryDocument(BaseDocTemplate):
    def beforeDocument(self):
        self.heading_number = 0

    def afterFlowable(self, flowable):
        if isinstance(flowable, Paragraph) and flowable.style.name == "DocH1":
            self.heading_number += 1
            key = "chapter-" + str(self.heading_number)
            self.canv.bookmarkPage(key)
            self.canv.addOutlineEntry(flowable.getPlainText(), key, level=0)
            self.notify("TOCEntry", (0, flowable.getPlainText(), self.page, key))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "output/pdf/Gabriel Silva - AI Engineer - Full-Stack Generative AI Applications.pdf")
    parser.add_argument("--allow-dirty", action="store_true", help="Allow uncommitted Markdown sources")
    args = parser.parse_args()
    for name in DOCUMENTS:
        if not (ROOT / name).is_file():
            parser.error("Missing source: " + name)
    if not args.allow_dirty:
        dirty = git_value("status", "--porcelain", "--", *DOCUMENTS)
        if dirty:
            parser.error("Commit the Markdown sources first to record a verifiable revision.")
    revision, timestamp = git_value("rev-parse", "HEAD"), git_value("show", "-s", "--format=%cI", "HEAD")
    body, bold, mono = register_fonts()
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle("DocH1", fontName=bold, fontSize=22, leading=27, textColor=GREEN, spaceAfter=16, keepWithNext=True))
    styles.add(ParagraphStyle("DocH2", fontName=bold, fontSize=13, leading=18, textColor=GREEN, spaceBefore=15, spaceAfter=7, keepWithNext=True))
    styles.add(ParagraphStyle("DocH3", fontName=bold, fontSize=10.5, leading=14.5, textColor=INK, spaceBefore=10, spaceAfter=5, keepWithNext=True))
    styles.add(ParagraphStyle("DocBody", fontName=body, fontSize=9.5, leading=14, textColor=INK, spaceAfter=7, splitLongWords=True))
    styles.add(ParagraphStyle("DocSmall", parent=styles["DocBody"], fontSize=8, leading=11, textColor=MUTED))
    styles.add(ParagraphStyle("DocCode", fontName=mono, fontSize=7.6, leading=10.3, textColor=INK, backColor=colors.HexColor("#f1f4ef"), borderPadding=8, spaceBefore=4, spaceAfter=10))
    styles.add(ParagraphStyle("DocCell", parent=styles["DocBody"], fontSize=8, leading=10.7, spaceAfter=0))
    styles.add(ParagraphStyle("DocBullet", parent=styles["DocBody"], leftIndent=12, firstLineIndent=-9, spaceAfter=5))
    width, height = A4
    content_width = width - 100

    def inline(text: str, source: str) -> str:
        text = clean(text)
        links = []

        def protect_link(match):
            label, target = match[1], match[2].strip("<>")
            if not target.startswith(("https://", "http://")):
                resolved = (Path(source).parent / target).as_posix()
                ref = "main" if resolved == "output/pdf/Gabriel Silva - AI Engineer - Full-Stack Generative AI Applications.pdf" else revision
                target = "https://github.com/gsssilva/emporio-musica-ai/blob/" + ref + "/" + quote(resolved)
            index = len(links)
            links.append('<link href="' + html.escape(target, quote=True) + '" color="#245c49">' + html.escape(label) + '</link>')
            return "LINKTOKEN" + str(index) + "END"

        text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", protect_link, text)
        text = html.escape(text)
        text = re.sub(r"`([^`]+)`", lambda match: '<font name="' + mono + '">' + match[1] + '</font>', text)
        text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
        for index, link in enumerate(links):
            text = text.replace("LINKTOKEN" + str(index) + "END", link)
        return text

    def footer(canv, doc):
        canv.saveState()
        canv.setStrokeColor(colors.HexColor("#dce3dc"))
        canv.line(50, 40, width - 50, 40)
        canv.setFont(body, 7.5)
        canv.setFillColor(MUTED)
        canv.drawString(50, 27, "Empório da Música - Technical documentation")
        canv.drawRightString(width - 50, 27, "Page " + str(doc.page))
        canv.restoreState()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    document = DeliveryDocument(str(args.output), pagesize=A4, title="Empório da Música - Project documentation",
                                author="Gabriel Silva", leftMargin=50, rightMargin=50, topMargin=48, bottomMargin=54)
    document.addPageTemplates(PageTemplate(id="Main", frames=[Frame(50, 54, content_width, height - 102, leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)], onPage=footer))
    story = [Spacer(1, 65), Paragraph("EMPÓRIO DA MÚSICA", ParagraphStyle("CoverLabel", fontName=bold, fontSize=12, leading=18, textColor=GREEN)),
             Spacer(1, 18), Paragraph("Generative AI<br/>support assistant", ParagraphStyle("CoverTitle", fontName=bold, fontSize=32, leading=39, textColor=INK)),
             Spacer(1, 20), Paragraph("Technical challenge - AI Engineer", styles["DocH2"]),
             Paragraph("Python, structured queries, and policy retrieval with a locally executed model.", styles["DocBody"]),
             Spacer(1, 34), Paragraph("Gabriel Silva", styles["DocH2"]),
             Paragraph("Model: Qwen3 8B through Ollama. No paid inference API.", styles["DocBody"]),
             Paragraph("Source revision: " + html.escape(revision), styles["DocSmall"]),
             Paragraph("Revision timestamp: " + html.escape(timestamp), styles["DocSmall"]),
             Spacer(1, 24), Paragraph("I prepared this submission from the versioned README, technical documentation, and five labelled translations of recorded conversations.", styles["DocBody"]),
             Paragraph('<link href="https://github.com/gsssilva/emporio-musica-ai" color="#245c49">github.com/gsssilva/emporio-musica-ai</link>', styles["DocBody"]), PageBreak()]
    toc = TableOfContents()
    toc.levelStyles = [ParagraphStyle("Contents", fontName=body, fontSize=10, leading=17, leftIndent=0, firstLineIndent=0, spaceBefore=5, textColor=INK)]
    story += [Paragraph("Contents", styles["DocH2"]), Spacer(1, 10), toc, PageBreak()]

    manifest = {}
    for position, name in enumerate(DOCUMENTS):
        if position:
            story.append(PageBreak())
        raw = (ROOT / name).read_bytes()
        manifest[name] = hashlib.sha256(raw).hexdigest()
        story.append(Paragraph(html.escape(name), styles["DocSmall"]))
        lines = raw.decode("utf-8-sig").splitlines()
        index = 0
        while index < len(lines):
            line = lines[index]
            if not line.strip():
                index += 1
                continue
            if line.startswith("```"):
                index += 1
                code = []
                while index < len(lines) and not lines[index].startswith("```"):
                    code.extend(textwrap.wrap(clean(lines[index]), width=112, replace_whitespace=False, drop_whitespace=False) or [""])
                    index += 1
                story.append(XPreformatted(html.escape("\n".join(code)), styles["DocCode"]))
                index += 1
                continue
            match = re.match(r"^(#{1,6})\s+(.+)", line)
            if match:
                title = match[2]
                if name.startswith("examples/") and len(match[1]) == 1:
                    title = match[2]
                style = "DocH1" if len(match[1]) == 1 else "DocH2" if len(match[1]) == 2 else "DocH3"
                story.append(Paragraph(inline(title, name), styles[style]))
                index += 1
                continue
            if line.strip().startswith("|"):
                rows = []
                while index < len(lines) and lines[index].strip().startswith("|"):
                    cells = [cell.strip() for cell in lines[index].strip().strip("|").split("|")]
                    if not all(re.fullmatch(r":?-+:?", cell.replace(" ", "")) for cell in cells):
                        rows.append([Paragraph(inline(cell, name), styles["DocCell"]) for cell in cells])
                    index += 1
                columns = max(map(len, rows))
                rows = [row + [Paragraph("", styles["DocCell"])] * (columns - len(row)) for row in rows]
                table = LongTable(rows, colWidths=[content_width / columns] * columns, repeatRows=1, hAlign="LEFT")
                table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dce8df")),
                                           ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 6),
                                           ("RIGHTPADDING", (0, 0), (-1, -1), 6), ("TOPPADDING", (0, 0), (-1, -1), 6),
                                           ("BOTTOMPADDING", (0, 0), (-1, -1), 6), ("LINEBELOW", (0, 0), (-1, 0), .6, GREEN),
                                           ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f7f8f5")])]))
                story += [table, Spacer(1, 10)]
                continue
            if re.match(r"^\s*(?:[-*]|\d+\.)\s+", line):
                story.append(Paragraph(inline(line.strip(), name), styles["DocBullet"]))
                index += 1
                continue
            paragraph = [line.strip()]
            index += 1
            while index < len(lines) and lines[index].strip() and not re.match(r"^(?:#|```|\||\s*[-*]\s|\d+\.\s)", lines[index]):
                paragraph.append(lines[index].strip())
                index += 1
            story.append(Paragraph(inline(" ".join(paragraph), name), styles["DocBody"]))

    def invariant_canvas(*args, **kwargs):
        kwargs["invariant"] = 1
        return canvas.Canvas(*args, **kwargs)

    document.multiBuild(story, canvasmaker=invariant_canvas)
    manifest_path = ROOT / "runtime/pdf-sources.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps({"revision": revision, "sources": manifest}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(str(args.output.resolve()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
