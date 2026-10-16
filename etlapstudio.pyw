"""ÉtlapStúdió: helyi asztali étlapkészítő, üres induló adatbázissal."""
from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
import base64
import io
import shutil
from datetime import date, datetime, timedelta
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, colorchooser

from themes import load_themes, import_theme, HEX


APP_NAME = "ÉtlapStúdió"
CATEGORIES = [
    "Levesek", "Főzelékek", "Feltétek", "Köretek", "Savanyúságok",
    "Készételek", "Frissensültek", "Tészták, desszertek", "Mártások, öntetek", "Egyéb",
]
WEEKDAYS = ["Hétfő", "Kedd", "Szerda", "Csütörtök", "Péntek"]
GREEN = "#1D6B50"
DEEP = "#123F32"
PAPER = "#F7F8F4"
TEXT = "#21342D"
FONT_OPTIONS = {"Modern sans": "DejaVu", "Klasszikus talpas": "DejaVuSerif"}
LEADERS = {"Nincs": "none", "Pontozott": "dots", "Szaggatott": "dashes", "Folytonos vonal": "line"}


def chosen_font(store, role, bold=False):
    family = FONT_OPTIONS.get(store.setting("font_" + role, "Modern sans"), "DejaVu")
    return family + ("-Bold" if bold else "")


def draw_leader(canvas, x1, x2, y, mode, color, size=8):
    if mode not in LEADERS.values() or mode == "none" or x2 <= x1 + 2:
        return
    canvas.saveState()
    canvas.setStrokeColor(color)
    canvas.setFillColor(color)
    if mode == "dots":
        step = max(2.3, size * .42)
        x = x1 + step / 2
        while x < x2:
            canvas.circle(x, y, max(.24, size * .035), stroke=0, fill=1)
            x += step
    else:
        canvas.setLineWidth(.38)
        if mode == "dashes": canvas.setDash(max(1.5, size * .28), max(1.5, size * .25))
        canvas.line(x1, y, x2, y)
    canvas.restoreState()


def background_path(store):
    name = store.setting("background_file")
    if name and Path(name).name == name:
        path = data_dir() / "backgrounds" / name
        if path.is_file(): return path
    if store.setting("background_builtin", "0") == "1":
        path = Path(__file__).resolve().parent / "backgrounds" / "botanical.png"
        if path.is_file(): return path
    return None


def draw_background(canvas, store, width, height):
    path = background_path(store)
    if not path or store.setting("background_enabled", "0") != "1": return
    from PIL import Image
    from reportlab.lib.utils import ImageReader
    with Image.open(path) as source:
        if source.width * source.height > 36_000_000:
            raise ValueError("A háttérkép túl nagy (legfeljebb 36 megapixel).")
        im = source.convert("RGBA")
        opacity = max(0, min(100, int(store.setting("background_opacity", "30")))) / 100
        im.putalpha(im.getchannel("A").point(lambda a: int(a * opacity)))
        canvas.drawImage(ImageReader(im), 0, 0, width, height, mask="auto")


def data_dir() -> Path:
    root = Path.home() / "Documents" / "EtlapStudio"
    root.mkdir(parents=True, exist_ok=True)
    return root


def monday(day: date) -> date:
    return day - timedelta(days=day.weekday())


def display_date(day: date) -> str:
    return day.strftime("%Y.%m.%d.")


def price(amount: int) -> str:
    return f"{amount:,}".replace(",", " ") + " Ft"


class Store:
    def __init__(self, path: Path):
        self.path = path
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys = ON")
        with self.db:
            self.db.executescript("""
                CREATE TABLE IF NOT EXISTS dishes (
                    id INTEGER PRIMARY KEY, name TEXT NOT NULL, category TEXT NOT NULL,
                    price INTEGER NOT NULL CHECK(price >= 0), active INTEGER NOT NULL DEFAULT 1
                );
                CREATE TABLE IF NOT EXISTS daily_selection (
                    day TEXT NOT NULL, dish_id INTEGER NOT NULL REFERENCES dishes(id),
                    PRIMARY KEY(day, dish_id)
                );
                CREATE TABLE IF NOT EXISTS weekly_menu (
                    day TEXT PRIMARY KEY, soup TEXT NOT NULL DEFAULT '',
                    menu_a TEXT NOT NULL DEFAULT '', menu_b TEXT NOT NULL DEFAULT ''
                );
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY, value TEXT NOT NULL
                );
            """)

    def dishes(self, query: str = ""):
        return self.db.execute(
            "SELECT * FROM dishes WHERE active=1 AND (name LIKE ? OR category LIKE ?) "
            "ORDER BY category, name COLLATE NOCASE, id",
            (f"%{query}%", f"%{query}%"),
        ).fetchall()

    def add_dish(self, name: str, category: str, amount: int, dish_id=None):
        with self.db:
            if dish_id:
                self.db.execute("UPDATE dishes SET name=?, category=?, price=? WHERE id=?",
                                (name, category, amount, dish_id))
            else:
                self.db.execute("INSERT INTO dishes(name,category,price) VALUES(?,?,?)",
                                (name, category, amount))

    def delete_dish(self, dish_id: int):
        with self.db:
            # Soft delete keeps old dated selections and their PDF export intact.
            self.db.execute("UPDATE dishes SET active=0 WHERE id=?", (dish_id,))

    def selection(self, day: date):
        return self.db.execute("""
            SELECT d.* FROM daily_selection s JOIN dishes d ON d.id=s.dish_id
            WHERE s.day=? ORDER BY d.category, d.name COLLATE NOCASE
        """, (day.isoformat(),)).fetchall()

    def set_selected(self, day: date, dish_ids: list[int]):
        with self.db:
            self.db.execute("DELETE FROM daily_selection WHERE day=?", (day.isoformat(),))
            self.db.executemany("INSERT INTO daily_selection(day,dish_id) VALUES(?,?)",
                                [(day.isoformat(), x) for x in dish_ids])

    def week_entry(self, day: date):
        row = self.db.execute("SELECT soup,menu_a,menu_b FROM weekly_menu WHERE day=?",
                              (day.isoformat(),)).fetchone()
        return tuple(row) if row else ("", "", "")

    def set_week_entry(self, day: date, soup: str, menu_a: str, menu_b: str):
        with self.db:
            self.db.execute("""
                INSERT INTO weekly_menu(day,soup,menu_a,menu_b) VALUES(?,?,?,?)
                ON CONFLICT(day) DO UPDATE SET soup=excluded.soup,
                menu_a=excluded.menu_a,menu_b=excluded.menu_b
            """, (day.isoformat(), soup.strip(), menu_a.strip(), menu_b.strip()))

    def setting(self, key: str, default: str = "") -> str:
        row = self.db.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row[0] if row else default

    def set_settings(self, values: dict[str, str]):
        with self.db:
            self.db.executemany("""
                INSERT INTO settings(key,value) VALUES(?,?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value
            """, list(values.items()))


