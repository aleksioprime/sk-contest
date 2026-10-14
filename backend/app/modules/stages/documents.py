"""Дипломы (PDF) и программа защит (XLSX)."""

from io import BytesIO
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

FONT_DIR = Path('/usr/share/fonts/truetype/dejavu')
BRAND = HexColor('#6d28d9')
INK = HexColor('#1d1a2b')
MUTED = HexColor('#5f5a75')

AWARD_TITLES = {'winner': 'Диплом победителя', 'prize': 'Диплом призёра', 'participant': 'Сертификат участника'}


def _fonts() -> tuple[str, str]:
    """Кириллический шрифт DejaVu, если установлен (в Docker-образе есть), иначе встроенный."""
    regular, bold = FONT_DIR / 'DejaVuSans.ttf', FONT_DIR / 'DejaVuSans-Bold.ttf'
    if regular.exists() and bold.exists():
        if 'DejaVu' not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont('DejaVu', str(regular)))
            pdfmetrics.registerFont(TTFont('DejaVu-Bold', str(bold)))
        return 'DejaVu', 'DejaVu-Bold'
    return 'Helvetica', 'Helvetica-Bold'


def _wrap(c: canvas.Canvas, text: str, font: str, size: int, width: float) -> list[str]:
    lines, line = [], ''
    for word in text.split():
        candidate = f'{line} {word}'.strip()
        if c.stringWidth(candidate, font, size) <= width:
            line = candidate
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def diplomas_pdf(entries: list[dict], event_title: str, awards: dict) -> bytes:
    """entries: [{name, award, rank, direction, work_title}] — одна страница на участника."""
    regular, bold = _fonts()
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=landscape(A4))
    width, height = landscape(A4)
    signatory = awards.get('signatory', '')
    signatory_title = awards.get('signatory_title', '')
    date_text = awards.get('date_text', '')
    for entry in entries:
        c.setStrokeColor(BRAND)
        c.setLineWidth(6)
        c.rect(24, 24, width - 48, height - 48)
        c.setLineWidth(1)
        c.rect(36, 36, width - 72, height - 72)

        c.setFillColor(MUTED)
        c.setFont(regular, 14)
        c.drawCentredString(width / 2, height - 90, event_title)

        c.setFillColor(BRAND)
        c.setFont(bold, 40)
        c.drawCentredString(width / 2, height - 160, AWARD_TITLES[entry['award']].upper())

        place = ''
        if entry['award'] != 'participant' and entry.get('rank'):
            place = f'{entry["rank"]} место'
        c.setFillColor(INK)
        c.setFont(regular, 16)
        c.drawCentredString(width / 2, height - 205, 'награждается' if place else 'выдан')
        c.setFont(bold, 30)
        c.drawCentredString(width / 2, height - 250, entry['name'])

        details = ' · '.join(filter(None, [place, entry.get('direction')]))
        y = height - 290
        if details:
            c.setFont(regular, 16)
            c.drawCentredString(width / 2, y, details)
            y -= 30
        if entry.get('work_title'):
            c.setFillColor(MUTED)
            for line in _wrap(c, f'Работа «{entry["work_title"]}»', regular, 14, width - 200)[:3]:
                c.setFont(regular, 14)
                c.drawCentredString(width / 2, y, line)
                y -= 20

        c.setFillColor(INK)
        c.setFont(regular, 12)
        if signatory:
            c.drawString(90, 90, signatory_title)
            c.drawRightString(width - 90, 90, signatory)
            c.line(width - 330, 105, width - 90, 105)
        if date_text:
            c.setFillColor(MUTED)
            c.drawCentredString(width / 2, 60, date_text)
        c.showPage()
    c.save()
    return buffer.getvalue()


def program_xlsx(stage_title: str, slots: list[dict]) -> bytes:
    """slots: [{starts_at, ends_at, room, title, items: [{number, title, participants, direction}]}]."""
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = 'Программа'
    sheet.append([f'Программа: {stage_title}'])
    sheet['A1'].font = Font(bold=True, size=14)
    sheet.append([])
    sheet.append(['Время', 'Аудитория', 'Слот', '№', 'Работа', 'Участники', 'Направление'])
    for cell in sheet[3]:
        cell.font = Font(bold=True)
    for slot in slots:
        time = slot['starts_at'].strftime('%d.%m %H:%M')
        if slot.get('ends_at'):
            time += f'–{slot["ends_at"].strftime("%H:%M")}'
        if not slot['items']:
            sheet.append([time, slot['room'], slot['title'], '', '', '', ''])
        for item in slot['items']:
            sheet.append(
                [
                    time,
                    slot['room'],
                    slot['title'],
                    item['number'],
                    item['title'],
                    ', '.join(item['participants']),
                    item['direction'],
                ]
            )
    for column, width in zip('ABCDEFG', (16, 14, 20, 6, 40, 36, 24), strict=True):
        sheet.column_dimensions[column].width = width
    for row in sheet.iter_rows(min_row=4):
        for cell in row:
            cell.alignment = Alignment(wrap_text=True, vertical='top')
    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()