def fonts():
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    folder = Path(__file__).resolve().parent / "fonts"
    pdfmetrics.registerFont(TTFont("DejaVu", str(folder / "DejaVuSans.ttf")))
    pdfmetrics.registerFont(TTFont("DejaVu-Bold", str(folder / "DejaVuSans-Bold.ttf")))
    pdfmetrics.registerFontFamily("DejaVu", normal="DejaVu", bold="DejaVu-Bold")
    pdfmetrics.registerFont(TTFont("DejaVuSerif", str(folder / "DejaVuSerif.ttf")))
    pdfmetrics.registerFont(TTFont("DejaVuSerif-Bold", str(folder / "DejaVuSerif-Bold.ttf")))
    pdfmetrics.registerFontFamily("DejaVuSerif", normal="DejaVuSerif", bold="DejaVuSerif-Bold")


def make_social_daily_pdf(path: str, store: Store, target: date):
    """One 4:5 image page: fixed header, fitted à la carte section."""
    from reportlab.pdfgen import canvas as pdfcanvas
    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph
    from reportlab.graphics import renderPDF
    from svglib.svglib import svg2rlg
    from xml.sax.saxutils import escape
    fonts()
    page_w,page_h=200*mm,250*mm
    left,right=19*mm,19*mm
    body_width=page_w-left-right
    packs=load_themes(Path(__file__).resolve().parent/"themes_builtin",data_dir()/"themes")
    manifest,artdir=packs.get(store.setting("theme","classic"),packs["classic"])
    palette=manifest["palette"]
    primary=store.setting("theme_primary")
    accent=store.setting("theme_accent")
    primary=primary if HEX.fullmatch(primary) else palette["primary"]
    accent=accent if HEX.fullmatch(accent) else palette["accent"]
    decorated=store.setting("decorations","1")=="1"
    green=colors.HexColor(primary)
    dark=colors.HexColor("#263A30")
    line=colors.HexColor(accent)
    c=pdfcanvas.Canvas(path,pagesize=(page_w,page_h))
    c.setTitle("Napi étlap – "+display_date(target))

    def vector(name,x,y,w,h):
        svg=(artdir/manifest["assets"][name]).read_text(encoding="utf-8")
        svg=svg.replace(palette["primary"],primary).replace(palette["accent"],accent)
        picture=svg2rlg(io.BytesIO(svg.encode("utf-8")))
        c.saveState();c.translate(x,y);c.scale(w/picture.width,h/picture.height)
        renderPDF.draw(picture,c,0,0);c.restoreState()

    c.setFillColor(colors.white);c.rect(0,0,page_w,page_h,stroke=0,fill=1)
    draw_background(c,store,page_w,page_h)
    c.setStrokeColor(green);c.setLineWidth(.7)
    c.rect(7*mm,7*mm,page_w-14*mm,page_h-14*mm,stroke=1,fill=0)
    if decorated:vector("header",left,page_h-42*mm,body_width,28*mm)
    else:c.line(left,page_h-32*mm,page_w-right,page_h-32*mm)
    c.setFillColor(dark);c.setFont(chosen_font(store,"restaurant",True),14)
    c.drawCentredString(page_w/2,page_h-20*mm,(store.setting("restaurant") or "Étterem")[:48])
    c.setFont("DejaVu",8)
    address=store.setting("address");phone=store.setting("phone")
    c.drawCentredString(page_w/2,page_h-26*mm,
                         (address+("  •  " if address and phone else "")+phone)[:95])
    c.setFont(chosen_font(store,"title",True),20);c.drawCentredString(page_w/2,page_h-54*mm,"Napi étlap")
    c.setFont("DejaVu",9);c.drawCentredString(page_w/2,page_h-62*mm,display_date(target))

    # The specials block occupies the same rectangle on every daily image.
    special_top=page_h-74*mm
    special_bottom=special_top-39*mm
    c.setFillColor(colors.HexColor(palette["background"]))
    c.setStrokeColor(green)
    c.roundRect(left,special_bottom,body_width,39*mm,5*mm,stroke=1,fill=1)
    c.setFillColor(green);c.setFont(chosen_font(store,"heading",True),10)
    c.drawString(left+5*mm,special_top-6.5*mm,"MAI MENÜ")
    soup,menu_a,menu_b=store.week_entry(target)
    fields=[("Leves",soup),("A menü",menu_a),("B menü",menu_b)]
    right_x=left+31*mm
    field_w=body_width-36*mm
    max_special_h=29*mm
    size=9.0
    while True:
        style=ParagraphStyle("special",fontName=chosen_font(store,"special"),fontSize=size,leading=size*1.35,textColor=dark)
        measured=[]
        for label,value in fields:
            p=Paragraph(escape(value or "—"),style)
            _w,h=p.wrap(field_w,1000)
            measured.append((label,p,max(h,size*1.35)))
        if sum(x[2]+2 for x in measured)<=max_special_h:break
        size*=.86
        if size<.1:
            raise ValueError("A napi menü szövege túl hosszú a fix fejlécmezőhöz.")
    y=special_top-10*mm
    for label,p,h in measured:
        c.setFillColor(dark);c.setFont(chosen_font(store,"heading",True),max(4,size))
        c.drawString(left+5*mm,y-max(4,size),label)
        p.drawOn(c,right_x,y-h)
        y-=h+2

    body_top=page_h-129*mm
    body_bottom=20*mm
    if decorated:vector("divider",left,body_top+2*mm,body_width,8*mm)
    else:
        c.setStrokeColor(line);c.line(left,body_top+4*mm,page_w-right,body_top+4*mm)
    selected=store.selection(target)
    gap=9*mm;col_w=(body_width-gap)/2
    name_w=col_w-23*mm
    def layout(font_size):
        normal=ParagraphStyle("dish",fontName=chosen_font(store,"dish"),fontSize=font_size,
                              leading=font_size*1.3,textColor=dark)
        result=[];column=0;y=body_top;last_category=None
        for category in CATEGORIES:
            dishes=[row for row in selected if row["category"]==category]
            for row in dishes:
                paragraph=Paragraph(escape(row["name"]),normal)
                _w,h=paragraph.wrap(name_w,10000)
                h=max(h,font_size*1.3)+font_size*.35
                header_needed=last_category!=category
                header_h=font_size*1.9 if header_needed else 0
                if y-h-header_h<body_bottom:
                    column+=1
                    if column>=2:return None
                    y=body_top;last_category=None
                    header_needed=True;header_h=font_size*1.9
                if y-h-header_h<body_bottom:return None
                if header_needed:
                    result.append(("heading",column,y,category,font_size))
                    y-=header_h
                result.append(("item",column,y,paragraph,h,row["price"],font_size))
                y-=h
                last_category=category
        return result

    if selected:
        low,high=.2,9.3
        for _ in range(20):
            middle=(low+high)/2
            if layout(middle) is None:high=middle
            else:low=middle
        placements=layout(low)
        size=low
        while placements is None and size>.001:
            size*=.5
            placements=layout(size)
        if placements is None:
            raise ValueError("Túl sok à la carte sor egyetlen képre.")
        for item in placements:
            kind,column,y,*rest=item
            x=left+column*(col_w+gap)
            if kind=="heading":
                category,size=rest
                c.setFillColor(green);c.setFont(chosen_font(store,"heading",True),size*1.13)
                c.drawString(x,y-size*1.2,category)
            else:
                paragraph,h,amount,size=rest
                paragraph.drawOn(c,x,y-h+size*.35)
                baseline=y-size*1.25
                c.setFillColor(dark);c.setFont(chosen_font(store,"dish"),size)
                amount_text=price(amount)
                c.drawRightString(x+col_w,baseline,amount_text)
                from reportlab.pdfbase.pdfmetrics import stringWidth
                amount_width=stringWidth(amount_text,chosen_font(store,"dish"),size)
                draw_leader(c,x+name_w+size*.4,x+col_w-amount_width-size*.5,
                            baseline+size*.12,store.setting("leader","none"),line,size)
    else:
        c.setFillColor(dark);c.setFont("DejaVu",9)
        c.drawCentredString(page_w/2,body_top-12*mm,"Még nincs à la carte kínálat kiválasztva.")
    c.setStrokeColor(line);c.line(left,14*mm,page_w-right,14*mm)
    c.setFillColor(dark);c.setFont("DejaVu",7)
    c.drawString(left,10*mm,store.setting("note")[:100])
    c.showPage();c.save()


def make_pdf(path: str, store: Store, mode: str, target: date, social: bool = False):
    if social and mode=="daily":
        return make_social_daily_pdf(path,store,target)
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer, Table,
        TableStyle, KeepTogether, FrameBreak, Flowable,
    )
    from reportlab.graphics import renderPDF
    from svglib.svglib import svg2rlg
    from xml.sax.saxutils import escape
    fonts()
    page_w, page_h = (200*mm, 250*mm) if social else A4
    left, right, bottom, top = 19*mm, 19*mm, 18*mm, 45*mm
    body_width = page_w-left-right
    packs=load_themes(Path(__file__).resolve().parent/"themes_builtin",data_dir()/"themes")
    theme_id=store.setting("theme","classic")
    manifest, artdir=packs.get(theme_id, next(iter(packs.values())))
    palette=manifest["palette"]
    primary=store.setting("theme_primary")
    accent=store.setting("theme_accent")
    primary=primary if HEX.fullmatch(primary) else palette["primary"]
    accent=accent if HEX.fullmatch(accent) else palette["accent"]
    line = colors.HexColor(palette["background"])
    dark = colors.HexColor("#263A30")
    green = colors.HexColor(primary)
    accent_color = colors.HexColor(accent)
    decorated=store.setting("decorations","1") == "1"

    def vector(name):
        source=(artdir/manifest["assets"][name]).read_text(encoding="utf-8")
        source=source.replace(palette["primary"],primary).replace(palette["accent"],accent)
        return svg2rlg(io.BytesIO(source.encode("utf-8")))

    class Ornament(Flowable):
        def __init__(self, name, width, height):
            Flowable.__init__(self)
            self.name, self.width, self.height=name,width,height
        def draw(self):
            picture=vector(self.name)
            self.canv.saveState()
            self.canv.scale(self.width/picture.width,self.height/picture.height)
            renderPDF.draw(picture,self.canv,0,0)
            self.canv.restoreState()
    class DishTable(Table):
        def draw(self):
            super().draw()
            if store.setting("leader","none") != "none":
                for index in range(len(self._rowHeights)):
                    y=sum(self._rowHeights[index+1:])+self._rowHeights[index]/2
                    draw_leader(self.canv,col_width-34*mm+1,col_width-26*mm-1,
                                y,store.setting("leader","none"),accent_color,9)
    restaurant = store.setting("restaurant", "Étterem") or "Étterem"
    address = store.setting("address", "")
    phone = store.setting("phone", "")
    note = store.setting("note", "")
    small = ParagraphStyle("small", fontName="DejaVu", fontSize=8.5, leading=12, textColor=dark)
    food = ParagraphStyle("food", fontName=chosen_font(store,"special"), fontSize=9.3, leading=13, textColor=dark)
    dish_style = ParagraphStyle("dish", fontName=chosen_font(store,"dish"), fontSize=9.3, leading=13, textColor=dark)
    price_style = ParagraphStyle("price", parent=dish_style, alignment=TA_RIGHT)
    heading = ParagraphStyle("heading", fontName=chosen_font(store,"heading",True), fontSize=11.5,
                             leading=16, textColor=green, spaceBefore=9, spaceAfter=5)
    title = ParagraphStyle("title", fontName=chosen_font(store,"title",True), fontSize=21,
                           leading=27, alignment=TA_CENTER, textColor=dark, spaceAfter=5)
    subtitle = ParagraphStyle("subtitle", parent=small, alignment=TA_CENTER, spaceAfter=14)
    col_gap = 12*mm
    col_width = (body_width-col_gap)/2

    def decoration(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(colors.white)
        canvas.rect(0,0,page_w,page_h,stroke=0,fill=1)
        draw_background(canvas,store,page_w,page_h)
        if decorated:
            picture=vector("header")
            canvas.saveState()
            canvas.translate(left, page_h-42*mm)
            canvas.scale(body_width/picture.width,28*mm/picture.height)
            renderPDF.draw(picture,canvas,0,0)
            canvas.restoreState()
            corner=vector("corner")
            canvas.saveState()
            canvas.translate(7*mm,8*mm)
            canvas.scale(14*mm/corner.width,14*mm/corner.height)
            renderPDF.draw(corner,canvas,0,0)
            canvas.restoreState()
        else:
            canvas.setStrokeColor(green)
            canvas.setLineWidth(1.2)
            canvas.line(left,page_h-32*mm,page_w-right,page_h-32*mm)
        canvas.setStrokeColor(green)
        canvas.setLineWidth(.7)
        canvas.rect(7*mm,7*mm,page_w-14*mm,page_h-14*mm,stroke=1,fill=0)
        canvas.setFillColor(dark)
        canvas.setFont(chosen_font(store,"restaurant",True), 14)
        canvas.drawCentredString(page_w/2, page_h-20*mm, restaurant[:48])
        canvas.setFont("DejaVu", 8)
        canvas.drawCentredString(page_w/2, page_h-26*mm,
                                 (address + ("  •  " if address and phone else "") + phone)[:95])
        canvas.setStrokeColor(accent_color)
        canvas.line(left, 14*mm, page_w-right, 14*mm)
        canvas.setFont("DejaVu", 7.2)
        canvas.setFillColor(colors.HexColor("#64756B"))
        canvas.drawString(left, 10*mm, note[:100])
        canvas.drawRightString(page_w-right, 10*mm, str(doc.page))
        canvas.restoreState()

    doc = BaseDocTemplate(path, pagesize=(page_w,page_h), leftMargin=left, rightMargin=right,
                          topMargin=top, bottomMargin=bottom)
    full = Frame(left, bottom, body_width, page_h-top-bottom, leftPadding=0,
                 rightPadding=0, topPadding=0, bottomPadding=0, id="full")
    intro_h = 68*mm
    lower_h = page_h-top-bottom-intro_h-3*mm
    intro = Frame(left, bottom+lower_h+3*mm, body_width, intro_h,
                  leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0, id="intro")
    first_a = Frame(left, bottom, col_width, lower_h, leftPadding=0,
                    rightPadding=0, topPadding=0, bottomPadding=0, id="first_a")
    first_b = Frame(left+col_width+col_gap, bottom, col_width, lower_h,
                    leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0, id="first_b")
    a = Frame(left, bottom, col_width, page_h-top-bottom, leftPadding=0,
              rightPadding=0, topPadding=0, bottomPadding=0, id="col_a")
    b = Frame(left+col_width+col_gap, bottom, col_width, page_h-top-bottom,
              leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0, id="col_b")
    weekly_template = PageTemplate(id="weekly", frames=[full], onPage=decoration)
    daily_template = PageTemplate(id="daily", frames=[intro,first_a,first_b],
                                  onPage=decoration, autoNextPageTemplate="continuation")
    continuation = PageTemplate(id="continuation", frames=[a,b], onPage=decoration)
    doc.addPageTemplates(([weekly_template] if mode == "weekly" else
                          [daily_template, continuation]))
    story = []
    if mode == "weekly":
        mon = monday(target)
        fri = mon + timedelta(days=4)
        story += [Paragraph("Heti menü", title),
                  Paragraph(f"{display_date(mon)} – {display_date(fri)}", subtitle)]
        if decorated:story.append(Ornament("divider",body_width,8*mm))
        for i, label in enumerate(WEEKDAYS):
            soup, menu_a, menu_b = store.week_entry(mon+timedelta(days=i))
            if not any((soup, menu_a, menu_b)):
                continue
            rows = [[Paragraph(f"<b>{label}</b>", heading), Paragraph(escape(soup), food)]]
            if menu_a:
                rows.append([Paragraph("A menü", small), Paragraph(escape(menu_a), food)])
            if menu_b:
                rows.append([Paragraph("B menü", small), Paragraph(escape(menu_b), food)])
            block = Table(rows, colWidths=[32*mm, body_width-32*mm], hAlign="LEFT")
            block.setStyle(TableStyle([
                ("VALIGN", (0,0),(-1,-1), "TOP"), ("LEFTPADDING",(0,0),(-1,-1),0),
                ("RIGHTPADDING",(0,0),(-1,-1),5), ("TOPPADDING",(0,0),(-1,-1),4),
                ("BOTTOMPADDING",(0,0),(-1,-1),4),
                ("LINEBELOW",(0,-1),(-1,-1),0.5,line),
            ]))
            story += [KeepTogether([block, Spacer(1, 7*mm)])]
        if len(story) == 2:
            story.append(Paragraph("Erre a hétre még nincs rögzítve menü.", small))
    else:
        story += [Paragraph("Napi étlap", title), Paragraph(display_date(target), subtitle)]
        soup, menu_a, menu_b = store.week_entry(target)
        if any((soup, menu_a, menu_b)):
            rows = [[Paragraph("MAI MENÜ", heading), ""]]
            if soup:
                rows.append([Paragraph("Leves", small), Paragraph(escape(soup), food)])
            if menu_a:
                rows.append([Paragraph("A menü", small), Paragraph(escape(menu_a), food)])
            if menu_b:
                rows.append([Paragraph("B menü", small), Paragraph(escape(menu_b), food)])
            special = Table(rows, colWidths=[30*mm, body_width-30*mm])
            special.setStyle(TableStyle([
                ("BACKGROUND",(0,0),(-1,-1),colors.HexColor(palette["background"])),
                ("BOX",(0,0),(-1,-1),0.7,line), ("VALIGN",(0,0),(-1,-1),"TOP"),
                ("TOPPADDING",(0,0),(-1,-1),6), ("BOTTOMPADDING",(0,0),(-1,-1),6),
            ]))
            story += [special, Spacer(1, 6*mm)]
        if decorated:story.append(Ornament("divider",body_width,8*mm))
        chosen = store.selection(target)
        if chosen:
            # The header and daily specials span the page; the catalogue starts below, in two columns.
            story.append(FrameBreak())
            for category in CATEGORIES:
                dishes = [x for x in chosen if x["category"] == category]
                if not dishes:
                    continue
                rows = [[Paragraph(escape(x["name"]), dish_style), "",
                         Paragraph(price(x["price"]), price_style)] for x in dishes]
                table = DishTable(rows, colWidths=[col_width-34*mm,8*mm,26*mm], hAlign="LEFT")
                table.setStyle(TableStyle([
                    ("VALIGN",(0,0),(-1,-1),"TOP"),
                    ("ALIGN",(2,0),(2,-1),"RIGHT"),
                    ("LEFTPADDING",(0,0),(-1,-1),0),
                    ("RIGHTPADDING",(0,0),(-1,-1),1),
                    ("TOPPADDING",(0,0),(-1,-1),3),
                    ("BOTTOMPADDING",(0,0),(-1,-1),3),
                ]))
                story += [KeepTogether([Paragraph(escape(category), heading), table]), Spacer(1,3*mm)]
        elif not any((soup, menu_a, menu_b)):
            story.append(Paragraph("Még nincs összeállítva ez a napi étlap.", small))
    doc.build(story)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.store = Store(data_dir() / "etlapstudio.sqlite3")
        self.day = date.today()
        self.week_start = monday(self.day)
        self.edit_id = None
        self.title(APP_NAME)
        self.geometry("1130x760")
        self.minsize(900, 620)
        self.configure(bg=PAPER)
        style = ttk.Style(self)
        if "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure("TFrame", background=PAPER)
        style.configure("TLabel", background=PAPER, foreground=TEXT, font=("Segoe UI",10))
        style.configure("Title.TLabel", font=("Segoe UI",18,"bold"), foreground=DEEP)
        style.configure("Hint.TLabel", foreground="#62756A", font=("Segoe UI",9))
        style.configure("TButton", padding=(12,7), font=("Segoe UI",10))
        style.configure("Accent.TButton", foreground="white", background=GREEN)
        style.map("Accent.TButton", background=[("active",DEEP)])
        style.configure("Treeview", rowheight=28, font=("Segoe UI",10))
        style.configure("Treeview.Heading", font=("Segoe UI",10,"bold"))
        header = tk.Frame(self, bg=DEEP, height=73)
        header.pack(fill="x")
        tk.Label(header, text="ÉTLAPSTÚDIÓ", bg=DEEP, fg="white",
                 font=("Segoe UI",18,"bold")).pack(side="left", padx=25, pady=16)
        tk.Label(header, text="Napi és heti étlapok", bg=DEEP, fg="#D2E5DA",
                 font=("Segoe UI",10)).pack(side="left", padx=8)
        self.tabs = ttk.Notebook(self)
        self.tabs.pack(fill="both", expand=True, padx=18, pady=17)
        self.daily = ttk.Frame(self.tabs, padding=18)
        self.weekly = ttk.Frame(self.tabs, padding=18)
        self.catalog = ttk.Frame(self.tabs, padding=18)
        self.appearance = ttk.Frame(self.tabs, padding=18)
        self.settings_tab = ttk.Frame(self.tabs, padding=18)
        self.tabs.add(self.daily, text="  Napi étlap  ")
        self.tabs.add(self.weekly, text="  Heti menü  ")
        self.tabs.add(self.catalog, text="  Ételek és árak  ")
        self.tabs.add(self.appearance, text="  Megjelenés  ")
        self.tabs.add(self.settings_tab, text="  Étterem adatai  ")
        self.build_daily()
        self.build_weekly()
        self.build_catalog()
        self.build_appearance()
        self.build_settings()
        self.refresh_all()
        self._last_tab = 0
        self.tabs.bind("<<NotebookTabChanged>>", self.on_tab_change)
        self.protocol("WM_DELETE_WINDOW", self.close_app)

    def on_tab_change(self, _event):
        current=self.tabs.index(self.tabs.select())
        if self._last_tab==1 and current!=1:
            self.save_week(notice=False)
        self._last_tab=current

    def close_app(self):
        if self.tabs.index(self.tabs.select())==1:
            self.save_week(notice=False)
        self.store.db.close()
        self.destroy()

    def title_block(self, parent, title, hint):
        ttk.Label(parent, text=title, style="Title.TLabel").pack(anchor="w")
        ttk.Label(parent, text=hint, style="Hint.TLabel").pack(anchor="w", pady=(2,14))

    def build_daily(self):
        self.title_block(self.daily, "Napi étlap", "Válaszd ki a dátumot, majd add hozzá az aznap elérhető à la carte ételeket.")
        row = ttk.Frame(self.daily)
        row.pack(fill="x", pady=(0,12))
        ttk.Button(row, text="◀", command=lambda:self.change_day(-1)).pack(side="left")
        self.day_label = ttk.Label(row, text="", font=("Segoe UI",14,"bold"))
        self.day_label.pack(side="left", padx=18)
        ttk.Button(row, text="▶", command=lambda:self.change_day(1)).pack(side="left")
        ttk.Button(row, text="Ma", command=self.today).pack(side="left", padx=10)
        ttk.Button(row, text="PDF készítése", style="Accent.TButton",
                   command=lambda:self.export_pdf("daily")).pack(side="right")
        ttk.Button(row, text="Facebook PNG", command=lambda:self.export_png("daily")).pack(side="right",padx=8)
        self.daily_special = ttk.Label(self.daily, text="", wraplength=850, justify="left")
        self.daily_special.pack(fill="x", pady=(0,15))
        content = ttk.Frame(self.daily)
        content.pack(fill="both", expand=True)
        content.columnconfigure(0, weight=1)
        content.columnconfigure(2, weight=1)
        content.rowconfigure(2, weight=1)
        ttk.Label(content, text="Ételadatbázis").grid(row=0,column=0,sticky="w")
        ttk.Label(content, text="A napi étlapon szerepel").grid(row=0,column=2,sticky="w")
        self.daily_search = tk.StringVar()
        search = ttk.Entry(content, textvariable=self.daily_search)
        search.grid(row=1,column=0,sticky="ew",pady=(6,8))
        self.daily_search.trace_add("write", lambda *_:self.refresh_daily_available())
        ttk.Label(content,text="Válassz több ételt a Ctrl vagy Shift billentyűvel.",
                  style="Hint.TLabel").grid(row=1,column=2,sticky="w",padx=3)
        self.available = ttk.Treeview(content, columns=("category","price"), show="tree headings", selectmode="extended")
        self.available.heading("#0",text="Étel")
        self.available.heading("category",text="Kategória")
        self.available.heading("price",text="Ár")
        self.available.column("#0",width=240)
        self.available.column("category",width=140)
        self.available.column("price",width=85,anchor="e")
        self.available.grid(row=2,column=0,sticky="nsew")
        buttons=ttk.Frame(content)
        buttons.grid(row=2,column=1,padx=12)
        ttk.Button(buttons,text="Hozzáad →",command=self.add_selected).pack(pady=8)
        ttk.Button(buttons,text="← Levétel",command=self.remove_selected).pack(pady=8)
        self.chosen = ttk.Treeview(content, columns=("category","price"), show="tree headings", selectmode="extended")
        self.chosen.heading("#0",text="Étel")
        self.chosen.heading("category",text="Kategória")
        self.chosen.heading("price",text="Ár")
        self.chosen.column("#0",width=240)
        self.chosen.column("category",width=140)
        self.chosen.column("price",width=85,anchor="e")
        self.chosen.grid(row=2,column=2,sticky="nsew")

    def build_weekly(self):
        self.title_block(self.weekly, "Heti menü", "A leves és az A/B menü önálló szöveg. Az adott napi étlap tetejére is átkerül.")
        row=ttk.Frame(self.weekly); row.pack(fill="x",pady=(0,18))
        ttk.Button(row,text="◀ Előző hét",command=lambda:self.change_week(-7)).pack(side="left")
        self.week_label=ttk.Label(row,text="",font=("Segoe UI",14,"bold"))
        self.week_label.pack(side="left",padx=20)
        ttk.Button(row,text="Következő hét ▶",command=lambda:self.change_week(7)).pack(side="left")
        ttk.Button(row,text="Aktuális hét",command=self.current_week).pack(side="left",padx=10)
        ttk.Button(row,text="Heti PDF",style="Accent.TButton",command=lambda:self.export_pdf("weekly")).pack(side="right")
        ttk.Button(row,text="Facebook PNG",command=lambda:self.export_png("weekly")).pack(side="right",padx=8)
        grid=ttk.Frame(self.weekly)
        grid.pack(fill="both",expand=True)
        grid.columnconfigure(1,weight=1)
        self.week_inputs=[]
        for i,label in enumerate(WEEKDAYS):
            frame=ttk.LabelFrame(grid,text=label,padding=(14,10))
            frame.grid(row=i,column=1,sticky="ew",pady=5)
            frame.columnconfigure(1,weight=1)
            vars=[]
            for j,field in enumerate(("Leves","A menü","B menü")):
                ttk.Label(frame,text=field,width=10).grid(row=j,column=0,sticky="w",pady=3)
                var=tk.StringVar()
                ttk.Entry(frame,textvariable=var).grid(row=j,column=1,sticky="ew",pady=3)
                vars.append(var)
            self.week_inputs.append(vars)
        ttk.Button(self.weekly,text="Heti menü mentése",style="Accent.TButton",
                   command=self.save_week).pack(anchor="e",pady=(14,0))

    def build_catalog(self):
        self.title_block(self.catalog, "Ételek és árak", "Ez az à la carte kínálat adatbázisa. Kezdetben üres.")
        upper=ttk.Frame(self.catalog); upper.pack(fill="x",pady=(0,12))
        self.food_search=tk.StringVar()
        ttk.Entry(upper,textvariable=self.food_search,width=40).pack(side="left")
        self.food_search.trace_add("write",lambda *_:self.refresh_catalog())
        ttk.Label(upper,text="  Keresés név vagy kategória szerint",style="Hint.TLabel").pack(side="left")
        columns=("category","price")
        self.food_tree=ttk.Treeview(self.catalog,columns=columns,show="tree headings",selectmode="browse")
        self.food_tree.heading("#0",text="Étel neve")
        self.food_tree.heading("category",text="Kategória")
        self.food_tree.heading("price",text="Ár")
        self.food_tree.column("#0",width=440)
        self.food_tree.column("category",width=250)
        self.food_tree.column("price",width=130,anchor="e")
        self.food_tree.pack(fill="both",expand=True)
        self.food_tree.bind("<Double-1>",lambda _:self.edit_food())
        row=ttk.Frame(self.catalog);row.pack(fill="x",pady=(13,0))
        ttk.Button(row,text="Új étel",style="Accent.TButton",command=self.new_food).pack(side="left")
        ttk.Button(row,text="Szerkesztés",command=self.edit_food).pack(side="left",padx=8)
        ttk.Button(row,text="Törlés",command=self.delete_food).pack(side="left")

    def build_settings(self):
        self.title_block(self.settings_tab,"Étterem adatai","Ezek az adatok mindkét nyomtatható étlapon szerepelnek.")
        self.setting_vars={}
        for key,label,default in [
            ("restaurant","Étterem neve",""),
            ("address","Cím",""),
            ("phone","Telefonszám",""),
            ("note","Alsó megjegyzés",""),
        ]:
            ttk.Label(self.settings_tab,text=label).pack(anchor="w",pady=(12,4))
            var=tk.StringVar(value=self.store.setting(key,default))
            ttk.Entry(self.settings_tab,textvariable=var,width=80).pack(anchor="w",fill="x")
            self.setting_vars[key]=var
        ttk.Button(self.settings_tab,text="Adatok mentése",style="Accent.TButton",
                   command=self.save_settings).pack(anchor="w",pady=18)
        ttk.Label(self.settings_tab,text="Az adatbázis helye: "+str(self.store.path),
                  style="Hint.TLabel",wraplength=850).pack(anchor="w",pady=8)
        ttk.Button(self.settings_tab,text="Adatbázis biztonsági másolata…",
                   command=self.backup).pack(anchor="w",pady=4)

    def build_appearance(self):
        self.title_block(self.appearance,"Megjelenés és témák",
                         "Állítsd be a betűket és a grafikai hátteret, vagy importálj új témacsomagot.")
        self.theme_packs={}
        self.theme_display={}
        row=ttk.Frame(self.appearance);row.pack(fill="x",pady=(4,14))
        ttk.Label(row,text="Téma:").pack(side="left")
        self.theme_choice=tk.StringVar()
        self.theme_combo=ttk.Combobox(row,textvariable=self.theme_choice,state="readonly",width=28)
        self.theme_combo.pack(side="left",padx=10)
        self.theme_combo.bind("<<ComboboxSelected>>",lambda _:self.select_theme())
        ttk.Button(row,text="Témacsomag importálása…",command=self.import_theme_file).pack(side="left",padx=8)
        self.primary_var=tk.StringVar(value=self.store.setting("theme_primary"))
        self.accent_var=tk.StringVar(value=self.store.setting("theme_accent"))
        palette_row=ttk.Frame(self.appearance);palette_row.pack(fill="x",pady=(0,13))
        ttk.Button(palette_row,text="Alapszín választása",command=lambda:self.pick_color("primary")).pack(side="left")
        ttk.Button(palette_row,text="Kiegészítő szín",command=lambda:self.pick_color("accent")).pack(side="left",padx=10)
        ttk.Button(palette_row,text="Téma eredeti színei",command=self.reset_colors).pack(side="left")
        self.deco_var=tk.BooleanVar(value=self.store.setting("decorations","1")=="1")
        ttk.Checkbutton(self.appearance,text="Grafikai díszek és elválasztók megjelenítése",
                        variable=self.deco_var,command=self.save_appearance).pack(anchor="w",pady=(0,5))
        ttk.Label(self.appearance,text="Betűtípusok",style="Title.TLabel").pack(anchor="w",pady=(3,3))
        font_row=ttk.Frame(self.appearance);font_row.pack(fill="x")
        self.font_vars={}
        for role,label in [("restaurant","Étterem neve"),("title","Főcím"),
                           ("heading","Alcímek"),("special","Heti / A-B menü"),
                           ("dish","Ételek és árak")]:
            box=ttk.Frame(font_row);box.pack(side="left",padx=(0,12))
            ttk.Label(box,text=label).pack(anchor="w")
            var=tk.StringVar(value=self.store.setting("font_"+role,"Modern sans"))
            combo=ttk.Combobox(box,textvariable=var,values=list(FONT_OPTIONS),state="readonly",width=17)
            combo.pack(anchor="w");combo.bind("<<ComboboxSelected>>",lambda _:self.save_appearance())
            self.font_vars[role]=var
        leader_row=ttk.Frame(self.appearance);leader_row.pack(fill="x",pady=(8,5))
        ttk.Label(leader_row,text="Étel és ár között:").pack(side="left")
        current=next((name for name,key in LEADERS.items() if key==self.store.setting("leader","none")),"Nincs")
        self.leader_var=tk.StringVar(value=current)
        leader_combo=ttk.Combobox(leader_row,textvariable=self.leader_var,values=list(LEADERS),state="readonly",width=19)
        leader_combo.pack(side="left",padx=9)
        leader_combo.bind("<<ComboboxSelected>>",lambda _:self.save_appearance())
        bg_row=ttk.Frame(self.appearance);bg_row.pack(fill="x",pady=(4,5))
        self.bg_enabled=tk.BooleanVar(value=self.store.setting("background_enabled","0")=="1")
        ttk.Checkbutton(bg_row,text="Háttérgrafika",variable=self.bg_enabled,
                        command=self.save_appearance).pack(side="left")
        ttk.Button(bg_row,text="Botanikus minta",command=self.use_sample_background).pack(side="left",padx=8)
        ttk.Button(bg_row,text="PNG/JPG importálása…",command=self.import_background).pack(side="left")
        ttk.Button(bg_row,text="Eltávolítás",command=self.clear_background).pack(side="left",padx=8)
        ttk.Label(bg_row,text="Erősség:").pack(side="left",padx=(13,3))
        self.bg_opacity=tk.IntVar(value=int(self.store.setting("background_opacity","30")))
        ttk.Scale(bg_row,from_=0,to=100,variable=self.bg_opacity,orient="horizontal",
                  length=110,command=lambda _value:self.save_appearance()).pack(side="left")
        ttk.Label(self.appearance,text="AI háttér készítéséhez: GRAPHICS_PROMPT.md → PNG háttér; a kapott fájlt itt importálhatod.",
                  style="Hint.TLabel").pack(anchor="w",pady=(0,5))
        ttk.Label(self.appearance,text="Téma előnézete",style="Title.TLabel").pack(anchor="w",pady=(6,8))
        self.theme_preview=tk.Canvas(self.appearance,height=170,bg="white",highlightthickness=0)
        self.theme_preview.pack(fill="x",pady=(0,12))
        self.theme_preview.bind("<Configure>",lambda _:self.draw_theme_preview())
        ttk.Label(self.appearance,text="Díszítő témacsomag: ZIP manifest.json és SVG elemekkel; háttér: külön PNG vagy JPG.",
                  style="Hint.TLabel",wraplength=900).pack(anchor="w")
        self.reload_themes()

    def reload_themes(self):
        self.theme_packs=load_themes(Path(__file__).resolve().parent/"themes_builtin",data_dir()/"themes")
        self.theme_display={m["name"]+"  ["+key+"]":key for key,(m,_) in self.theme_packs.items()}
        self.theme_combo["values"]=list(self.theme_display)
        chosen=self.store.setting("theme","classic")
        for label,key in self.theme_display.items():
            if key==chosen:self.theme_choice.set(label);break
        else:self.theme_choice.set(next(iter(self.theme_display)))
        self.draw_theme_preview()

    def current_theme(self):
        key=self.theme_display.get(self.theme_choice.get(),"classic")
        return key,self.theme_packs[key]

    def select_theme(self):
        self.primary_var.set("");self.accent_var.set("")
        self.save_appearance()

    def pick_color(self,kind):
        _key,(manifest,_folder)=self.current_theme()
        current=(self.primary_var if kind=="primary" else self.accent_var).get() or manifest["palette"][kind]
        result=colorchooser.askcolor(color=current,parent=self)
        if result and result[1]:
            (self.primary_var if kind=="primary" else self.accent_var).set(result[1].upper())
            self.save_appearance()

    def reset_colors(self):
        self.primary_var.set("");self.accent_var.set("")
        self.save_appearance()

    def save_appearance(self):
        key,_pack=self.current_theme()
        self.store.set_settings({"theme":key,"theme_primary":self.primary_var.get(),
                                 "theme_accent":self.accent_var.get(),
                                 "decorations":"1" if self.deco_var.get() else "0",
                                 "leader":LEADERS[self.leader_var.get()],
                                 "background_enabled":"1" if self.bg_enabled.get() else "0",
                                 "background_opacity":str(round(self.bg_opacity.get())),
                                 **{"font_"+role:var.get() for role,var in self.font_vars.items()}})
        self.draw_theme_preview()

    def draw_theme_preview(self):
        if not hasattr(self,"theme_preview") or not self.theme_packs:return
        key,(manifest,folder)=self.current_theme()
        palette=manifest["palette"]
        primary=self.primary_var.get() or palette["primary"]
        accent=self.accent_var.get() or palette["accent"]
        width=max(self.theme_preview.winfo_width(),600)
        c=self.theme_preview;c.delete("all")
        c.create_rectangle(12,8,width-12,162,fill="white",outline=primary,width=2)
        if self.bg_enabled.get() and background_path(self.store):
            try:
                from PIL import Image
                with Image.open(background_path(self.store)) as source:
                    bg=source.convert("RGBA").resize((min(width-28,800),154))
                bg.putalpha(bg.getchannel("A").point(lambda a:int(a*self.bg_opacity.get()/100)))
                stream=io.BytesIO();bg.save(stream,format="PNG")
                self._background_preview=tk.PhotoImage(data=base64.b64encode(stream.getvalue()).decode())
                c.create_image(width/2,85,image=self._background_preview)
            except Exception:pass
        c.create_text(width/2,59,text=self.store.setting("restaurant") or "AZ ÉTTEREM NEVE",
                      font=("Georgia",18,"bold"),fill=primary)
        c.create_text(width/2,85,text="Heti menü  ·  Napi étlap",
                      font=("Georgia",15,"bold"),fill="#263A30")
        c.create_rectangle(65,106,width-65,132,fill=palette["background"],outline="")
        c.create_text(width/2,119,text="Leves  •  A menü  •  B menü",font=("Segoe UI",11),fill=primary)
        c.create_line(100,141,width-100,141,fill=accent,width=2)
        c.create_text(width/2,152,text=manifest["name"]+" téma",font=("Segoe UI",9),fill=accent)
        if self.deco_var.get():
            try:
                import fitz
                svg=(folder/"header.svg").read_text(encoding="utf-8")
                svg=svg.replace(palette["primary"],primary).replace(palette["accent"],accent)
                document=fitz.open(stream=svg.encode("utf-8"),filetype="svg")
                pix=document[0].get_pixmap(matrix=fitz.Matrix(.55,.55),alpha=True)
                self._preview_image=tk.PhotoImage(data=base64.b64encode(pix.tobytes("png")).decode())
                c.create_image(width/2,18,image=self._preview_image)
                document.close()
            except Exception:
                pass

    def import_theme_file(self):
        filename=filedialog.askopenfilename(parent=self,title="SVG témacsomag importálása",
                                            filetypes=[("Témacsomag ZIP","*.zip")])
        if not filename:return
        try:
            slug=import_theme(Path(filename),data_dir()/"themes",set(self.theme_packs))
            self.store.set_settings({"theme":slug,"theme_primary":"","theme_accent":""})
            self.primary_var.set("");self.accent_var.set("")
            self.reload_themes()
            messagebox.showinfo(APP_NAME,"A téma importálva, és kiválasztva.",parent=self)
        except Exception as exc:
            messagebox.showerror(APP_NAME,"A téma nem importálható:\n"+str(exc),parent=self)

    def use_sample_background(self):
        self.store.set_settings({"background_builtin":"1","background_file":""})
        self.bg_enabled.set(True);self.save_appearance()

    def clear_background(self):
        self.bg_enabled.set(False)
        self.store.set_settings({"background_builtin":"0","background_file":""})
        self.save_appearance()

    def import_background(self):
        filename=filedialog.askopenfilename(parent=self,title="Háttérgrafika importálása",
                                            filetypes=[("PNG vagy JPEG","*.png *.jpg *.jpeg")])
        if not filename:return
        try:
            from PIL import Image
            source=Path(filename)
            if source.stat().st_size>20_000_000:raise ValueError("A kép legfeljebb 20 MB lehet.")
            with Image.open(source) as image:
                if image.format not in ("PNG","JPEG") or image.width<800 or image.height<1000:
                    raise ValueError("PNG/JPEG képet válassz, legalább 800 × 1000 képponttal.")
                if image.width*image.height>36_000_000:
                    raise ValueError("A kép legfeljebb 36 megapixeles lehet.")
                image.load()
                suffix=".png" if image.format=="PNG" else ".jpg"
            folder=data_dir()/"backgrounds";folder.mkdir(exist_ok=True)
            import hashlib
            name=hashlib.sha256(source.read_bytes()).hexdigest()[:20]+suffix
            shutil.copyfile(source,folder/name)
            self.store.set_settings({"background_file":name,"background_builtin":"0"})
            self.bg_enabled.set(True);self.save_appearance()
        except Exception as exc:
            messagebox.showerror(APP_NAME,"A háttér nem importálható:\n"+str(exc),parent=self)

    def refresh_all(self):
        self.refresh_week()
        self.refresh_daily()
        self.refresh_catalog()

    def refresh_daily(self):
        self.day_label.config(text=display_date(self.day))
        soup,a,b=self.store.week_entry(self.day)
        special="  ·  ".join(f"{label}: {value}" for label,value in
                            (("Leves",soup),("A menü",a),("B menü",b)) if value)
        self.daily_special.config(text="Mai menü: "+(special or "még nincs megadva a Heti menü fülön"))
        for item in self.chosen.get_children(): self.chosen.delete(item)
        for row in self.store.selection(self.day):
            self.chosen.insert("", "end", iid=str(row["id"]),text=row["name"],
                               values=(row["category"],price(row["price"])))
        self.refresh_daily_available()

    def refresh_daily_available(self):
        if not hasattr(self,"available"): return
        chosen={int(row["id"]) for row in self.store.selection(self.day)}
        for item in self.available.get_children(): self.available.delete(item)
        for row in self.store.dishes(self.daily_search.get()):
            if row["id"] not in chosen:
                self.available.insert("","end",iid=str(row["id"]),text=row["name"],
                                      values=(row["category"],price(row["price"])))

    def add_selected(self):
        selected={int(x) for x in self.chosen.get_children()}
        selected.update(int(x) for x in self.available.selection())
        self.store.set_selected(self.day,sorted(selected)); self.refresh_daily()

    def remove_selected(self):
        removing={int(x) for x in self.chosen.selection()}
        keep=[int(x) for x in self.chosen.get_children() if int(x) not in removing]
        self.store.set_selected(self.day,keep);self.refresh_daily()

    def change_day(self,offset):
        self.day+=timedelta(days=offset);self.refresh_daily()

    def today(self):
        self.day=date.today();self.refresh_daily()

    def refresh_week(self):
        end=self.week_start+timedelta(days=4)
        self.week_label.config(text=f"{display_date(self.week_start)} – {display_date(end)}")
        for i,group in enumerate(self.week_inputs):
            entry=self.store.week_entry(self.week_start+timedelta(days=i))
            for var,value in zip(group,entry):var.set(value)

    def change_week(self,days):
        self.save_week(notice=False)
        self.week_start+=timedelta(days=days);self.refresh_week()

    def current_week(self):
        self.save_week(notice=False)
        self.week_start=monday(date.today());self.refresh_week()

    def save_week(self,notice=True):
        for i,group in enumerate(self.week_inputs):
            self.store.set_week_entry(self.week_start+timedelta(days=i),
                                      *(var.get() for var in group))
        self.refresh_daily()
        if notice: messagebox.showinfo(APP_NAME,"A heti menü mentve.",parent=self)

    def refresh_catalog(self):
        for item in self.food_tree.get_children():self.food_tree.delete(item)
        for row in self.store.dishes(self.food_search.get()):
            self.food_tree.insert("","end",iid=str(row["id"]),text=row["name"],
                                  values=(row["category"],price(row["price"])))

    def new_food(self): self.food_dialog()

    def edit_food(self):
        selection=self.food_tree.selection()
        if not selection:return
        row=self.store.db.execute("SELECT * FROM dishes WHERE id=?",(int(selection[0]),)).fetchone()
        self.food_dialog(row)

    def food_dialog(self,row=None):
        dialog=tk.Toplevel(self);dialog.title("Étel szerkesztése" if row else "Új étel")
        dialog.geometry("440x290");dialog.resizable(False,False);dialog.transient(self);dialog.grab_set()
        panel=ttk.Frame(dialog,padding=20);panel.pack(fill="both",expand=True)
        name=tk.StringVar(value=row["name"] if row else "")
        cat=tk.StringVar(value=row["category"] if row else CATEGORIES[0])
        amount=tk.StringVar(value=str(row["price"]) if row else "")
        for label,var in (("Étel neve",name),("Ár (Ft)",amount)):
            ttk.Label(panel,text=label).pack(anchor="w",pady=(4,2))
            entry=ttk.Entry(panel,textvariable=var)
            entry.pack(fill="x",pady=(0,6))
            if label=="Étel neve":entry.focus_set()
        ttk.Label(panel,text="Kategória").pack(anchor="w",pady=(4,2))
        ttk.Combobox(panel,textvariable=cat,values=CATEGORIES,state="readonly").pack(fill="x")
        def save():
            try:
                if not name.get().strip():raise ValueError("Add meg az étel nevét.")
                value=int(amount.get().replace(" ",""))
                if value<0:raise ValueError("Az ár nem lehet negatív.")
            except ValueError as exc:
                messagebox.showerror(APP_NAME,str(exc) if str(exc) and not str(exc).startswith("invalid")
                                     else "Az ár egész szám legyen.",parent=dialog);return
            self.store.add_dish(name.get().strip(),cat.get(),value,row["id"] if row else None)
            self.refresh_catalog();self.refresh_daily();dialog.destroy()
        ttk.Button(panel,text="Mentés",style="Accent.TButton",command=save).pack(anchor="e",pady=14)
        dialog.bind("<Return>",lambda _:save())

    def delete_food(self):
        selection=self.food_tree.selection()
        if not selection:return
        name=self.food_tree.item(selection[0],"text")
        if not messagebox.askyesno(APP_NAME,f"Töröljük az ételt az adatbázisból?\n\n{name}",parent=self):return
        self.store.delete_dish(int(selection[0]));self.refresh_catalog();self.refresh_daily()

    def save_settings(self):
        self.store.set_settings({key:var.get().strip() for key,var in self.setting_vars.items()})
        messagebox.showinfo(APP_NAME,"Az étterem adatai mentve.",parent=self)

    def backup(self):
        target=filedialog.asksaveasfilename(parent=self,defaultextension=".sqlite3",
                                             initialfile="etlapstudio-mentes.sqlite3",
                                             filetypes=[("SQLite adatbázis","*.sqlite3")])
        if not target:return
        try:
            with sqlite3.connect(target) as destination:self.store.db.backup(destination)
            messagebox.showinfo(APP_NAME,"A biztonsági másolat elkészült.",parent=self)
        except Exception as exc:messagebox.showerror(APP_NAME,str(exc),parent=self)

    def export_pdf(self,mode):
        if mode=="weekly":self.save_week(notice=False)
        self.store.set_settings({key:var.get().strip() for key,var in self.setting_vars.items()})
        target=self.week_start if mode=="weekly" else self.day
        stem=("heti_menu_" if mode=="weekly" else "napi_etlap_")+target.isoformat()
        path=filedialog.asksaveasfilename(parent=self,defaultextension=".pdf",initialfile=stem+".pdf",
                                           filetypes=[("PDF dokumentum","*.pdf")])
        if not path:return
        try:
            make_pdf(path,self.store,mode,target)
            messagebox.showinfo(APP_NAME,"A PDF elkészült.\n"+path,parent=self)
            if sys.platform=="win32":os.startfile(path)
            elif sys.platform=="darwin":os.system("open "+repr(path))
        except ImportError:
            messagebox.showerror(APP_NAME,"Hiányzik a reportlab csomag. Indítsd az appot a Windows indítóval, vagy telepítsd: pip install reportlab",parent=self)
        except Exception as exc:messagebox.showerror(APP_NAME,"A PDF készítése sikertelen:\n"+str(exc),parent=self)

    def export_png(self,mode):
        if mode=="weekly":self.save_week(notice=False)
        self.store.set_settings({key:var.get().strip() for key,var in self.setting_vars.items()})
        target=self.week_start if mode=="weekly" else self.day
        stem=("heti_menu_" if mode=="weekly" else "napi_etlap_")+target.isoformat()
        destination=filedialog.asksaveasfilename(parent=self,defaultextension=".png",
                                                 initialfile=stem+".png",
                                                 filetypes=[("PNG kép","*.png")])
        if not destination:return
        try:
            import fitz
            with tempfile.TemporaryDirectory() as temp:
                pdf_path=str(Path(temp)/"social.pdf")
                make_pdf(pdf_path,self.store,mode,target,social=True)
                document=fitz.open(pdf_path)
                base=Path(destination)
                outputs=[]
                for index,page in enumerate(document):
                    matrix=fitz.Matrix(1440/page.rect.width,1800/page.rect.height)
                    pix=page.get_pixmap(matrix=matrix,alpha=False,colorspace=fitz.csRGB)
                    output=base if len(document)==1 else base.with_name(f"{base.stem}_{index+1:02d}.png")
                    pix.save(str(output));outputs.append(str(output))
                document.close()
            messagebox.showinfo(APP_NAME,
                f"{len(outputs)} Facebook-kép elkészült (1440 × 1800 px).\n"+
                (outputs[0] if len(outputs)==1 else str(Path(outputs[0]).parent)),parent=self)
        except ImportError:
            messagebox.showerror(APP_NAME,"Hiányzik a PyMuPDF csomag. Indítsd az appot a Windows indítóval.",parent=self)
        except Exception as exc:
            messagebox.showerror(APP_NAME,"A PNG készítése sikertelen:\n"+str(exc),parent=self)


if __name__=="__main__":
    App().mainloop()
