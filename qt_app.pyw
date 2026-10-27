"""ÉtlapStúdió Qt6 desktop editor with persistent split preview."""
from __future__ import annotations
import sqlite3
import json
import csv
import sys
import os
import re
import shutil
import subprocess
import tempfile
import time
from urllib.request import Request, urlopen
from datetime import date, timedelta
from pathlib import Path
from PyQt6.QtCore import QDate, QTimer, Qt, QEvent, QPropertyAnimation, QEasingCurve, QSize, QPoint
from PyQt6.QtGui import QAction, QColor, QFont, QIcon, QIntValidator, QPainter, QPen, QPixmap, QPalette, QTextCharFormat
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QCompleter, QDateEdit, QDialog,
    QDialogButtonBox, QFileDialog, QFontComboBox, QFormLayout, QFrame,
    QGridLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget, QMenu,
    QListWidgetItem, QMainWindow, QMessageBox, QPushButton, QScrollArea,
    QSplitter, QSizePolicy, QStackedWidget, QTabBar, QTabWidget, QTreeWidget, QTreeWidgetItem, QTextEdit, QColorDialog,
    QVBoxLayout, QWidget, QDoubleSpinBox, QGraphicsDropShadowEffect, QSpinBox, QSlider, QSplashScreen,
)
from menu_core import (APP_NAME, ArchivedMenu, CATEGORIES, WEEKDAYS, Store,
                       data_dir, default_daily_section_columns, display_date, insert_pending_dishes, monday, price)
from menu_render import A4_WIDTH_PT, EXPORT_HEIGHT, EXPORT_WIDTH, H, W, asset_file, export_pdf, export_png, render_image
from themes import load_themes, import_theme, import_theme_images
from version import APP_VERSION

BASE=Path(__file__).resolve().parent
GITHUB_LATEST_RELEASE="https://api.github.com/repos/szokezoltan95/etlapstudio/releases/latest"
TEXT_STYLES=[
    ("header_title","Étterem neve · fejléc-adatmező","Segoe UI",11,"title"),
    ("header_date","Dátum a napi / heti panelben","Segoe UI",16,"special"),
    ("header_contact","Cím, telefonszám és Facebook link","Segoe UI",11,"special"),
    ("daily_title","Napi / heti étlap címsora","Candara",22,"heading"),
    ("daily_label","Napi menü sorcímkéi · Leves / A / B","Segoe UI",13,"heading"),
    ("daily_value","Napi menü ételnevei","Segoe UI",13,"special"),
    ("menu_price_label","Napi menü árának címkéje","Segoe UI",12,"special"),
    ("menu_price_value","Napi menü ára","Candara",20,"title"),
    ("category_title","À la carte kategóriacímek","Candara",14,"heading"),
    ("dish_name","À la carte ételnevek · maximális méret","Segoe UI",14.5,"dish"),
    ("dish_price","À la carte normál árak","Segoe UI",12.5,"dish"),
    ("promo_old_price","Akciós étel régi ára","Segoe UI",7,"dish"),
    ("promo_new_price","Akciós étel új ára","Segoe UI",12.5,"dish"),
    ("promo_badge","AKCIÓ jelzés","Segoe UI",6,"dish"),
    ("weekday_title","Heti menü napnevei","Candara",16,"heading"),
    ("weekly_label","Heti menü sorcímkéi · Leves / A / B","Segoe UI",15,"heading"),
    ("weekly_value","Heti menü ételnevei","Segoe UI",15,"special"),
    ("footer_note","Alsó megjegyzés","Segoe UI",10,"special"),
]
MIT_LICENSE_TEXT='''MIT License

Copyright (c) 2026 Szőke Zoltán

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.'''
LEADERS={"Nincs":"none","Pontozott":"dots","Szaggatott":"dashes","Folytonos vonal":"line"}


def qdate(value):return QDate(value.year,value.month,value.day)
def pydate(value):return date(value.year(),value.month(),value.day())


def app_asset(name):
    candidates=[BASE/"design_assets"/name,
                Path(getattr(sys,"_MEIPASS",BASE))/"design_assets"/name,
                Path(sys.executable).resolve().parent/"design_assets"/name]
    return next((path for path in candidates if path.is_file()),candidates[0])


def button(label,callback):
    b=QPushButton(label);b.clicked.connect(callback);return b


def two_way_arrow_icon():
    pixmap=QPixmap(20,16);pixmap.fill(Qt.GlobalColor.transparent)
    painter=QPainter(pixmap);painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor("#34483d"),2,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap,Qt.PenJoinStyle.RoundJoin))
    painter.drawLine(3,8,17,8)
    painter.drawLine(3,8,7,4);painter.drawLine(3,8,7,12)
    painter.drawLine(17,8,13,4);painter.drawLine(17,8,13,12)
    painter.end()
    return QIcon(pixmap)


class OrderRow(QFrame):
    """Whole flat order row responds to hover and fades its recent-move tint."""
    def __init__(self,recent=False):
        super().__init__();self.setObjectName("orderRow");self.recent=recent;self.hovered=False
        self._recent_opacity=1.0 if recent else 0.0;self._fade_started=None
        self._fade_delay=QTimer(self);self._fade_delay.setSingleShot(True);self._fade_delay.setInterval(1000)
        self._fade_delay.timeout.connect(self.start_recent_fade)
        self._fade_timer=QTimer(self);self._fade_timer.setInterval(30);self._fade_timer.timeout.connect(self.update_recent_fade)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover,True);self.setMouseTracking(True);self.apply_style()
        if recent:self._fade_delay.start()

    @staticmethod
    def blend_color(start,end,amount):
        first,second=QColor(start),QColor(end)
        return QColor(round(first.red()*(1-amount)+second.red()*amount),
                      round(first.green()*(1-amount)+second.green()*amount),
                      round(first.blue()*(1-amount)+second.blue()*amount)).name()

    def apply_style(self):
        if self.recent:
            normal_background,normal_border=("#f0f6f1","#83a88c") if self.hovered else ("#ffffff","#e2d9ce")
            gold_background="#ffedb8" if self.hovered else "#fff4d6"
            background=self.blend_color(gold_background,normal_background,1-self._recent_opacity)
            border=self.blend_color("#c9a347",normal_border,1-self._recent_opacity)
        elif self.hovered:background,border="#f0f6f1","#83a88c"
        else:background,border="#ffffff","#e2d9ce"
        self.setStyleSheet(f"QFrame#orderRow {{ background:{background}; border:1px solid {border}; border-radius:5px; }}")

    def start_recent_fade(self):
        if not self.recent:return
        self._fade_started=time.monotonic();self._fade_timer.start()

    def update_recent_fade(self):
        if self._fade_started is None:return
        progress=min(1.0,(time.monotonic()-self._fade_started)/0.45)
        self._recent_opacity=1.0-progress
        if progress>=1.0:
            self.recent=False;self._fade_timer.stop()
        self.apply_style()

    def enterEvent(self,event):
        self.hovered=True;self.apply_style();super().enterEvent(event)

    def leaveEvent(self,event):
        self.hovered=False;self.apply_style();super().leaveEvent(event)


def price_edit(value=0):
    edit=QLineEdit(str(value));edit.setValidator(QIntValidator(0,1_000_000,edit))
    edit.setPlaceholderText("Ár forintban");edit.setClearButtonEnabled(True)
    return edit


class DishDialog(QDialog):
    def __init__(self,parent,row=None,initial_name="",initial_category=None):
        super().__init__(parent);self.setWindowTitle("Étel szerkesztése" if row else "Új étel")
        layout=QVBoxLayout(self);form=QFormLayout();layout.addLayout(form)
        self.name=QLineEdit(row["name"] if row else initial_name);form.addRow("Étel neve",self.name)
        self.category=QComboBox();self.category.addItems(CATEGORIES)
        if row:self.category.setCurrentText(row["category"])
        elif initial_category in CATEGORIES:self.category.setCurrentText(initial_category)
        form.addRow("Étel kategóriája",self.category)
        self.amount=price_edit(row["price"] if row else 0);form.addRow("Ár (Ft)",self.amount)
        self.amount_label=QLabel("A Menü kategóriában a 0 Ft azt jelenti, hogy nincs külön feltüntetett ár.")
        self.amount_label.setWordWrap(True);layout.addWidget(self.amount_label)
        hint=QLabel("A napi akciós árat a Napi étlap fülön, az adott dátumhoz állíthatod be.")
        hint.setWordWrap(True);layout.addWidget(hint)
        controls=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        controls.accepted.connect(self.validate_accept);controls.rejected.connect(self.reject);layout.addWidget(controls)
        self.setMinimumWidth(440)

    def validate_accept(self):
        if not self.name.text().strip():
            QMessageBox.warning(self,APP_NAME,"Add meg az étel nevét.");return
        try:int(self.amount.text())
        except ValueError:
            QMessageBox.warning(self,APP_NAME,"Az ár mezőbe számot írj.");return
        self.accept()


class PromotionDialog(QDialog):
    def __init__(self,parent,dish):
        super().__init__(parent);self.setWindowTitle("Napi akció · "+dish["name"])
        self.parent_dish_price=dish["price"]
        layout=QVBoxLayout(self);layout.addWidget(QLabel("Normál ár: "+price(dish["price"])))
        self.enabled=QCheckBox("Akciós ár alkalmazása ezen a napon")
        self.enabled.setChecked(bool(dish["promo_enabled"]));layout.addWidget(self.enabled)
        self.amount=price_edit(dish["promo_price"] or 0);self.amount.setEnabled(self.enabled.isChecked())
        self.enabled.toggled.connect(self.amount.setEnabled)
        row=QFormLayout();row.addRow("Akciós ár",self.amount);layout.addLayout(row)
        layout.addWidget(QLabel("A kedvezmény csak a kiválasztott napi étlapon jelenik meg."))
        controls=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        controls.accepted.connect(self.validate_accept);controls.rejected.connect(self.reject);layout.addWidget(controls)

    def validate_accept(self):
        if self.enabled.isChecked():
            try:amount=int(self.amount.text())
            except ValueError:
                QMessageBox.warning(self,APP_NAME,"Írd be az akciós árat számjegyekkel.");return
            if not 0<=amount<self.parent_dish_price:
                QMessageBox.warning(self,APP_NAME,"Az akciós ár legyen kisebb a normál árnál.");return
        self.accept()


class SectionDishOrderDialog(QDialog):
    """Arrow-only dish ordering for one section; changes stay in the parent dialog."""
    def __init__(self,parent,category,dishes,initial_order):
        super().__init__(parent);self.setWindowTitle(f"{category} · ételsorrend")
        self.resize(540,600);self.category=category;self.last_moved_id=None
        by_id={str(dish["id"]):dish for dish in dishes}
        requested=[str(value) for value in initial_order]
        self.items=[by_id.pop(key) for key in requested if key in by_id]
        self.items.extend(sorted(by_id.values(),key=lambda dish:str(dish["name"]).casefold()))
        layout=QVBoxLayout(self)
        hint=QLabel("Az ételek sorrendjét a sorok melletti nyilakkal állíthatod be.")
        hint.setWordWrap(True);layout.addWidget(hint)
        self.scroll=QScrollArea();self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.rows=QWidget();self.rows_layout=QVBoxLayout(self.rows);self.rows_layout.setContentsMargins(4,4,8,4);self.rows_layout.setSpacing(4)
        self.scroll.setWidget(self.rows);layout.addWidget(self.scroll,1);self.rebuild_rows()
        controls=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel)
        controls.accepted.connect(self.accept);controls.rejected.connect(self.reject);layout.addWidget(controls)

    def rebuild_rows(self):
        while self.rows_layout.count():
            item=self.rows_layout.takeAt(0);widget=item.widget()
            if widget:widget.deleteLater()
        for index,dish in enumerate(self.items):
            row=OrderRow(recent=str(dish["id"])==str(self.last_moved_id))
            line=QHBoxLayout(row);line.setContentsMargins(10,3,5,3)
            label=QLabel(str(dish["name"]));label.setMinimumWidth(0);line.addWidget(label,1)
            up=QPushButton("↑");down=QPushButton("↓")
            for control in (up,down):
                control.setFixedSize(34,30);control.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            up.setEnabled(index>0);down.setEnabled(index<len(self.items)-1)
            up.clicked.connect(lambda _=False,i=index:self.move_item(i,-1))
            down.clicked.connect(lambda _=False,i=index:self.move_item(i,1))
            line.addWidget(up);line.addWidget(down);self.rows_layout.addWidget(row)
        self.rows_layout.addStretch(1)

    def move_item(self,index,direction):
        target=index+direction
        if not 0<=target<len(self.items):return
        self.items[index],self.items[target]=self.items[target],self.items[index]
        self.last_moved_id=self.items[target]["id"]
        self.rebuild_rows()

    def ordered_ids(self):return [dish["id"] for dish in self.items]


class SectionOrderDialog(QDialog):
    def __init__(self,parent,categories,order,layout_by_column,dishes,dish_order):
        super().__init__(parent);self.setWindowTitle("Napi étlap · szekciók rendezése")
        self.setMinimumSize(850,560);self.resize(1050,650)
        layout=QVBoxLayout(self)
        hint=QLabel("A szekciókat a fel/le nyilakkal rendezheted. Az „Ételek rendezése…” külön ablakban nyitja meg az adott szekció ételsorrendjét.")
        hint.setWordWrap(True);layout.addWidget(hint)
        ordered=[category for category in order if category in categories]
        ordered += [category for category in categories if category not in ordered]
        self.section_columns={1:[],2:[]};assigned=set();legacy_third=[]
        if isinstance(layout_by_column,dict):
            for column in (1,2,3):
                values=layout_by_column.get(str(column),layout_by_column.get(column,[]))
                if isinstance(values,list):
                    for category in values:
                        if category in categories and category not in assigned:
                            (legacy_third if column==3 else self.section_columns[column]).append(category);assigned.add(category)
        if not assigned:self.section_columns=default_daily_section_columns(categories,dishes)
        else:
            for category in ordered:
                if category not in assigned:self.section_columns[1].append(category)
            for category in legacy_third:
                target=1 if len(self.section_columns[1])<=len(self.section_columns[2]) else 2
                self.section_columns[target].append(category)
        self.dishes_by_category={category:[] for category in categories}
        for dish in dishes:
            if dish["category"] in self.dishes_by_category:self.dishes_by_category[dish["category"]].append(dish)
        self.dish_order={category:list(dish_order.get(category,[])) for category in categories} if isinstance(dish_order,dict) else {category:[] for category in categories}
        self.last_moved_category=None
        self.column_layouts={}
        grid=QGridLayout();grid.setHorizontalSpacing(12);layout.addLayout(grid,1)
        for column in (1,2):
            holder=QWidget();holder_layout=QVBoxLayout(holder);holder_layout.setContentsMargins(0,0,0,0)
            title=QLabel(f"{column}. oszlop");title.setStyleSheet("font-weight:700;color:#285943")
            scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            rows=QWidget();rows_layout=QVBoxLayout(rows);rows_layout.setContentsMargins(4,4,8,4);rows_layout.setSpacing(5)
            scroll.setWidget(rows);self.column_layouts[column]=rows_layout
            holder_layout.addWidget(title);holder_layout.addWidget(scroll,1);grid.addWidget(holder,0,column-1)
        controls=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel)
        controls.accepted.connect(self.accept);controls.rejected.connect(self.reject);layout.addWidget(controls)
        self.rebuild_sections()

    def rebuild_sections(self):
        for column,row_layout in self.column_layouts.items():
            while row_layout.count():
                item=row_layout.takeAt(0);widget=item.widget()
                if widget:widget.deleteLater()
            for index,category in enumerate(self.section_columns[column]):
                row=OrderRow(recent=category==self.last_moved_category)
                line=QHBoxLayout(row);line.setContentsMargins(9,4,5,4)
                label=QLabel(category);label.setMinimumWidth(0);line.addWidget(label,1)
                up=QPushButton("↑");down=QPushButton("↓");transfer=QPushButton("→" if column==1 else "←")
                for control in (up,down,transfer):
                    control.setFixedSize(34,30);control.setFocusPolicy(Qt.FocusPolicy.NoFocus)
                transfer.setText("");transfer.setIcon(two_way_arrow_icon());transfer.setIconSize(QSize(20,16))
                up.setEnabled(index>0);down.setEnabled(index<len(self.section_columns[column])-1)
                transfer.setToolTip(f"Áthelyezés a {2 if column==1 else 1}. oszlopba")
                up.clicked.connect(lambda _=False,c=column,i=index:self.move_section(c,i,-1))
                down.clicked.connect(lambda _=False,c=column,i=index:self.move_section(c,i,1))
                transfer.clicked.connect(lambda _=False,c=category,target=2 if column==1 else 1:self.move_section_to(c,target))
                dishes=QPushButton("Ételek rendezése…");dishes.clicked.connect(lambda _=False,c=category:self.open_dish_order(c))
                line.addWidget(up);line.addWidget(down);line.addWidget(transfer);line.addWidget(dishes);row_layout.addWidget(row)
            row_layout.addStretch(1)

    def move_section(self,column,index,direction):
        target=index+direction
        if not 0<=target<len(self.section_columns[column]):return
        values=self.section_columns[column];values[index],values[target]=values[target],values[index]
        self.last_moved_category=values[target]
        self.rebuild_sections()

    def move_section_to(self,category,target_column):
        source_column=next((column for column in (1,2) if category in self.section_columns[column]),None)
        if source_column is None or source_column==target_column:return
        self.section_columns[source_column].remove(category)
        self.section_columns[target_column].append(category)
        self.last_moved_category=category
        self.rebuild_sections()

    def open_dish_order(self,category):
        dialog=SectionDishOrderDialog(self,category,self.dishes_by_category.get(category,[]),self.dish_order.get(category,[]))
        if dialog.exec()==QDialog.DialogCode.Accepted:self.dish_order[category]=dialog.ordered_ids()

    def section_layout(self):return {str(column):list(self.section_columns[column]) for column in (1,2)}

    def ordered_categories(self):return self.section_columns[1]+self.section_columns[2]

    def dish_orders(self):return {category:list(values) for category,values in self.dish_order.items()}


class DailyDishDialog(QDialog):
    def __init__(self,parent,dish,selected):
        super().__init__(parent);self.setWindowTitle(dish["name"])
        self.setMinimumWidth(420);layout=QVBoxLayout(self)
        title=QLabel(dish["name"]);title.setStyleSheet("font-size:19px;font-weight:700;color:#173f34")
        layout.addWidget(title)
        self.include=QCheckBox("Felveszem a kiválasztott napi étlapra");self.include.setChecked(True)
        layout.addWidget(self.include)
        form=QFormLayout();layout.addLayout(form)
        self.regular=price_edit(dish["price"]);form.addRow("Normál ár (Ft)",self.regular)
        self.promo=QCheckBox("Akciós ár ezen a napon");self.promo.setChecked(bool(selected and selected["promo_enabled"] and selected["promo_price"] is not None))
        form.addRow("Akció",self.promo)
        self.promo_amount=price_edit(selected["promo_price"] if selected and selected["promo_price"] is not None else 0)
        self.promo_amount.setEnabled(self.promo.isChecked());self.promo.toggled.connect(self.promo_amount.setEnabled)
        form.addRow("Akciós ár",self.promo_amount)
        layout.addWidget(QLabel("Az új normál ár az étel adatlapján is frissül."))
        controls=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel)
        controls.accepted.connect(self.validate_accept);controls.rejected.connect(self.reject);layout.addWidget(controls)

    def validate_accept(self):
        try:
            regular=int(self.regular.text());promo=int(self.promo_amount.text() or "0")
        except ValueError:
            QMessageBox.warning(self,APP_NAME,"Írd be a normál és az akciós árat számjegyekkel.");return
        if self.promo.isChecked() and (regular<=0 or promo>=regular):
            QMessageBox.warning(self,APP_NAME,"Az akciós ár legyen kisebb a normál árnál.");return
        self.accept()


class FoodButton(QPushButton):
    pass


class AnimatedFoodAction(QPushButton):
    """Small animated elevation cue so the add/remove control reads as clickable."""
    def __init__(self,label,parent=None):
        super().__init__(label,parent)
        self.shadow=QGraphicsDropShadowEffect(self)
        self.shadow.setBlurRadius(0);self.shadow.setOffset(0,1);self.shadow.setColor(QColor(52,82,55,95))
        self.setGraphicsEffect(self.shadow)
        self.animation=QPropertyAnimation(self.shadow,b"blurRadius",self)
        self.animation.setDuration(145);self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)
    def enterEvent(self,event):
        self.animation.stop();self.animation.setStartValue(self.shadow.blurRadius());self.animation.setEndValue(13)
        self.animation.start();self.shadow.setOffset(0,3);super().enterEvent(event)
    def leaveEvent(self,event):
        self.animation.stop();self.animation.setStartValue(self.shadow.blurRadius());self.animation.setEndValue(0)
        self.animation.start();self.shadow.setOffset(0,1);super().leaveEvent(event)


class PreviewLabel(QLabel):
    """Preview canvas with draggable guides for the printed sections."""
    from PyQt6.QtCore import pyqtSignal
    regionChanged = pyqtSignal(str, object)
    zoomRequested = pyqtSignal(int, object)
    panRequested = pyqtSignal(object)
    def __init__(self,parent=None):
        super().__init__(parent);self.guides=False;self.regions={};self._drag=None
        self.manual_pan_zoom=False;self._pan_position=None
        self.setMouseTracking(True)
    def set_manual_pan_zoom(self,enabled):
        self.manual_pan_zoom=bool(enabled)
        self.setCursor(Qt.CursorShape.OpenHandCursor if enabled else Qt.CursorShape.ArrowCursor)
    def set_guides(self,enabled,regions):
        self.guides=enabled;self.regions=regions;self.update()
    def paintEvent(self,event):
        super().paintEvent(event)
        if not self.guides or not self.pixmap() or self.width()<=0:return
        scale=self.pixmap().width()/1440;p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing)
        for name,y in self.regions.items():
            yy=round(y*scale)
            p.setPen(QPen(QColor(37,116,93,190),2));p.drawLine(12,yy,self.width()-12,yy)
            p.setPen(Qt.PenStyle.NoPen);p.setBrush(QColor(37,116,93,220));p.drawRoundedRect(16,yy-12,150,24,9,9)
            p.setPen(QColor("white"));p.drawText(24,yy+5,name)
        p.end()
    def mousePressEvent(self,event):
        if self.guides and event.button()==Qt.MouseButton.LeftButton:
            scale=self.pixmap().width()/1440 if self.pixmap() else 0
            if scale>0:
                y=event.position().y()/scale
                for name,guide_y in reversed(list(self.regions.items())):
                    if abs(guide_y-y)<=16:
                        self._drag=(name,y,guide_y);self.setCursor(Qt.CursorShape.SizeVerCursor);event.accept();return
        if self.manual_pan_zoom and event.button()==Qt.MouseButton.LeftButton:
            self._pan_position=event.position().toPoint()
            self.setCursor(Qt.CursorShape.ClosedHandCursor);event.accept();return
        super().mousePressEvent(event)
    def mouseMoveEvent(self,event):
        if self._drag:
            name,start,original=self._drag;scale=self.pixmap().width()/1440
            header_shift=self.regions.get("Fejléc vége",205)-205
            limits={"Fejléc vége":(195,235),"Napi menü vége":(420+header_shift,640+header_shift),
                    "Heti menü kezdete":(310+header_shift,430+header_shift)}
            low,high=limits.get(name,(100,1700))
            y=round(max(low,min(high,event.position().y()/scale)))
            self.regions[name]=y;self.regionChanged.emit(name,y);self.update();event.accept();return
        if self._pan_position is not None:
            position=event.position().toPoint()
            delta=position-self._pan_position;self._pan_position=position
            self.panRequested.emit(delta);event.accept();return
        super().mouseMoveEvent(event)
    def mouseReleaseEvent(self,event):
        if self._drag and event.button()==Qt.MouseButton.LeftButton:
            self._drag=None;self.unsetCursor()
            if self.manual_pan_zoom:self.setCursor(Qt.CursorShape.OpenHandCursor)
            event.accept();return
        if self._pan_position is not None and event.button()==Qt.MouseButton.LeftButton:
            self._pan_position=None
            self.setCursor(Qt.CursorShape.OpenHandCursor if self.manual_pan_zoom else Qt.CursorShape.ArrowCursor)
            event.accept();return
        super().mouseReleaseEvent(event)
    def wheelEvent(self,event):
        if self.manual_pan_zoom and event.angleDelta().y():
            self.zoomRequested.emit(event.angleDelta().y(),event.position().toPoint())
            event.accept();return
        super().wheelEvent(event)


class DishCatalogItem(QTreeWidgetItem):
    def __lt__(self,other):
        tree=self.treeWidget();column=tree.sortColumn() if tree else 0
        if column==2:
            return int(self.data(2,Qt.ItemDataRole.UserRole+1) or 0)<int(other.data(2,Qt.ItemDataRole.UserRole+1) or 0)
        return self.text(column).casefold()<other.text(column).casefold()


class CalendarDateEdit(QDateEdit):
    """Date edit with an explicit calendar glyph in the popup affordance."""
    def paintEvent(self,event):
        super().paintEvent(event)
        if not self.isEnabled():return
        painter=QPainter(self);painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color=QColor("#604c42");painter.setPen(QPen(color,1.4));painter.setBrush(Qt.BrushStyle.NoBrush)
        x=self.width()-19;y=(self.height()-12)/2
        painter.drawRoundedRect(int(x),int(y+1),12,11,1.5,1.5)
        painter.drawLine(int(x),int(y+4),int(x+12),int(y+4))
        painter.drawLine(int(x+3),int(y),int(x+3),int(y+3))
        painter.drawLine(int(x+9),int(y),int(x+9),int(y+3))
        painter.setBrush(color);painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRect(int(x+3),int(y+6),2,2);painter.drawRect(int(x+7),int(y+6),2,2)
        painter.end()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__();self.store=Store(data_dir()/"etlapstudio.sqlite3")
        self.store.set_settings({"restaurant_name":self.store.setting("restaurant_name","Megyeháza Étterem"),
                                 "address":self.store.setting("address","Miskolc, Városház tér 1."),
                                 "phone":self.store.setting("phone","+36 30 / 513 2605"),
                                 "facebook_url":self.store.setting("facebook_url","facebook.com/mhetterem"),
                                 "note":self.store.setting("note","Az étlapváltoztatás jogát fenntartjuk!"),
                                 "daily_menu_price":self.store.setting("daily_menu_price","2800")})
        old_facebook=(self.store.setting("facebook_url","") or "").strip().lower()
        old_facebook=old_facebook.removeprefix("https://").removeprefix("http://").removeprefix("www.").rstrip("/")
        if old_facebook in {"itcetterem","ittetterem","facebook.com/itcetterem","facebook.com/ittetterem",
                            "facebook.com/share/1gqgcnjxe","facebook.com/megyehazaetteremmiskolc"}:
            self.store.set_settings({"facebook_url":"facebook.com/mhetterem"})
        if self.store.setting("guide_layout_version","0")!="9":
            layout_defaults={"guide_layout_version":"9"}
            for key,value in {"guide_daily_header":"205","guide_daily_menu_end":"438",
                              "guide_weekly_header":"205","guide_weekly_days":"330"}.items():
                if self.store.setting(key) is None:layout_defaults[key]=value
            # Promote only untouched former defaults; preserve sizes the user tuned.
            for role,old,new in (("daily_title","18","22"),("header_date","14","16"),
                                 ("menu_price_label","7.5","12"),("menu_price_value","15","20"),
                                 ("weekday_title","13","16"),("weekly_label","10.5","15"),
                                 ("weekly_value","13","15"),("promo_new_price","8","12.5"),
                                 ("dish_name","12.5","14.5"),
                                 ("footer_note","7","10")):
                if self.store.setting("font_size_"+role)==old:
                    layout_defaults["font_size_"+role]=new
            for kind in ("daily","weekly","special"):
                key=kind+"_font_size_dish_name"
                if self.store.setting(key)=="12.5":layout_defaults[key]="14.5"
            if self.store.setting("font_size_header_title")=="19.5":
                layout_defaults["font_size_header_title"]="11"
                if self.store.setting("font_header_title")=="Georgia":
                    layout_defaults["font_header_title"]="Segoe UI"
            self.store.set_settings(layout_defaults)
        if self.store.setting("design_font_default_version","0")!="1":
            font_defaults={"design_font_default_version":"1"}
            for key in ("font_heading","daily_font_heading","weekly_font_heading","special_font_heading"):
                if self.store.setting(key) in ("Georgia","Trebuchet MS"):font_defaults[key]="Candara"
            self.store.set_settings(font_defaults)
        self.setWindowTitle(APP_NAME);self.setWindowIcon(QIcon(str(app_asset("megyehaza_emblem.png"))));self.setMinimumSize(760,540)
        screen=QApplication.primaryScreen()
        available=screen.availableGeometry() if screen else None
        if available:self.resize(min(1500,max(760,available.width()-48)),min(900,max(540,available.height()-72)))
        else:self.resize(1280,780)
        self._loading=False;self._image=None;self._date_change_old=None;self.preview_archive=None;self._manual_week_preview=False
        self.manual_preview_zoom=1.0
        self._initial_splitter_layout_done=False
        self.timer=QTimer(self);self.timer.setSingleShot(True);self.timer.timeout.connect(self.refresh_preview)
        self._responsive_timer=QTimer(self);self._responsive_timer.setSingleShot(True);self._responsive_timer.setInterval(180)
        self._responsive_timer.timeout.connect(self.refresh_food_grid)
        splitter=QSplitter(Qt.Orientation.Horizontal);self.main_splitter=splitter;self._responsive_orientation=Qt.Orientation.Horizontal;self.setCentralWidget(splitter)
        left=QWidget();left_layout=QVBoxLayout(left);left_layout.setContentsMargins(10,8,6,8)
        brand=QHBoxLayout();brand.setContentsMargins(4,0,4,0)
        title=QLabel("Megyeháza Étterem – Étlapstúdió");title.setObjectName("appTitle");brand.addWidget(title,1)
        left_layout.addLayout(brand)
        self.tabs=QTabWidget();left_layout.addWidget(self.tabs,1)
        splitter.addWidget(left)
        right=QWidget();right_layout=QVBoxLayout(right);right_layout.setContentsMargins(8,12,12,12)
        self.preview_title=QLabel("Élő előnézet");self.preview_title.setObjectName("previewTitle")
        title_row=QHBoxLayout();title_row.addWidget(self.preview_title);title_row.addStretch();right_layout.addLayout(title_row)
        toolbar=QHBoxLayout();toolbar.setSpacing(6)
        toolbar.addWidget(button("Mentés",self.save_current))
        toolbar.addWidget(button("PDF",lambda:self.export("pdf")))
        toolbar.addWidget(button("Facebook-kép",lambda:self.export("png")))
        toolbar.addStretch();right_layout.addLayout(toolbar)
        controls=QHBoxLayout();controls.setSpacing(6)
        controls.addStretch()
        self.zoom_out_button=QPushButton("−");self.zoom_out_button.setFixedWidth(30);self.zoom_out_button.setAccessibleName("Kicsinyítés")
        self.zoom_in_button=QPushButton("+");self.zoom_in_button.setFixedWidth(30);self.zoom_in_button.setAccessibleName("Nagyítás")
        self.zoom_out_button.clicked.connect(lambda:self.zoom_preview_step(1/1.2))
        self.zoom_in_button.clicked.connect(lambda:self.zoom_preview_step(1.2))
        controls.addWidget(self.zoom_out_button);controls.addWidget(self.zoom_in_button)
        self.zoom=QComboBox();self.zoom.addItems(["Teljes oldal","Szélesség","Kézi pan-zoom"])
        self.zoom.setMaximumWidth(170);self.zoom.currentIndexChanged.connect(self.preview_zoom_mode_changed);controls.addWidget(self.zoom)
        right_layout.addLayout(controls)
        self.scroll=QScrollArea();self.scroll.setWidgetResizable(False);self.scroll.setAlignment(Qt.AlignmentFlag.AlignHCenter|Qt.AlignmentFlag.AlignTop)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.viewport().installEventFilter(self)
        self.zoom.setCurrentIndex(0)
        self.preview=PreviewLabel();self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter);self.preview.regionChanged.connect(self.save_layout_region)
        self.preview.zoomRequested.connect(self.zoom_preview_at);self.preview.panRequested.connect(self.pan_preview_by)
        self.scroll.setWidget(self.preview);right_layout.addWidget(self.scroll,1)
        self.status=QLabel();right_layout.addWidget(self.status)
        splitter.addWidget(right);self.preview_panel=right;splitter.setSizes([570,850]);splitter.setChildrenCollapsible(False)
        self.build_daily();self.build_weekly();self.build_special();self.build_appearance();self.build_archive()
        self.main_splitter.setStretchFactor(0, 5);self.main_splitter.setStretchFactor(1, 7)
        self.tab_date_controls=QStackedWidget();self.tab_date_controls.addWidget(self.daily_date_controls);self.tab_date_controls.addWidget(self.week_date_controls)
        self.tab_date_controls.setSizePolicy(QSizePolicy.Policy.Fixed,QSizePolicy.Policy.Preferred)
        self.tabs.setCornerWidget(self.tab_date_controls,Qt.Corner.TopRightCorner)
        self.tabs.currentChanged.connect(self.on_tab)
        self.refresh_daily();self.refresh_week();self.refresh_archive()
        self.store.copy_previous_daily(date.today());self.refresh_daily()
        self.schedule_preview()
        self.setStyleSheet('''
            QMainWindow { background:#efe8dc; }
            QWidget { background-color:#f8f3eb; color:#362f2b; font-size:13px; }
            QMainWindow,QWidget#previewPanel { background-color:#efe8dc; color:#362f2b; }
            QFrame { background-color:#f8f3eb; color:#362f2b; }
            QSplitter { background-color:#efe8dc; }
            QSplitter::handle { background:#d2c2b2; width:5px; }
            QTabWidget::pane { border:0; border-radius:16px; background:#fffaf2; }
            QTabBar { background:#efe8dc; }
            QTabBar::tab { padding:8px 12px; margin-right:3px; background:#e6d8c8; color:#604c42; border-radius:10px 10px 0 0; font-weight:600; }
            QTabBar::tab:selected { background:#fffaf2; color:#963f36; }
            QTabBar::tab:hover { background:#f1e4d6; color:#793c32; }
            QPushButton { padding:9px 13px; background:#d9e5d8; color:#344b3a; border:0; border-radius:10px; font-weight:600; }
            QPushButton:hover { background:#c2d5c1; color:#263e2e; }
            QPushButton:pressed { background:#a8c1a9; color:#203b2a; }
            QPushButton:disabled { background:#e8e1d8; color:#999087; }
            QPushButton[role="category"] { padding:4px 6px; min-height:25px; background:#f0e3d1; color:#66503f; font-size:12px; font-weight:650; border:0; border-radius:8px; }
            QPushButton[role="category"][active="true"] { background:#b85a4a; color:#ffffff; }
            QPushButton[role="destructive"] { background:#f1dfdc; color:#923d34; border:1px solid #d8aaa3; }
            QPushButton[role="destructive"]:hover { background:#e9cbc5; color:#762f28; }
            QPushButton[role="food"] { padding:8px; min-height:54px; min-width:0; text-align:left; background:#fffdf8; color:#38332f; border:1px solid #eadfce; border-radius:12px; }
            QPushButton[role="newFoodCard"] { padding:12px; min-height:82px; text-align:center; background:#ffffff; color:#344b3a; border:1px dashed #cbbdaf; border-radius:12px; font-weight:700; }
            QPushButton[role="newFoodCard"]:hover { background:#f7f2eb; border-color:#9d8977; }
            QPushButton[role="food"][selected="true"] { background:#deeadb; color:#263e2e; border:1px solid #7f9c7c; }
            QPushButton[role="foodEdit"] { padding:6px 5px; min-width:54px; background:#ffffff; color:#6c4436; border:1px solid #d8cbbd; border-radius:9px; }
            QPushButton[role="foodEdit"]:hover { background:#f7f2eb; color:#55382d; }
            QPushButton[role="foodAction"] { padding:3px; min-width:42px; min-height:30px; background:#dce9d8; color:#31553b; border:1px solid #bdd0b8; border-radius:8px; font-size:17px; }
            QPushButton[role="foodAction"]:hover { background:#c7ddc0; color:#23452d; border:1px solid #789a73; }
            QPushButton[role="foodAction"]:pressed { background:#aac9a2; }
            QPushButton[role="foodRemove"] { padding:3px; min-width:42px; min-height:30px; background:#ffffff; color:#98463d; border:1px solid #e0c9c4; border-radius:8px; font-size:17px; }
            QPushButton[role="foodRemove"]:hover { background:#fff8f6; color:#7f332d; border:1px solid #ce8e82; }
            QPushButton[role="foodRemove"]:pressed { background:#f5e8e5; }
            QSlider::groove:horizontal { height:6px; background:#e1d5c8; border-radius:3px; }
            QSlider::sub-page:horizontal { background:#a94e41; border-radius:3px; }
            QSlider::handle:horizontal { width:18px; margin:-6px 0; background:#fffaf2; border:2px solid #a94e41; border-radius:9px; }
            QLineEdit,QComboBox,QDateEdit,QFontComboBox { background:#fffdf9; color:#362f2b; padding:8px; border:1px solid #dacbbb; border-radius:9px; selection-background-color:#bc6957; selection-color:#ffffff; }
            QLineEdit:focus,QComboBox:focus,QDateEdit:focus,QFontComboBox:focus { background:#ffffff; border:2px solid #bf715b; color:#2e2824; }
            QLineEdit:disabled,QComboBox:disabled,QDateEdit:disabled,QFontComboBox:disabled { background:#ece5dc; color:#898076; }
            QComboBox::drop-down,QDateEdit::drop-down { background:#eadfd2; border:0; border-top-right-radius:8px; border-bottom-right-radius:8px; width:26px; }
            QComboBox::down-arrow,QFontComboBox::down-arrow { width:0; height:0; border-left:5px solid transparent; border-right:5px solid transparent; border-top:6px solid #604c42; }
            QDateEdit::down-arrow { image:none; width:0; height:0; }
            QTabBar#categoryTabs { background:transparent; }
            QTabBar#categoryTabs::tab { padding:7px 10px 8px; margin:4px 2px 0 0; background:#e6d8c8; color:#604c42; border:1px solid #d2c0ad; border-bottom-color:#c6b09b; border-top-left-radius:8px; border-top-right-radius:8px; font-size:12px; font-weight:600; }
            QTabBar#categoryTabs::tab:selected { background:#fffaf2; color:#963f36; border-bottom-color:#fffaf2; }
            QTabBar#categoryTabs[inactiveRow="true"]::tab:selected { background:#e6d8c8; color:#604c42; border-bottom-color:#c6b09b; }
            QTabBar#categoryTabs::tab:hover:!selected { background:#f1e4d6; color:#793c32; }
            QTabBar#categoryTabs::scroller { width:18px; }
            QTabBar#categoryTabs QToolButton { padding:2px; min-width:18px; background:#eadfd2; color:#604c42; border:1px solid #d2c0ad; border-radius:5px; }
            QComboBox QAbstractItemView { background:#fffdf9; color:#362f2b; selection-background-color:#b85a4a; selection-color:#ffffff; border:1px solid #d7c4b2; outline:0; }
            QCheckBox { spacing:8px; color:#50453e; background:transparent; }
            QCheckBox::indicator { width:19px; height:19px; background:#fffdf9; border:1px solid #b8a896; border-radius:5px; }
            QCheckBox::indicator:hover { background:#f2e8dc; border-color:#a35545; }
            QCheckBox::indicator:checked { background:#a94e41; border:1px solid #87392f; }
            QTreeWidget,QListWidget { background:#fffcf7; color:#362f2b; alternate-background-color:#f3eadf; border:1px solid #ddcbb7; border-radius:11px; selection-background-color:#ead8c8; selection-color:#392d27; }
            QTreeWidget::item,QListWidget::item { background:transparent; color:#362f2b; padding:5px; }
            QTreeWidget::item:hover,QListWidget::item:hover { background:#f3e6d9; color:#362f2b; }
            QDockWidget { background:#f8f3eb; color:#362f2b; }
            QDockWidget::title { background:#a64d40; padding:10px; color:#ffffff; font-weight:bold; }
            QLabel#appTitle { color:#874739; font-size:18px; font-weight:bold; padding:2px 4px; }
            QLabel#previewTitle { color:#864637; font-size:18px; font-weight:bold; }
            QLabel#dailySpecial { background:#e2ecdc; border-radius:12px; color:#42583f; padding:12px; }
            QLabel { background:transparent; color:#362f2b; }
            QScrollArea { border:0; background:#f8f3eb; }
            QScrollBar:vertical { background:#eee5da; width:14px; margin:2px; border-radius:6px; }
            QScrollBar::handle:vertical { background:#c5b09b; min-height:28px; border-radius:6px; }
            QScrollBar::handle:vertical:hover { background:#a98e76; }
            QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical { height:0; background:transparent; }
            QScrollBar:horizontal { background:#eee5da; height:14px; margin:2px; border-radius:6px; }
            QScrollBar::handle:horizontal { background:#c5b09b; min-width:28px; border-radius:6px; }
            QScrollBar::add-line:horizontal,QScrollBar::sub-line:horizontal { width:0; background:transparent; }
            QToolTip { background:#382f2a; color:#fffaf2; border:1px solid #6c5a4f; padding:5px 7px; border-radius:5px; }
            QMenuBar { background:#e6d8c8; color:#43372f; }
            QMenuBar::item { background:transparent; color:#43372f; padding:7px 10px; }
            QMenuBar::item:selected { background:#b85a4a; color:#ffffff; }
            QMenu { background:#fffaf2; color:#362f2b; border:1px solid #d8c7b6; }
            QMenu::item { background:transparent; color:#362f2b; padding:6px 28px 6px 18px; }
            QMenu::item:selected { background:#ead8c8; color:#362f2b; }
            QDialog,QMessageBox { background:#f8f3eb; color:#362f2b; }
            QCalendarWidget QWidget { background:#fffaf2; color:#362f2b; }
            QCalendarWidget QToolButton { background:#a64d40; color:#ffffff; }
            QCalendarWidget QAbstractItemView { background:#fffdf9; color:#362f2b; selection-background-color:#b85a4a; selection-color:#ffffff; }
            QStatusBar { background:#ddcbb7; color:#4e443d; }
        ''')

    def pane(self,title):
        outer=QWidget();layout=QVBoxLayout(outer);layout.setContentsMargins(12,12,12,12)
        heading=QLabel(title);heading.setWordWrap(True);layout.addWidget(heading);return outer,layout

    def build_daily(self):
        page=QWidget();box=QVBoxLayout(page);box.setContentsMargins(10,10,10,10);box.setSpacing(7)
        self.tabs.addTab(page,"Napi")
        self.daily_date_controls=QWidget();date_row=QHBoxLayout(self.daily_date_controls);date_row.setContentsMargins(0,0,0,0);date_row.setSpacing(5)
        self.day=CalendarDateEdit(qdate(date.today()));self.day.setCalendarPopup(True);self.day.setMaximumWidth(132)
        self.day.setDisplayFormat("yyyy.MM.dd.");self.day.dateChanged.connect(self.daily_date_changed)
        date_row.addWidget(QLabel("Dátum"));date_row.addWidget(self.day)
        date_row.addWidget(button("Ma",lambda:self.day.setDate(qdate(date.today()))))
        self.active_category="Összes"
        category_row=QHBoxLayout();category_row.addWidget(QLabel("Ételkategória:"))
        self.category_filter=QComboBox();self.category_filter.addItem("Összes kategória","Összes")
        for category in CATEGORIES:
            if category!="Menü":self.category_filter.addItem(category,category)
        self.category_filter.currentIndexChanged.connect(self.choose_category_index)
        category_row.addWidget(self.category_filter,1);box.addLayout(category_row)
        self.search=QLineEdit();self.search.setPlaceholderText("Keresés az ételek között…");self.search.textChanged.connect(self.refresh_food_grid)
        self.search.returnPressed.connect(self.handle_search_enter)
        self.search.setToolTip("Enter: ugrás az első hozzáadható találatra; találat nélkül új étel felvétele.")
        box.addWidget(self.search)
        self.food_scroll=QScrollArea();self.food_scroll.setWidgetResizable(True)
        self.food_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        foods_wrap=QWidget();self.food_grid=QGridLayout(foods_wrap);self.food_grid.setContentsMargins(2,3,8,3);self.food_grid.setSpacing(8)
        self.food_scroll.setWidget(foods_wrap);box.addWidget(self.food_scroll,1)
        self.copy_previous_button=button("Legutóbbi kész étlap másolása",self.copy_previous_daily_menu)
        self.section_order_button=button("Ételek sorrendjének módosítása…",self.edit_daily_section_order)
        self.clear_daily_button=button("Étlap kiürítése…",self.clear_daily_menu);self.clear_daily_button.setProperty("role","destructive")
        action_row=QHBoxLayout();action_row.setSpacing(8)
        action_row.addWidget(self.copy_previous_button,2)
        action_row.addWidget(self.section_order_button,2)
        action_row.addWidget(self.clear_daily_button,1)
        box.addLayout(action_row)
        self.daily_count=QLabel();box.addWidget(self.daily_count)

    def edit_daily_section_order(self):
        categories=[category for category in CATEGORIES if category!="Menü"]
        day_key=self.current_day().isoformat()
        order_key="daily_section_order_"+day_key;layout_key="daily_section_layout_"+day_key
        dish_order_key="daily_dish_order_"+day_key
        try:order=json.loads(self.store.setting(order_key,""))
        except (TypeError,ValueError):order=categories
        try:layout_by_column=json.loads(self.store.setting(layout_key,""))
        except (TypeError,ValueError):layout_by_column=None
        try:dish_order=json.loads(self.store.setting(dish_order_key,""))
        except (TypeError,ValueError):dish_order={}
        catalog=self.store.db.execute(
            "SELECT id,name,category,priority,priority_pending FROM dishes ORDER BY name COLLATE HUNGARIAN,id").fetchall()
        catalog_by_category={category:[] for category in categories}
        for dish in catalog:
            if dish["category"] in catalog_by_category:catalog_by_category[dish["category"]].append(dish)
        def priority_order(rows):
            def rank(pair):
                try:code=int(pair[1]["priority"] or 0)
                except (KeyError,TypeError,ValueError):code=0
                return (code if code>0 else 1_000_000_000+pair[0])
            return [row for _,row in sorted(enumerate(rows),key=rank)]
        if not dish_order:
            dish_order={category:[row["id"] for row in priority_order(rows)]
                        for category,rows in catalog_by_category.items()}
        dialog=SectionOrderDialog(self,categories,order,layout_by_column,
                                  self.store.selection(self.current_day()),dish_order)
        if dialog.exec()!=QDialog.DialogCode.Accepted:return
        layout=dialog.section_layout();ordered=dialog.ordered_categories()
        visible_orders=dialog.dish_orders()
        for category,rows in catalog_by_category.items():
            visible=[int(value) for value in visible_orders.get(category,[]) if value is not None]
            visible_set=set(visible)
            base_order=[row["id"] for row in priority_order(rows)]
            pending_ids=[row["id"] for row in rows
                         if row["priority_pending"] and row["id"] in visible_set]
            if pending_ids:
                base_order=insert_pending_dishes(base_order,visible,pending_ids)
            with self.store.db:
                self.store.db.executemany("UPDATE dishes SET priority=? WHERE id=?",
                    [((index+1)*1000,dish_id) for index,dish_id in enumerate(base_order)])
                if pending_ids:
                    self.store.db.executemany("UPDATE dishes SET priority_pending=0 WHERE id=?",
                                              [(dish_id,) for dish_id in pending_ids])
        self.store.set_settings({layout_key:json.dumps(layout,ensure_ascii=False),
                                 order_key:json.dumps(ordered,ensure_ascii=False),
                                 dish_order_key:json.dumps(visible_orders,ensure_ascii=False)})
        self.preview_archive=None;self.schedule_preview()

    def choose_category(self,category):
        if hasattr(self,"category_filter"):
            index=self.category_filter.findData(category)
            if index>=0:self.category_filter.setCurrentIndex(index)

    def choose_category_index(self,index):
        if index<0 or index>=self.category_filter.count():return
        self.active_category=self.category_filter.itemData(index)
        self.refresh_food_grid()

    def clear_daily_menu(self):
        day=self.current_day()
        selected=self.store.selection(day)
        if not selected:
            QMessageBox.information(self,APP_NAME,"A kiválasztott nap étlapja már üres.");return
        answer=QMessageBox.question(self,"Napi étlap kiürítése",
            f"Biztosan eltávolítod mind a {len(selected)} ételt a(z) {display_date(day)} napi étlapról?\n\n"
            "Ez csak az adott napi étlapot üríti ki; az ételadatbázisban az ételek megmaradnak.",
            QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)
        if answer!=QMessageBox.StandardButton.Yes:return
        self.store.set_selected(day,[]);self.preview_archive=None
        self.refresh_daily();self.refresh_archive();self.status.setText("A napi étlap kiürült.")

    def copy_previous_daily_menu(self):
        target=self.current_day();source=self.store.latest_daily_menu_date(target)
        if source is None:
            QMessageBox.information(self,APP_NAME,"A kiválasztott nap előtt nem található kész napi étlap.");return
        answer=QMessageBox.question(self,"Legutóbbi étlap másolása",
            f"A legutóbbi kész étlap ({display_date(source)}) másolódik erre a napra: {display_date(target)}.\n\n"
            "A jelenlegi napi étlap tartalma lecserélődik.",
            QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)
        if answer!=QMessageBox.StandardButton.Yes:return
        copied=self.store.copy_latest_daily_menu(target)
        if not copied:
            QMessageBox.information(self,APP_NAME,"A kiválasztott nap előtt nem található kész napi étlap.")
            return
        self.preview_archive=None;self.refresh_daily();self.refresh_archive()
        self.status.setText(f"A legutóbbi kész étlap átmásolva: {display_date(copied)} → {display_date(target)}.")

    def refresh_food_grid(self,*_):
        if not hasattr(self,"food_grid"):return
        while self.food_grid.count():
            item=self.food_grid.takeAt(0)
            if item.widget():item.widget().deleteLater()
        query=self.search.text().strip()
        foods=list(self.store.daily_dishes(query))
        if self.active_category!="Összes" and not query:
            foods=[x for x in foods if x["category"]==self.active_category]
        selected={r["id"]:r for r in self.store.selection(self.current_day())}
        # Keep available matches alphabetical, but put dishes already on this day's menu first.
        foods.sort(key=lambda dish:dish["id"] not in selected)
        self._food_rows={r["id"]:r for r in foods}
        self._food_action_buttons={}
        cols=max(1,min(3,self.food_scroll.viewport().width()//235))
        new_category=None if self.active_category=="Összes" else self.active_category
        new_food=button("＋\nÚj étel",lambda checked=False,category=new_category:self.add_catalogue_dish(initial_category=category))
        new_food.setProperty("role","newFoodCard");new_food.setToolTip("Új étel felvétele"+(" · válaszd ki a kategóriát" if self.active_category=="Összes" else f" · kategória: {self.active_category}"))
        self.food_grid.addWidget(new_food,0,0)
        for n,dish in enumerate(foods):
            is_selected=dish["id"] in selected
            cols=max(1,min(3,self.food_scroll.viewport().width()//235))
            promo=bool(dish["promo_enabled"] and dish["promo_price"] is not None)
            card=QWidget();card.setStyleSheet("background:transparent")
            cardbox=QHBoxLayout(card);cardbox.setContentsMargins(0,0,0,0);cardbox.setSpacing(5)
            card.setStyleSheet("QWidget { background:#deeadb; border:1px solid #7f9c7c; border-radius:10px; }" if is_selected else
                               "QWidget { background:#fffdf8; border:1px solid #eadfce; border-radius:10px; }")
            details=QVBoxLayout();details.setContentsMargins(8,8,3,8);details.setSpacing(3)
            title=QLabel(dish["name"]);title.setWordWrap(True);title.setStyleSheet("font-weight:700;color:#38332f;background:transparent;border:0;")
            details.addWidget(title)
            if self.active_category=="Összes":
                category_label=QLabel(dish["category"]);category_label.setStyleSheet("font-size:11px;color:#817267;background:transparent;border:0;")
                details.addWidget(category_label)
            amount=QLabel(("Akciós ár: "+price(dish["promo_price"])) if promo else price(dish["price"]))
            amount.setStyleSheet(("font-weight:700;color:#a9433b;" if promo else "color:#5d554e;")+"background:transparent;border:0;")
            details.addWidget(amount);cardbox.addLayout(details,1)
            actions=QVBoxLayout();actions.setContentsMargins(0,5,5,5);actions.setSpacing(4)
            toggle=AnimatedFoodAction("×" if is_selected else "+")
            toggle.clicked.connect(lambda checked=False,dish_id=dish["id"]:self.toggle_daily_dish(dish_id))
            action_name="Eltávolítás" if is_selected else "Hozzáadás"
            toggle.setToolTip(action_name+" "+("a kiválasztott napi étlapról" if is_selected else "a kiválasztott napi étlaphoz"))
            toggle.setAccessibleName(action_name+": "+dish["name"])
            toggle.setProperty("role","foodRemove" if is_selected else "foodAction")
            self._food_action_buttons[dish["id"]]=(toggle,is_selected)
            edit=button("Szerk.",lambda checked=False,dish_id=dish["id"]:self.edit_daily_dish(dish_id))
            edit.setProperty("role","foodEdit");edit.setToolTip("Étel, ár és napi akció szerkesztése")
            edit.setAccessibleName("Szerkesztés: "+dish["name"])
            for action in (toggle,edit):
                action.setMinimumSize(48,32);action.setMaximumWidth(62)
                action.setSizePolicy(QSizePolicy.Policy.Fixed,QSizePolicy.Policy.Fixed)
                actions.addWidget(action)
            cardbox.addLayout(actions)
            position=n+1
            self.food_grid.addWidget(card,position//cols,position%cols)
        for col in range(cols):self.food_grid.setColumnStretch(col,1)
        self.food_grid.setRowStretch((len(foods)+cols-1)//cols,1)
        self.daily_count.setText(f"{len(selected)} étel szerepel a kiválasztott napi étlapon"+ (" · nincs találat" if not foods else ""))
        self.schedule_preview()

    def handle_search_enter(self):
        query=self.search.text().strip()
        if not query:return
        foods=list(self.store.daily_dishes(query))
        if not foods:
            self.add_catalogue_dish(initial_name=query)
            return
        selected_ids={row["id"] for row in self.store.selection(self.current_day())}
        target=next((food for food in foods if food["id"] not in selected_ids),None)
        if target is None:
            self.status.setText("Minden találat már szerepel a kiválasztott napi étlapon.")
            return
        action=self._food_action_buttons.get(target["id"])
        if action:
            toggle,_=action
            self.food_scroll.ensureWidgetVisible(toggle,12,12)
            toggle.setFocus(Qt.FocusReason.ShortcutFocusReason)
            self.status.setText(f"Találat: {target['name']} · Enterrel hozzáadható az étlaphoz.")

    def add_daily_dish(self,dish_id):
        dish=self.store.db.execute("SELECT price FROM dishes WHERE id=? AND active=1",(dish_id,)).fetchone()
        if not dish:return
        self.store.save_daily_dish(self.current_day(),dish_id,int(dish["price"]),True)
        self.status.setText("Az étel felkerült a kiválasztott napi étlapra.")
        self.preview_archive=None;self.refresh_daily();self.refresh_archive()

    def remove_daily_dish(self,dish_id):
        selected={row["id"]:dict(row) for row in self.store.selection(self.current_day())}
        if dish_id not in selected:return
        self.store.save_daily_dish(self.current_day(),dish_id,int(selected[dish_id]["price"]),False)
        self.status.setText("Az étel lekerült a kiválasztott napi étlapról.")
        self.preview_archive=None;self.refresh_daily();self.refresh_archive()

    def toggle_daily_dish(self,dish_id):
        selected={row["id"] for row in self.store.selection(self.current_day())}
        (self.remove_daily_dish if dish_id in selected else self.add_daily_dish)(dish_id)

    def add_catalogue_dish(self,checked=False,initial_name="",initial_category=None):
        form=DishDialog(self,initial_name=initial_name,initial_category=initial_category)
        if form.exec()!=QDialog.DialogCode.Accepted:return
        try:
            dish_id=self.store.add_dish(form.name.text().strip(),form.category.currentText(),int(form.amount.text()))
            self.store.save_daily_dish(self.current_day(),dish_id,int(form.amount.text()),True)
        except (ValueError,sqlite3.Error) as exc:
            QMessageBox.warning(self,APP_NAME,"Nem sikerült elmenteni az új ételt.\n"+str(exc));return
        self.search.clear();self.choose_category(initial_category or "Összes")
        self.refresh_menu_suggestions();self.refresh_daily()
        self.status.setText("Az új étel bekerült az adatbázisba és a kiválasztott napi étlapra.")

    def build_weekly(self):
        page,box=self.pane("Heti menü · leves, A és B menü külön az à la carte kínálattól")
        self.tabs.addTab(page,"Heti")
        self.week_date_controls=QWidget();row=QHBoxLayout(self.week_date_controls);row.setContentsMargins(0,0,0,0);row.setSpacing(5)
        self.week=CalendarDateEdit(qdate(monday(date.today())));self.week.setMaximumWidth(132)
        self.week.setCalendarPopup(True);self.week.setDisplayFormat("yyyy.MM.dd.")
        self.week.dateChanged.connect(lambda _:self.change_week())
        row.addWidget(QLabel("Hét"));row.addWidget(self.week)
        self.week_fields=[];self.week_closed=[];self.week_closure_notes=[]
        self.week_field_labels=[];self.week_closure_labels=[]
        self.week_save_timer=QTimer(self);self.week_save_timer.setSingleShot(True);self.week_save_timer.setInterval(300)
        self.week_save_timer.timeout.connect(self.persist_week_entries)
        scroll=QScrollArea();scroll.setWidgetResizable(True)
        inner=QWidget();innerbox=QVBoxLayout(inner)
        for i,label in enumerate(WEEKDAYS):
            dayrow=QHBoxLayout();heading=QLabel(label);heading.setStyleSheet("font-weight:bold;color:#176246;margin-top:8px;")
            dayrow.addWidget(heading);dayrow.addStretch();closed=QCheckBox("Zárva a heti menün");closed.setToolTip("Csak a heti étlapon rejti el ezen a napnál a leves és az A/B menü sorait. A napi étlap adatait nem módosítja.");closed.toggled.connect(self.schedule_week_save);dayrow.addWidget(closed);innerbox.addLayout(dayrow)
            form=QFormLayout();group=[];field_labels=[]
            for field in ("Leves","A menü","B menü"):
                edit=QLineEdit();edit.textChanged.connect(self.schedule_week_save)
                completer=QCompleter(self.store.menu_suggestions(),edit)
                completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
                completer.setFilterMode(Qt.MatchFlag.MatchContains)
                edit.setCompleter(completer)
                form.addRow(field,edit);group.append(edit);field_labels.append(form.labelForField(edit))
            self.week_fields.append(group);self.week_field_labels.append(field_labels);innerbox.addLayout(form)
            closure_note=QLineEdit();closure_note.setPlaceholderText("Megjegyzés / ok (pl. ünnepnap miatt)");closure_note.textChanged.connect(self.schedule_week_save)
            self.week_closed.append(closed);self.week_closure_notes.append(closure_note);form.addRow("Zárva megjegyzés",closure_note)
            self.week_closure_labels.append(form.labelForField(closure_note))
            self.update_week_day_visibility(i)
        innerbox.addStretch();scroll.setWidget(inner);box.addWidget(scroll,1)
        note_row=QHBoxLayout()
        note=QLabel("Az előnézet csak a frissítés gombbal készül el. A menüt a jobb felső Mentés gomb rögzíti.")
        note.setWordWrap(True);note_row.addWidget(note,1)
        note_row.addWidget(button("Előnézet frissítése",self.refresh_week_preview));box.addLayout(note_row)

    def build_special(self):
        page,box=self.pane("Különleges alkalom · egyedi címsor és szabadon formázható, nagy szövegmező")
        self.tabs.addTab(page,"Különleges")
        row=QHBoxLayout();self.special_show_date=QCheckBox("Dátum megjelenítése")
        self.special_show_date.setChecked(self.store.setting("special_show_date","0")=="1")
        self.special_date=CalendarDateEdit(qdate(date.today()));self.special_date.setCalendarPopup(True)
        self.special_date.setDisplayFormat("yyyy.MM.dd.");self.special_date.setEnabled(self.special_show_date.isChecked())
        self.special_show_date.toggled.connect(self.special_date.setEnabled);self.special_date.dateChanged.connect(self.special_changed)
        self.special_show_date.toggled.connect(self.special_changed)
        row.addWidget(self.special_show_date);row.addWidget(self.special_date)
        self.special_show_title=QCheckBox("Címsor megjelenítése")
        self.special_show_title.setChecked(self.store.setting("special_show_title","0")=="1")
        self.special_title_edit=QLineEdit(self.store.setting("special_title",""))
        self.special_title_edit.setPlaceholderText("Az étlapon megjelenő címsor")
        self.special_title_edit.setEnabled(self.special_show_title.isChecked())
        self.special_title_edit.textChanged.connect(self.special_changed)
        self.special_show_title.toggled.connect(self.special_title_edit.setEnabled);self.special_show_title.toggled.connect(self.special_changed)
        row.addWidget(self.special_show_title);row.addWidget(self.special_title_edit,1);box.addLayout(row)
        layout_row=QHBoxLayout();layout_row.addWidget(QLabel("Elrendezés"))
        self.special_header_mode=QComboBox()
        for label,mode,tip in (
            ("Teljes fejléc","full","Logó, címsor, dátum és éttermi elérhetőségek."),
            ("Fejléc nélkül","none","Csak a szöveges panel jelenik meg."),
            ("Összevont panelek","merged","A logó és címsor a szöveggel egy közös panelbe kerül."),
            ("Középre tett logó","logo","Csak a logó jelenik meg középen, cím és kontaktadatok nélkül."),
        ):
            self.special_header_mode.addItem(label,mode)
            self.special_header_mode.setItemData(self.special_header_mode.count()-1,tip,Qt.ItemDataRole.ToolTipRole)
        saved_header_mode=self.store.setting("special_header_mode","full")
        header_index=self.special_header_mode.findData(saved_header_mode)
        self.special_header_mode.setCurrentIndex(header_index if header_index>=0 else 0)
        self.special_header_mode.currentIndexChanged.connect(self.special_changed)
        footer_row=QHBoxLayout();self.special_show_footer=QCheckBox("Lábjegyzet megjelenítése")
        self.special_show_footer.setChecked(self.store.setting("special_show_footer","1")=="1")
        self.special_footer_note=QLineEdit(self.store.setting("special_footer_note",self.store.setting("note","Az étlapváltoztatás jogát fenntartjuk!")))
        self.special_footer_note.setPlaceholderText("A különleges lap lábjegyzete")
        self.special_footer_note.setEnabled(self.special_show_footer.isChecked())
        self.special_show_footer.toggled.connect(self.special_footer_note.setEnabled)
        self.special_show_footer.toggled.connect(self.special_changed)
        self.special_footer_note.textChanged.connect(self.special_changed)
        footer_row.addWidget(self.special_show_footer);footer_row.addWidget(self.special_footer_note,1);box.addLayout(footer_row)
        size_row=QHBoxLayout();size_row.addWidget(QLabel("Kimeneti méret"))
        self.special_size_preset=QComboBox()
        for label,width,height in (("A4 álló · 1240 × 1754",1240,1754),("Instagram négyzet · 1080 × 1080",1080,1080),("Instagram álló · 1080 × 1350",1080,1350),("Story / Reels · 1080 × 1920",1080,1920),("Facebook fekvő · 1200 × 630",1200,630),("Full HD fekvő · 1920 × 1080",1920,1080)):
            self.special_size_preset.addItem(label,(width,height))
        saved_width=int(self.store.setting("special_canvas_width","1240") or "1240")
        saved_height=int(self.store.setting("special_canvas_height","1754") or "1754")
        self.special_size_width=QSpinBox();self.special_size_width.setRange(200,8000);self.special_size_width.setSuffix(" px");self.special_size_width.setValue(saved_width)
        self.special_size_height=QSpinBox();self.special_size_height.setRange(200,8000);self.special_size_height.setSuffix(" px");self.special_size_height.setValue(saved_height)
        self.special_size_preset.setEditable(True);self.special_size_preset.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.special_size_preset.lineEdit().setReadOnly(True)
        preset_index=next((i for i in range(self.special_size_preset.count()) if self.special_size_preset.itemData(i)==(saved_width,saved_height)),-1)
        if preset_index>=0:self.special_size_preset.setCurrentIndex(preset_index)
        else:
            self.special_size_preset.setCurrentIndex(-1)
            self.special_size_preset.setEditText(f"Egyedi méret · {saved_width} × {saved_height}")
        self._updating_special_size=False
        self.special_size_preset.currentIndexChanged.connect(self.special_apply_size_preset)
        self.special_size_preset.setMinimumWidth(220);self.special_header_mode.setMinimumWidth(190)
        layout_row.addWidget(self.special_header_mode);layout_row.addWidget(self.special_size_preset)
        layout_row.addWidget(button("Egyedi méret…",self.special_edit_custom_size));layout_row.addStretch();box.addLayout(layout_row)
        toolbar=QHBoxLayout();toolbar.setSpacing(5)
        self.special_font=QFontComboBox();self.special_font.setCurrentFont(QFont(self.store.setting("special_font","Segoe UI")))
        self.special_font.currentFontChanged.connect(self.special_set_font);toolbar.addWidget(self.special_font)
        self.special_size=QDoubleSpinBox();self.special_size.setRange(6,60);self.special_size.setValue(16);self.special_size.setSuffix(" pt")
        self.special_size.valueChanged.connect(self.special_set_size);toolbar.addWidget(self.special_size)
        for label,attribute in (("B","bold"),("I","italic"),("U","underline")):
            control=QPushButton(label);control.setCheckable(True);control.setFixedWidth(38)
            if label=="B":control.setStyleSheet("font-weight:bold")
            if label=="I":control.setStyleSheet("font-style:italic")
            if label=="U":control.setStyleSheet("text-decoration:underline")
            control.clicked.connect(lambda checked,a=attribute:self.special_set_decoration(a,checked))
            toolbar.addWidget(control)
        toolbar.addWidget(button("Szín",self.special_choose_color))
        toolbar.addWidget(button("Balra",lambda:self.special_text.setAlignment(Qt.AlignmentFlag.AlignLeft)))
        toolbar.addWidget(button("Középre",lambda:self.special_text.setAlignment(Qt.AlignmentFlag.AlignHCenter)))
        toolbar.addWidget(button("Jobbra",lambda:self.special_text.setAlignment(Qt.AlignmentFlag.AlignRight)))
        toolbar.addStretch();box.addLayout(toolbar)
        self.special_text=QTextEdit();self.special_text.setAcceptRichText(True)
        self.special_text.setPlaceholderText("Írd ide a különleges menü vagy esemény szövegét. Jelöld ki a szöveget, majd használd a formázó gombokat.")
        self.special_text.setHtml(self.store.setting("special_html","") or "")
        self.special_text.textChanged.connect(self.special_content_changed)
        box.addWidget(self.special_text,1)

    def special_changed(self,*_):
        if not hasattr(self,"special_title_edit"):return
        self.store.set_settings({"special_title":self.special_title_edit.text().strip(),
            "special_show_title":"1" if self.special_show_title.isChecked() else "0",
            "special_show_date":"1" if self.special_show_date.isChecked() else "0",
            "special_show_footer":"1" if self.special_show_footer.isChecked() else "0",
            "special_footer_note":self.special_footer_note.text().strip(),
            "special_header_mode":str(self.special_header_mode.currentData() or "full")})
        self.preview_archive=None;self.schedule_preview()

    def special_apply_size_preset(self,index):
        if self._updating_special_size:return
        size=self.special_size_preset.itemData(index)
        if not size:return
        self._updating_special_size=True
        self.special_size_width.setValue(size[0]);self.special_size_height.setValue(size[1])
        self._updating_special_size=False
        self.special_size_changed()

    def special_edit_custom_size(self):
        dialog=QDialog(self);dialog.setWindowTitle("Egyedi kimeneti méret");dialog.setModal(True)
        form=QFormLayout(dialog)
        width=QSpinBox();width.setRange(200,8000);width.setSuffix(" px");width.setValue(self.special_size_width.value())
        height=QSpinBox();height.setRange(200,8000);height.setSuffix(" px");height.setValue(self.special_size_height.value())
        form.addRow("Szélesség",width);form.addRow("Magasság",height)
        controls=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        controls.accepted.connect(dialog.accept);controls.rejected.connect(dialog.reject);form.addRow(controls)
        if dialog.exec()!=QDialog.DialogCode.Accepted:return
        self._updating_special_size=True
        self.special_size_width.setValue(width.value());self.special_size_height.setValue(height.value())
        self._updating_special_size=False
        self.special_size_changed()

    def special_size_changed(self,*_):
        width=self.special_size_width.value();height=self.special_size_height.value()
        if not self._updating_special_size:
            preset_index=next((i for i in range(self.special_size_preset.count()) if self.special_size_preset.itemData(i)==(width,height)),-1)
            self._updating_special_size=True
            if preset_index>=0:self.special_size_preset.setCurrentIndex(preset_index)
            else:
                self.special_size_preset.setCurrentIndex(-1)
                self.special_size_preset.setEditText(f"Egyedi méret · {width} × {height}")
            self._updating_special_size=False
        self.store.set_settings({"special_canvas_width":str(width),"special_canvas_height":str(height)})
        self.preview_archive=None;self.schedule_preview()

    def special_content_changed(self):
        self.store.set_settings({"special_html":self.special_text.toHtml()})
        self.preview_archive=None;self.schedule_preview()

    def special_set_font(self,font):
        fmt=QTextCharFormat();fmt.setFontFamily(font.family());self.special_text.mergeCurrentCharFormat(fmt)

    def special_set_size(self,size):
        fmt=QTextCharFormat();fmt.setFontPointSize(size);self.special_text.mergeCurrentCharFormat(fmt)

    def special_set_decoration(self,attribute,checked):
        fmt=QTextCharFormat()
        if attribute=="bold":fmt.setFontWeight(QFont.Weight.Bold if checked else QFont.Weight.Normal)
        elif attribute=="italic":fmt.setFontItalic(checked)
        else:fmt.setFontUnderline(checked)
        self.special_text.mergeCurrentCharFormat(fmt)

    def special_choose_color(self):
        color=QColorDialog.getColor(QColor("#342f2b"),self,"Szövegszín választása")
        if color.isValid():
            fmt=QTextCharFormat();fmt.setForeground(color);self.special_text.mergeCurrentCharFormat(fmt)

    def build_archive(self):
        dialog=QDialog(self);dialog.setWindowTitle("Korábbi étlapok");dialog.resize(430,620)
        dialog.setModal(False);self.archive_dialog=dialog
        body_layout=QVBoxLayout(dialog);body_layout.setContentsMargins(12,12,12,12)
        self.archive=QTreeWidget();self.archive.setHeaderHidden(True);self.archive.setIndentation(18)
        self.archive.itemClicked.connect(self.preview_saved_menu);self.archive.itemDoubleClicked.connect(self.edit_saved_menu)
        info=QLabel("Egy kattintás: előnézet · dupla kattintás: szerkesztés")
        info.setStyleSheet("color:#60747d;padding:5px")
        body_layout.addWidget(info);body_layout.addWidget(self.archive,1)
        buttons=QHBoxLayout()
        open_button=button("Megnyitás szerkesztésre",lambda:self.edit_saved_menu(self.archive.currentItem(),0))
        delete_button=button("Törlés",self.delete_saved_menu)
        close_button=button("Bezárás",dialog.close)
        buttons.addWidget(open_button);buttons.addWidget(delete_button);buttons.addStretch();buttons.addWidget(close_button)
        body_layout.addLayout(buttons)

        file_menu=self.menuBar().addMenu("Fájl")
        for label,callback in (("Mentés",self.save_current),("Megnyitás…",self.open_archive_window)):
            action=file_menu.addAction(label);action.triggered.connect(callback)
        file_menu.addSeparator()
        for label,callback in (("Exportálás PDF-be…",lambda:self.export("pdf")),("Exportálás képként…",lambda:self.export("png"))):
            action=file_menu.addAction(label);action.triggered.connect(callback)
        file_menu.addSeparator();action=file_menu.addAction("Kilépés");action.triggered.connect(self.close)
        restaurant_action=QAction("Étterem",self)
        restaurant_action.triggered.connect(lambda:self.database_manager(0));self.menuBar().addAction(restaurant_action)
        dishes_action=QAction("Ételek",self)
        dishes_action.triggered.connect(lambda:self.database_manager(1));self.menuBar().addAction(dishes_action)
        data_action=QAction("Adatok",self)
        data_action.triggered.connect(lambda:self.database_manager(2));self.menuBar().addAction(data_action)
        program_menu=self.menuBar().addMenu("Program")
        action=program_menu.addAction("Frissítések keresése…");action.triggered.connect(self.check_for_updates)
        program_menu.addSeparator()
        action=program_menu.addAction("Névjegy…");action.triggered.connect(self.about_dialog)

    def open_archive_window(self):
        self.refresh_archive();self.archive_dialog.show();self.archive_dialog.raise_();self.archive_dialog.activateWindow()

    def delete_saved_menu(self):
        item=self.archive.currentItem()
        if not item or item.data(0,Qt.ItemDataRole.UserRole) is None:
            QMessageBox.information(self,APP_NAME,"Válassz ki egy mentett étlapot a törléshez.");return
        menu_id=item.data(0,Qt.ItemDataRole.UserRole)
        label=item.text(0).strip()
        if QMessageBox.question(self,"Étlap törlése",f"Biztosan törlöd ezt a mentett étlapot?\n\n{label}",QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No)==QMessageBox.StandardButton.Yes:
            if self.preview_archive is not None:
                archived_day=self.preview_archive[2]
                row=self.store.db.execute("SELECT kind,menu_date FROM saved_menus WHERE id=?",(menu_id,)).fetchone()
                if row and row["kind"]==self.preview_archive[1] and row["menu_date"]==archived_day.isoformat():self.preview_archive=None
            self.store.delete_saved_menu(menu_id);self.refresh_archive();self.schedule_preview()

    def check_for_updates(self):
        if sys.platform!="win32" or not getattr(sys,"frozen",False):
            QMessageBox.information(self,APP_NAME,"Az automatikus frissítés a telepített Windows-verzióban érhető el.")
            return
        try:
            request=Request(GITHUB_LATEST_RELEASE,headers={"Accept":"application/vnd.github+json",
                                                          "User-Agent":"EtlapStudio-Updater"})
            with urlopen(request,timeout=15) as response:release=json.loads(response.read().decode("utf-8"))
            latest=str(release.get("tag_name","")).removeprefix("v")
            parse_version=lambda value:tuple(int(part) for part in value.split(".") if part.isdigit())
            if not latest or parse_version(latest)<=parse_version(APP_VERSION):
                QMessageBox.information(self,APP_NAME,f"A program naprakész (v{APP_VERSION}).")
                return
            asset=next((item for item in release.get("assets",[])
                        if item.get("name")==f"EtlapStudio-Windows-{latest}.zip"),None)
            digest=str(asset.get("digest","")) if asset else ""
            if (not asset or not str(asset.get("browser_download_url","")).startswith(
                    "https://github.com/szokezoltan95/etlapstudio/releases/download/")
                    or not re.fullmatch(r"sha256:[0-9a-fA-F]{64}",digest)):
                QMessageBox.warning(self,APP_NAME,"Ehhez a verzióhoz nem található ellenőrizhető Windows-frissítőcsomag.")
                return
        except Exception as exc:
            QMessageBox.warning(self,APP_NAME,"Nem sikerült ellenőrizni a frissítéseket. Ellenőrizd az internetkapcsolatot.\n\n"+str(exc))
            return
        notes=str(release.get("body","")).strip()
        message=f"Elérhető az ÉtlapStúdió v{latest} verziója (jelenlegi: v{APP_VERSION})."
        if notes:message+="\n\n"+notes[:1800]
        message+="\n\nA frissítő letölti és kicsomagolja az új programfájlokat. A helyi ételadatbázis és éttermi beállítások megmaradnak."
        answer=QMessageBox.question(self,"Frissítés érhető el",message,
                                    QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,
                                    QMessageBox.StandardButton.Yes)
        if answer!=QMessageBox.StandardButton.Yes:return
        helper_source=Path(getattr(sys,"_MEIPASS",BASE))/"EtlapStudioUpdater.exe"
        if not helper_source.is_file():
            QMessageBox.critical(self,APP_NAME,"A frissítőprogram hiányzik ebből a telepítésből. Telepítsd kézzel a legújabb verziót.")
            return
        update_dir=Path(tempfile.mkdtemp(prefix="EtlapStudio-Update-"))
        helper_copy=update_dir/"EtlapStudioUpdater.exe";ready=update_dir/"ready"
        try:
            shutil.copy2(helper_source,helper_copy)
            flags=(getattr(subprocess,"DETACHED_PROCESS",0)|getattr(subprocess,"CREATE_NEW_PROCESS_GROUP",0)|
                   getattr(subprocess,"CREATE_NO_WINDOW",0))
            process=subprocess.Popen([str(helper_copy),asset["browser_download_url"],digest.removeprefix("sha256:"),
                                      str(os.getpid()),str(Path(sys.executable).resolve().parent),
                                      str(Path(sys.executable).resolve()),str(ready)],
                                     cwd=str(update_dir),creationflags=flags,close_fds=True)
            deadline=time.monotonic()+12
            while time.monotonic()<deadline and not ready.exists() and process.poll() is None:
                time.sleep(0.05)
            if not ready.exists():
                if process.poll() is None:process.terminate()
                raise RuntimeError("A frissítő nem tudott biztonságos várakozást indítani.")
        except Exception as exc:
            QMessageBox.critical(self,APP_NAME,"Nem sikerült elindítani a frissítést; a program nem zárult be.\n\n"+str(exc))
            return
        QMessageBox.information(self,APP_NAME,"A program bezárul. A frissítő megvárja a teljes leállást, lecseréli a programfájlokat, majd újraindítja az alkalmazást.\n\nKérjük, várj az újraindulásig.")
        self.close()

    def about_dialog(self):
        dialog=QDialog(self);dialog.setWindowTitle(f"Névjegy – {APP_NAME}");dialog.resize(760,760)
        layout=QVBoxLayout(dialog)
        heading=QLabel(f"<h2>{APP_NAME}</h2><p><b>Verzió:</b> {APP_VERSION}<br><b>Copyright:</b> © 2026 Szőke Zoltán<br><b>Cél:</b> A Megyeháza Étterem napi, heti és alkalmi étlapjainak szerkesztése, mentése és exportálása.</p><p><a href='https://github.com/szokezoltan95/etlapstudio'>GitHub-projektoldal</a> · Forráskód-licenc: MIT</p><hr><b>MIT licenc teljes szövege</b>")
        heading.setOpenExternalLinks(True);layout.addWidget(heading)
        license_text=QTextEdit();license_text.setReadOnly(True);license_text.setPlainText(MIT_LICENSE_TEXT);layout.addWidget(license_text,1)
        note=QLabel("A külső függőségek, betűkészletek és külön licencű mellékelt fájlok saját licencfeltételei ettől függetlenül érvényesek.");note.setWordWrap(True);layout.addWidget(note)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Close);buttons.rejected.connect(dialog.close);layout.addWidget(buttons)
        dialog.exec()

    def build_appearance(self):
        page,box=self.pane("Dizájn · színek, betűtípusok és grafikai elemek")
        self.tabs.addTab(page,"Dizájn")
        scroll=QScrollArea();scroll.setWidgetResizable(True);inner=QWidget();form=QFormLayout(inner)
        self.settings={}
        self.design_kind="daily"
        self.design_type=QComboBox();self.design_type.addItem("Napi étlap","daily");self.design_type.addItem("Heti étlap","weekly");self.design_type.addItem("Különleges alkalom","special")
        form.addRow("Szerkesztett laptípus",self.design_type)
        self.theme=QComboBox();self.theme_keys=[];self.reload_themes()
        self.theme.currentIndexChanged.connect(self.save_appearance);form.addRow("Téma · színek és háttér",self.theme)
        self.text_style_widgets={}
        self.heading_font=QFontComboBox();self.heading_font.setMinimumWidth(220)
        self.heading_font.currentFontChanged.connect(self.save_appearance)
        form.addRow("Címsorok betűtípusa",self.heading_font)
        self.body_font=QFontComboBox();self.body_font.setMinimumWidth(220)
        self.body_font.currentFontChanged.connect(self.save_appearance)
        form.addRow("Sima szöveg betűtípusa",self.body_font)
        self.advanced_button=button("Haladó beállítások…",self.open_advanced_design)
        self.advanced_button.setToolTip("Külön ablakban módosíthatók az egyes szövegtípusok betűi és méretei.")
        form.addRow("Betűméretek",self.advanced_button)
        self.leader=QComboBox()
        for label,value in LEADERS.items():self.leader.addItem(label,value)
        index=self.leader.findData(self.store.setting("leader","none"));self.leader.setCurrentIndex(max(index,0))
        self.leader.currentIndexChanged.connect(self.save_appearance);form.addRow("Étel–ár jelölés",self.leader)
        self.glass=QCheckBox("Félig áttetsző üveghatású panelek az olvashatóságért")
        self.glass.setChecked(self.store.setting("glass_panels","1")=="1")
        self.glass.toggled.connect(self.save_appearance);form.addRow("",self.glass)
        self.glass_color_mode=QComboBox()
        self.glass_color_mode.addItem("Fehér", "white")
        self.glass_color_mode.addItem("Témaszín", "theme")
        self.glass_color_mode.addItem("Egyéni szín", "custom")
        mode=self.store.setting("glass_color_mode","white")
        if mode=="auto":mode="white"
        mode_index=self.glass_color_mode.findData(mode);self.glass_color_mode.setCurrentIndex(max(0,mode_index))
        self.glass_color_mode.currentIndexChanged.connect(self.glass_color_mode_changed)
        form.addRow("Üvegpanelek színe",self.glass_color_mode)
        self.glass_color_button=button("Egyéni szín kiválasztása…",self.choose_glass_color)
        self.glass_color_button.setToolTip("Egyéni panelárnyalat. A finom áttetszőség megőrzi a szöveg olvashatóságát.")
        self._glass_custom_color=self.store.setting("glass_color","#DDE7D8")
        form.addRow("Egyéni panelárnyalat",self.glass_color_button)
        opacity_row=QWidget();opacity_layout=QHBoxLayout(opacity_row);opacity_layout.setContentsMargins(0,0,0,0);opacity_layout.setSpacing(10)
        self.glass_opacity=QSlider(Qt.Orientation.Horizontal);self.glass_opacity.setRange(25,100);self.glass_opacity.setSingleStep(1);self.glass_opacity.setPageStep(5)
        self.glass_opacity.setValue(int(self.store.setting("glass_opacity","80") or "80"))
        self.glass_opacity.setToolTip("Nagyobb értéknél a panel jobban takarja a hátteret, így a szöveg könnyebben olvasható.")
        self.glass_opacity_label=QLabel(f"{self.glass_opacity.value()} %");self.glass_opacity_label.setMinimumWidth(42);self.glass_opacity_label.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter)
        self.glass_opacity.valueChanged.connect(lambda value:self.glass_opacity_label.setText(f"{value} %"))
        self.glass_opacity.valueChanged.connect(self.save_appearance)
        opacity_layout.addWidget(self.glass_opacity,1);opacity_layout.addWidget(self.glass_opacity_label);form.addRow("Panel fedettsége",opacity_row)
        self.decorations=QCheckBox("Áttetsző szezonális elválasztók")
        self.decorations.setChecked(self.store.setting("decorations","1")=="1")
        self.decorations.toggled.connect(self.save_appearance);form.addRow("",self.decorations)
        self.glass_color_mode_changed()
        form.addRow("",button("Dizájnkezelő…",self.new_design_dialog))
        reset=button("Dizájn visszaállítása alapértékre",self.reset_design);reset.setObjectName("resetButton")
        form.addRow("",reset)
        self.design_type.currentIndexChanged.connect(self.change_design_kind)
        scroll.setWidget(inner);box.addWidget(scroll,1)
        # Load saved per-page design, while retaining compatibility with older global settings.
        self.load_design_kind("daily")

    def capture_design_kind(self,kind):
        prefix=kind+"_"
        values={prefix+"theme":self.theme.currentData() or "auto",
                prefix+"auto_theme":"1" if self.theme.currentData()=="auto" else "0",
                prefix+"decorations":"1" if self.decorations.isChecked() else "0",
                prefix+"glass_panels":"1" if self.glass.isChecked() else "0",
                prefix+"leader":self.leader.currentData() or "none",prefix+"font_size_unit":"pt_a4",
                prefix+"font_heading":self.heading_font.currentFont().family(),
                prefix+"font_body":self.body_font.currentFont().family(),
                prefix+"advanced_typography":self.store.setting(prefix+"advanced_typography","0")}
        advanced=getattr(self,"advanced_font_widgets",{})
        if getattr(self,"advanced_design_kind",None)==kind:
            for key,(combo,size) in advanced.items():
                values[prefix+"font_"+key]=combo.currentFont().family()
                values[prefix+"font_size_"+key]=str(size.value())
        values[prefix+"glass_color_mode"]=self.glass_color_mode.currentData() or "auto"
        values[prefix+"glass_color"]=self._glass_custom_color
        values[prefix+"glass_opacity"]=str(self.glass_opacity.value())
        self.store.set_settings(values)

    def glass_color_mode_changed(self,*_):
        if not hasattr(self,"glass_color_button"):return
        self.glass_color_button.setEnabled(self.glass_color_mode.currentData()=="custom")
        self.update_glass_color_button();self.save_appearance()

    def update_glass_color_button(self):
        color=QColor(self._glass_custom_color)
        if color.isValid():
            self.glass_color_button.setStyleSheet(f"background-color:{color.name()}; color:#28332a; border:1px solid #8f998e; padding:8px; border-radius:8px;")

    def choose_glass_color(self):
        color=QColorDialog.getColor(QColor(self._glass_custom_color),self,"Üvegpanelek színe")
        if not color.isValid():return
        self._glass_custom_color=color.name().upper();self.update_glass_color_button();self.save_appearance()

    def load_design_kind(self,kind):
        self.design_kind=kind;prefix=kind+"_"
        theme=self.store.setting(prefix+"theme",self.store.setting("theme","auto"))
        self.theme.blockSignals(True);idx=self.theme.findData(theme);self.theme.setCurrentIndex(max(0,idx));self.theme.blockSignals(False)
        for widget,key,default in ((self.heading_font,"font_heading","Candara"),(self.body_font,"font_body","Segoe UI")):
            family=self.store.setting(prefix+key,self.store.setting(key,default))
            family={"Modern sans":"DejaVu Sans","Klasszikus talpas":"DejaVu Serif"}.get(family,family)
            widget.blockSignals(True);widget.setCurrentFont(QFont(family));widget.blockSignals(False)
        if getattr(self,"advanced_dialog",None) is not None and self.advanced_dialog.isVisible():
            self.populate_advanced_design(kind)
        for widget,key,default in ((self.glass,"glass_panels","1"),(self.decorations,"decorations","1")):
            widget.blockSignals(True);widget.setChecked(self.store.setting(prefix+key,self.store.setting(key,default))=="1");widget.blockSignals(False)
        idx=self.leader.findData(self.store.setting(prefix+"leader",self.store.setting("leader","none")))
        self.leader.blockSignals(True);self.leader.setCurrentIndex(max(0,idx));self.leader.blockSignals(False)
        self.glass_color_mode.blockSignals(True)
        mode=self.store.setting(prefix+"glass_color_mode",self.store.setting("glass_color_mode","white"))
        if mode=="auto":mode="white"
        idx=self.glass_color_mode.findData(mode);self.glass_color_mode.setCurrentIndex(max(0,idx));self.glass_color_mode.blockSignals(False)
        self._glass_custom_color=self.store.setting(prefix+"glass_color",self.store.setting("glass_color","#DDE7D8"))
        self.update_glass_color_button();self.glass_color_button.setEnabled(self.glass_color_mode.currentData()=="custom")
        opacity=self.store.setting(prefix+"glass_opacity",self.store.setting("glass_opacity","80"))
        self.glass_opacity.blockSignals(True);self.glass_opacity.setValue(int(opacity or "80"));self.glass_opacity.blockSignals(False)
        self.glass_opacity_label.setText(f"{self.glass_opacity.value()} %")
        self.schedule_preview()

    def change_design_kind(self,index):
        if not hasattr(self,"heading_font"):return
        old=self.design_kind;self.capture_design_kind(old)
        self.load_design_kind(self.design_type.currentData() or "daily")

    def open_advanced_design(self):
        if getattr(self,"advanced_dialog",None) is None:
            self.advanced_dialog=QDialog(self);self.advanced_dialog.setWindowTitle("Haladó dizájnbeállítások")
            self.advanced_dialog.resize(720,720);layout=QVBoxLayout(self.advanced_dialog)
            self.advanced_enabled=QCheckBox("Egyedi betűméretek és szövegtípusonkénti betűk használata")
            self.advanced_enabled.setToolTip("Kikapcsolva a két egyszerű betűtípus és a beépített alapméretek érvényesülnek.")
            self.advanced_enabled.toggled.connect(self.save_advanced_design);layout.addWidget(self.advanced_enabled)
            scroll=QScrollArea();scroll.setWidgetResizable(True);inner=QWidget();form=QFormLayout(inner)
            self.advanced_font_widgets={}
            for key,label,default_font,default_size,legacy_role in TEXT_STYLES:
                row=QWidget();row_layout=QHBoxLayout(row);row_layout.setContentsMargins(0,0,0,0);row_layout.setSpacing(8)
                combo=QFontComboBox();combo.setMinimumWidth(210)
                size=QDoubleSpinBox();size.setRange(4,48);size.setDecimals(1);size.setSingleStep(.5);size.setSuffix(" pt")
                size.setToolTip("Nyomdai pont. Az ételnevek szükség esetén automatikusan kisebbre méreteződnek.")
                combo.currentFontChanged.connect(self.save_advanced_design);size.valueChanged.connect(self.save_advanced_design)
                row_layout.addWidget(combo,1);row_layout.addWidget(size);form.addRow(label,row)
                self.advanced_font_widgets[key]=(combo,size)
            scroll.setWidget(inner);layout.addWidget(scroll,1)
            controls=QDialogButtonBox(QDialogButtonBox.StandardButton.Close);controls.rejected.connect(self.advanced_dialog.reject);layout.addWidget(controls)
        self.populate_advanced_design(self.design_kind);self.advanced_dialog.show();self.advanced_dialog.raise_();self.advanced_dialog.activateWindow()

    def populate_advanced_design(self,kind):
        prefix=kind+"_";self.advanced_design_kind=kind
        self.advanced_enabled.blockSignals(True);self.advanced_enabled.setChecked(self.store.setting(prefix+"advanced_typography","0")=="1");self.advanced_enabled.blockSignals(False)
        for key,(combo,size) in self.advanced_font_widgets.items():
            definition=next(item for item in TEXT_STYLES if item[0]==key)
            family=self.store.setting(prefix+"font_"+key,self.store.setting("font_"+key,definition[2]))
            combo.blockSignals(True);combo.setCurrentFont(QFont(family));combo.blockSignals(False)
            raw=self.store.setting(prefix+"font_size_"+key,self.store.setting("font_size_"+key))
            try:value=float(raw) if raw else definition[3]
            except (ValueError,TypeError):value=definition[3]
            unit=self.store.setting(prefix+"font_size_unit",self.store.setting("font_size_unit","px"))
            if raw and unit not in ("pt_a4_300","pt_a4"):value*=A4_WIDTH_PT/W
            size.blockSignals(True);size.setValue(value);size.blockSignals(False)

    def save_advanced_design(self,*_):
        if not hasattr(self,"advanced_enabled") or not self.advanced_dialog.isVisible():return
        prefix=self.design_kind+"_";values={prefix+"advanced_typography":"1" if self.advanced_enabled.isChecked() else "0"}
        for key,(combo,size) in self.advanced_font_widgets.items():
            values[prefix+"font_"+key]=combo.currentFont().family();values[prefix+"font_size_"+key]=str(size.value())
        values[prefix+"font_size_unit"]="pt_a4";self.store.set_settings(values);self.schedule_preview()

    def current_day(self):return pydate(self.day.date())
    def current_week(self):return monday(pydate(self.week.date()))

    def refresh_daily(self,*_):
        if not hasattr(self,"search"):return
        self.refresh_food_grid()

    def daily_date_changed(self,qdate_value):
        day=pydate(qdate_value)
        if not self._loading:
            self.preview_archive=None
            self.store.copy_previous_daily(day)
            self._date_change_old=day
        self.refresh_daily();self.refresh_archive()

    def edit_daily_dish(self,dish_id):
        dish=self.store.db.execute("SELECT * FROM dishes WHERE id=? AND active=1",(dish_id,)).fetchone()
        if not dish:return
        selected=next((dict(x) for x in self.store.selection(self.current_day()) if x["id"]==dish_id),None)
        dialog=DailyDishDialog(self,dish,selected)
        if dialog.exec()!=QDialog.DialogCode.Accepted:return
        try:
            self.store.save_daily_dish(self.current_day(),dish_id,int(dialog.regular.text()),
                dialog.include.isChecked(),dialog.promo.isChecked(),int(dialog.promo_amount.text() or "0"))
            saved=any(row["id"]==dish_id for row in self.store.selection(self.current_day()))
            if saved!=dialog.include.isChecked():raise RuntimeError("Az étlap adatbázisa nem igazolta vissza a mentést.")
        except (ValueError,sqlite3.Error,RuntimeError) as exc:
            QMessageBox.warning(self,APP_NAME,"Nem sikerült elmenteni az ételt.\n"+str(exc));return
        self.preview_archive=None;self.refresh_daily();self.refresh_archive()
        self.status.setText("Az étel és az ár elmentve.")

    def refresh_week(self):
        if not hasattr(self,"week_fields"):return
        mon=self.current_week();self._loading=True
        if self.week.date()!=qdate(mon):self.week.setDate(qdate(mon))
        for i,group in enumerate(self.week_fields):
            day=mon+timedelta(days=i)
            for widget,value in zip(group,self.store.week_entry(day)):widget.setText(value)
            closed,note=self.store.week_entry_state(day)
            self.week_closed[i].setChecked(closed);self.week_closure_notes[i].setText(note)
            self.update_week_day_visibility(i)
        self._loading=False;self._week_loaded_monday=mon

    def change_week(self):
        if getattr(self,"week_save_timer",None) and self.week_save_timer.isActive():
            self.week_save_timer.stop();self.persist_week_entries()
        self.refresh_week()

    def update_week_day_visibility(self,index):
        closed=self.week_closed[index].isChecked()
        for label,edit in zip(self.week_field_labels[index],self.week_fields[index]):
            label.setVisible(not closed);edit.setVisible(not closed)
        self.week_closure_labels[index].setVisible(closed)
        self.week_closure_notes[index].setVisible(closed)

    def schedule_week_save(self):
        if self._loading:return
        self.preview_archive=None
        for i in range(len(self.week_fields)):self.update_week_day_visibility(i)
        self.week_save_timer.start()

    def persist_week_entries(self):
        if self._loading or not hasattr(self,"week_fields"):return
        base=getattr(self,"_week_loaded_monday",self.current_week())
        for i,group in enumerate(self.week_fields):
            self.store.set_week_entry(base+timedelta(days=i),*(edit.text() for edit in group),
                self.week_closed[i].isChecked(),self.week_closure_notes[i].text())

    def refresh_week_preview(self):
        if self.week_save_timer.isActive():self.week_save_timer.stop()
        self.persist_week_entries()
        self._manual_week_preview=True
        self.timer.stop();self.refresh_preview()

    def save_daily(self):
        self.store.save_menu("daily",self.current_day());self.preview_archive=None;self.refresh_archive()
        QMessageBox.information(self,APP_NAME,"A napi étlap mentve az étlap-adatbázisba.")

    def save_week(self):
        self.week_save_timer.stop();self.persist_week_entries()
        self.store.save_menu("weekly",self.current_week());self.refresh_archive()
        self.preview_archive=None;QMessageBox.information(self,APP_NAME,"A heti menü mentve az étlap-adatbázisba.")

    def save_special(self):
        self.special_content_changed();self.special_changed()
        self.store.save_menu("special",pydate(self.special_date.date()));self.refresh_archive()
        self.preview_archive=None;QMessageBox.information(self,APP_NAME,"A különleges étlap mentve az étlap-adatbázisba.")

    def save_current(self):
        if self.preview_archive is not None:
            self.edit_saved_menu(self.archive.currentItem(),0);return
        if self.tabs.currentIndex()==1:self.save_week()
        elif self.tabs.currentIndex()==2:self.save_special()
        else:self.save_daily()

    def refresh_menu_suggestions(self):
        suggestions=self.store.menu_suggestions()
        for group in self.week_fields:
            for edit in group:edit.completer().model().setStringList(suggestions)

    def import_starter(self):
        count=self.store.import_starter_catalogue()
        self.refresh_daily();self.refresh_menu_suggestions()
        QMessageBox.information(self,APP_NAME,f"{count} hiányzó étel bekerült az adatbázisba.")

    def database_manager(self,initial_tab=0):
        """Central place for restaurant details, dishes, and database import/export."""
        dialog=QDialog(self);dialog.setWindowTitle("Adatbázis kezelő");dialog.resize(900,680)
        layout=QVBoxLayout(dialog);tabs=QTabWidget();layout.addWidget(tabs,1)

        restaurant_page=QWidget();restaurant_layout=QVBoxLayout(restaurant_page)
        restaurant_form=QFormLayout();restaurant_layout.addLayout(restaurant_form)
        details=(
            ("restaurant_name","Étterem neve","Megyeháza Étterem"),
            ("address","Cím","Miskolc, Városház tér 1."),
            ("phone","Telefonszám","+36 30 / 513 2605"),
            ("facebook_url","Facebook link","facebook.com/mhetterem"),
            ("note","Alsó megjegyzés","Az étlapváltoztatás jogát fenntartjuk!"),
        )
        restaurant_fields={}
        for key,label,default in details:
            edit=QLineEdit(self.store.setting(key,default) or default)
            restaurant_fields[key]=edit;restaurant_form.addRow(label,edit)
        menu_price=price_edit(self.store.setting("daily_menu_price","2800") or "2800")
        menu_price.setToolTip("Ez az ár jelenik meg a napi étlapon és a heti étlap fejlécében is.")
        restaurant_form.addRow("Napi menü ára (Ft)",menu_price)
        hint=QLabel("Ezek az adatok az étlapok fejlécében és láblécében jelennek meg.");hint.setWordWrap(True)
        restaurant_layout.addWidget(hint);restaurant_layout.addStretch(1)
        tabs.addTab(restaurant_page,"Étterem adatai")

        dishes_page=QWidget();dishes_layout=QVBoxLayout(dishes_page)
        filter_row=QHBoxLayout();dishes_layout.addLayout(filter_row)
        search=QLineEdit();search.setPlaceholderText("Keresés név szerint…");filter_row.addWidget(search,1)
        category_filter=QComboBox();category_filter.addItem("Minden kategória","")
        for category in CATEGORIES:category_filter.addItem(category,category)
        category_filter.setToolTip("Az étellista szűrése kategória szerint")
        filter_row.addWidget(category_filter)
        tree=QTreeWidget();tree.setHeaderLabels(["Étel","Kategória","Normál ár"]);tree.setAlternatingRowColors(True);tree.setSortingEnabled(True)
        tree.setToolTip("A táblázat oszlopfejléceire kattintva sorba rendezheted a listát.")
        dishes_layout.addWidget(tree,1)
        actions=QHBoxLayout();dishes_layout.addLayout(actions)
        tabs.addTab(dishes_page,"Ételek")

        transfer_page=QWidget();transfer_layout=QVBoxLayout(transfer_page)
        transfer_layout.addWidget(QLabel("Étlapadatbázis biztonsági mentése és az étellista CSV-fájlos cseréje."))
        transfer_layout.addWidget(button("Teljes adatbázis mentése…",self.backup))
        transfer_layout.addWidget(button("Ételek exportálása CSV-be…",lambda:self.export_dishes_csv(dialog)))
        transfer_layout.addWidget(button("Ételek importálása CSV-ből…",lambda:self.import_dishes_csv(dialog)))
        format_hint=QLabel("CSV oszlopok: name, category, price. Az import az azonos nevű és kategóriájú ételek árát frissíti, az újakat hozzáadja.")
        format_hint.setWordWrap(True);transfer_layout.addWidget(format_hint);transfer_layout.addStretch(1)
        tabs.addTab(transfer_page,"Import / export")

        def save_restaurant(*_):
            values={key:field.text().strip() for key,field in restaurant_fields.items()}
            values["daily_menu_price"]=menu_price.text().strip() or "0"
            self.store.set_settings(values);self.schedule_preview()
        for field in restaurant_fields.values():field.textChanged.connect(save_restaurant)
        menu_price.editingFinished.connect(save_restaurant)

        def reload(*_):
            tree.clear()
            for row in self.store.dishes(search.text()):
                if category_filter.currentData() and row["category"]!=category_filter.currentData():continue
                item=DishCatalogItem([row["name"],row["category"],price(row["price"])])
                item.setData(0,Qt.ItemDataRole.UserRole,row["id"]);item.setData(2,Qt.ItemDataRole.UserRole+1,int(row["price"]));tree.addTopLevelItem(item)
        def selected_row():
            item=tree.currentItem()
            return self.store.db.execute("SELECT * FROM dishes WHERE id=?",(item.data(0,Qt.ItemDataRole.UserRole),)).fetchone() if item else None
        def edit(row=None):
            form=DishDialog(dialog,row)
            if form.exec()!=QDialog.DialogCode.Accepted:return
            self.store.add_dish(form.name.text().strip(),form.category.currentText(),int(form.amount.text()),row["id"] if row else None)
            reload();self.refresh_daily();self.refresh_menu_suggestions()
        def delete():
            row=selected_row()
            if row and QMessageBox.question(dialog,APP_NAME,"Eltávolítsuk ezt az ételt az aktív ételadatbázisból?")==QMessageBox.StandardButton.Yes:
                self.store.delete_dish(row["id"]);reload();self.refresh_daily();self.refresh_menu_suggestions()
        actions.addWidget(button("Új étel",lambda:edit()))
        actions.addWidget(button("Szerkesztés",lambda:edit(selected_row())))
        actions.addWidget(button("Eltávolítás",delete));actions.addStretch()
        actions.addWidget(button("Hiányzó alapételek betöltése",self.import_starter))
        search.textChanged.connect(reload);category_filter.currentIndexChanged.connect(reload);tree.itemDoubleClicked.connect(lambda *_:edit(selected_row()))
        tabs.setCurrentIndex(max(0,min(2,int(initial_tab))));reload();dialog.exec()

    def catalog_manager(self):
        # Backward-compatible entry point used by older UI actions.
        self.database_manager()

    def export_dishes_csv(self,parent):
        path,_=QFileDialog.getSaveFileName(parent,"Ételek exportálása","etelek.csv","CSV (*.csv)")
        if not path:return
        try:
            with open(path,"w",newline="",encoding="utf-8-sig") as handle:
                writer=csv.writer(handle,delimiter=";");writer.writerow(["name","category","price"])
                for row in self.store.dishes():writer.writerow([row["name"],row["category"],row["price"]])
            QMessageBox.information(parent,APP_NAME,"Az étellista exportálása elkészült.")
        except Exception as exc:QMessageBox.warning(parent,APP_NAME,f"Az export nem sikerült:\n{exc}")

    def import_dishes_csv(self,parent):
        path,_=QFileDialog.getOpenFileName(parent,"Ételek importálása","","CSV (*.csv);;Minden fájl (*)")
        if not path:return
        try:
            with open(path,"r",newline="",encoding="utf-8-sig") as handle:
                sample=handle.read(4096);handle.seek(0)
                try:delimiter=csv.Sniffer().sniff(sample,delimiters=";,\t").delimiter
                except csv.Error:delimiter=";"
                reader=csv.DictReader(handle,delimiter=delimiter)
                if not reader.fieldnames or not {"name","category","price"}.issubset(set(reader.fieldnames)):
                    raise ValueError("A fejlécnek ezeket az oszlopokat kell tartalmaznia: name, category, price.")
                existing={(row["name"].strip().casefold(),row["category"].strip().casefold()):row for row in self.store.dishes()}
                imported=[]
                for line,row in enumerate(reader,2):
                    name=(row.get("name") or "").strip();category=(row.get("category") or "").strip()
                    if not name:continue
                    amount=int((row.get("price") or "").strip())
                    if amount<0:raise ValueError(f"A(z) {line}. soron az ár nem lehet negatív.")
                    if category not in CATEGORIES:raise ValueError(f"A(z) {line}. sor kategóriája ismeretlen: {category}")
                    imported.append((name,category,amount))
            inserted=updated=0
            with self.store.db:
                for name,category,amount in imported:
                    match=existing.get((name.casefold(),category.casefold()))
                    self.store.add_dish(name,category,amount,match["id"] if match else None)
                    if match:updated+=1
                    else:
                        inserted+=1
                        fresh=self.store.db.execute("SELECT * FROM dishes WHERE id=last_insert_rowid()").fetchone()
                        existing[(name.casefold(),category.casefold())]=fresh
            self.refresh_daily();self.refresh_menu_suggestions()
            QMessageBox.information(parent,APP_NAME,f"Import kész. Új étel: {inserted}, frissített étel: {updated}.")
        except Exception as exc:QMessageBox.warning(parent,APP_NAME,f"Az import nem sikerült:\n{exc}")

    def refresh_archive(self):
        if not hasattr(self,"archive"):return
        self.archive.clear();groups={}
        for row in self.store.saved_menus():
            day=date.fromisoformat(row["menu_date"]);week=monday(day)
            key=week.isoformat()
            if key not in groups:
                group=QTreeWidgetItem([f"{week:%Y.%m.%d.} – {(week+timedelta(days=6)):%m.%d.}"])
                group.setData(0,Qt.ItemDataRole.UserRole,None);self.archive.addTopLevelItem(group);groups[key]=group
            label={"daily":"📅  ","weekly":"🗓  ","special":"✦  "}[row["kind"]]+day.strftime("%Y.%m.%d.")
            item=QTreeWidgetItem([label]);item.setData(0,Qt.ItemDataRole.UserRole,row["id"])
            item.setData(0,Qt.ItemDataRole.UserRole+1,row["kind"]);item.setToolTip(0,"Dupla kattintással megnyitás szerkesztésre")
            groups[key].addChild(item)
        self.archive.expandAll()


    def preview_saved_menu(self,item,column=0):
        if not item or item.data(0,Qt.ItemDataRole.UserRole) is None:return
        row,definition=self.store.saved_menu(item.data(0,Qt.ItemDataRole.UserRole))
        self.preview_archive=(ArchivedMenu(row["kind"],date.fromisoformat(row["menu_date"]),definition),row["kind"],date.fromisoformat(row["menu_date"]))
        self.schedule_preview()

    def edit_saved_menu(self,item,column=0):
        if not item or item.data(0,Qt.ItemDataRole.UserRole) is None:return
        row,definition=self.store.saved_menu(item.data(0,Qt.ItemDataRole.UserRole));day=date.fromisoformat(row["menu_date"])
        self.preview_archive=None
        if row["kind"]=="weekly":self.tabs.setCurrentIndex(1);self.week.setDate(qdate(day))
        elif row["kind"]=="special":
            self.tabs.setCurrentIndex(2);self.special_date.setDate(qdate(day))
            values=definition.get("settings",{})
            settings={key:values.get(key,"") for key in ("special_title","special_html","special_show_title","special_show_date")}
            settings["special_show_footer"]=values.get("special_show_footer","1")
            settings["special_footer_note"]=values.get("special_footer_note",self.store.setting("note","Az étlapváltoztatás jogát fenntartjuk!"))
            settings["special_canvas_width"]=values.get("special_canvas_width",self.store.setting("special_canvas_width","1240"))
            settings["special_canvas_height"]=values.get("special_canvas_height",self.store.setting("special_canvas_height","1754"))
            settings["special_header_mode"]=values.get("special_header_mode","full")
            self.store.set_settings(settings)
            self.special_title_edit.blockSignals(True);self.special_title_edit.setText(values.get("special_title",""));self.special_title_edit.blockSignals(False)
            self.special_show_title.setChecked(values.get("special_show_title","0")=="1")
            self.special_show_date.setChecked(values.get("special_show_date","0")=="1")
            self.special_show_footer.setChecked(values.get("special_show_footer","1")=="1")
            self.special_header_mode.blockSignals(True)
            header_index=self.special_header_mode.findData(values.get("special_header_mode","full"))
            self.special_header_mode.setCurrentIndex(header_index if header_index>=0 else 0)
            self.special_header_mode.blockSignals(False)
            self.special_footer_note.setText(values.get("special_footer_note",self.store.setting("note","Az étlapváltoztatás jogát fenntartjuk!")))
            self.special_text.blockSignals(True);self.special_text.setHtml(values.get("special_html",""));self.special_text.blockSignals(False)
            self._updating_special_size=True
            self.special_size_width.setValue(int(settings["special_canvas_width"] or "1240"))
            self.special_size_height.setValue(int(settings["special_canvas_height"] or "1754"))
            self._updating_special_size=False
            self.special_size_changed()
            self.special_changed()
            self.schedule_preview()
        else:self.tabs.setCurrentIndex(0);self.day.setDate(qdate(day))

    def reload_themes(self):
        self.theme_packs=load_themes(BASE/"themes_builtin",data_dir()/"themes")
        self.theme.blockSignals(True)
        self.theme.clear();self.theme.addItem("Automatikus évszakos téma · színek + háttér","auto");self.theme_keys=["auto",*self.theme_packs]
        for key in self.theme_keys:
            self.theme.addItem("Automatikus évszakos téma · színek + háttér" if key=="auto" else self.theme_packs[key][0]["name"],key)
        for key,label in (("valentine","Valentin-nap · szív motívum"),("august20","Augusztus 20. · nemzeti színek")):
            if key not in self.theme_keys:self.theme_keys.append(key);self.theme.addItem(label,key)
        prefix=getattr(self,"design_kind","daily")+"_"
        chosen=self.store.setting(prefix+"theme",self.store.setting("theme","auto"))
        default_theme=chosen if chosen!="" else "auto"
        index=self.theme.findData(default_theme);self.theme.setCurrentIndex(max(index,0))
        self.theme.blockSignals(False)

    def save_appearance(self,*_):
        if not hasattr(self,"glass"):return
        if hasattr(self,"text_style_widgets"):self.capture_design_kind(getattr(self,"design_kind","daily"))
        self.schedule_preview()

    def reset_design(self):
        with self.store.db:
            self.store.db.execute("DELETE FROM settings WHERE (key LIKE 'guide_%' AND key!='guide_layout_version') OR key LIKE 'layout_%'")
        defaults={"theme":"auto","auto_theme":"1","decorations":"1","glass_panels":"1",
                  "glass_color_mode":"white","glass_color":"#DDE7D8","glass_opacity":"80",
                  "background_path":"","leader":"none","theme_primary":"","theme_accent":"","font_size_unit":"pt_a4",
                  "font_title":"Candara","font_heading":"Candara","font_body":"Segoe UI","font_special":"Segoe UI","font_dish":"Segoe UI","advanced_typography":"0",
                  "guide_layout_version":"9"}
        for key,_,family,size,_legacy in TEXT_STYLES:
            defaults["font_"+key]=family;defaults["font_size_"+key]=str(size)
        for kind in ("daily","weekly","special"):
            for key,value in list(defaults.items()):
                if key.startswith(("font_","font_size_","theme","auto_theme","decorations","glass_panels","glass_color_mode","glass_color","glass_opacity","leader")) or key=="advanced_typography":
                    defaults[kind+"_"+key]=value
        self.store.set_settings(defaults)
        self.theme.blockSignals(True);idx=self.theme.findData("auto");self.theme.setCurrentIndex(max(0,idx));self.theme.blockSignals(False)
        self.heading_font.setCurrentFont(QFont("Candara"));self.body_font.setCurrentFont(QFont("Segoe UI"))
        if getattr(self,"advanced_dialog",None) is not None:self.populate_advanced_design(self.design_kind)
        self.glass.setChecked(True);self.decorations.setChecked(True)
        self.glass_color_mode.blockSignals(True);self.glass_color_mode.setCurrentIndex(self.glass_color_mode.findData("white"));self.glass_color_mode.blockSignals(False)
        self._glass_custom_color="#DDE7D8";self.update_glass_color_button();self.glass_color_button.setEnabled(False)
        self.glass_opacity.setValue(80)
        idx=self.leader.findData("none");self.leader.setCurrentIndex(max(0,idx))
        self.update_guides()
        for kind in ("daily","weekly","special"):self.capture_design_kind(kind)
        self.schedule_preview()

    def new_design_dialog(self):
        dialog=QDialog(self);dialog.setWindowTitle("Dizájnkezelő")
        dialog.resize(900,720);layout=QVBoxLayout(dialog)
        tabs=QTabWidget();layout.addWidget(tabs,1)

        manage=QWidget();manage_layout=QHBoxLayout(manage);tabs.addTab(manage,"Meglévő dizájnok")
        designs=QListWidget();designs.setMinimumWidth(240);manage_layout.addWidget(designs)
        detail=QWidget();detail_layout=QVBoxLayout(detail);manage_layout.addWidget(detail,1)
        form=QFormLayout();detail_layout.addLayout(form)
        name=QLineEdit();form.addRow("Dizájn neve",name)
        occasion=QLineEdit();form.addRow("Alkalom",occasion)
        status=QLabel("Válassz egy dizájnt a listából.");status.setWordWrap(True);detail_layout.addWidget(status)
        controls=QHBoxLayout();detail_layout.addLayout(controls)
        apply_button=button("Alkalmazás",lambda:None);controls.addWidget(apply_button)
        save_button=button("Név és alkalom mentése",lambda:None);controls.addWidget(save_button)
        replace_button=button("Grafikák cseréje…",lambda:None);controls.addWidget(replace_button)
        delete_button=button("Törlés",lambda:None);controls.addWidget(delete_button)

        create=QWidget();create_layout=QVBoxLayout(create);tabs.addTab(create,"Új dizájn és import")
        create_form=QFormLayout();create_layout.addLayout(create_form)
        name.setText("Új ünnepi téma")
        prompt_name=QLineEdit("Új ünnepi téma");create_form.addRow("Új dizájn neve",prompt_name)
        prompt_occasion=QComboBox();prompt_occasion.setEditable(True)
        prompt_occasion.addItems(["Valentin-nap","Augusztus 20.","Anyák napja","Szüreti időszak","Helyi rendezvény","Egyéb alkalom"])
        prompt_occasion.setCurrentText("");prompt_occasion.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        create_form.addRow("Milyen alkalomra?",prompt_occasion)
        help_text=QLabel("A promptot másold tetszőleges AI-modellbe. Témacsomagot ZIP-ből vagy külön képfájlokból is importálhatsz.")
        help_text.setWordWrap(True);create_layout.addWidget(help_text)
        prompt=QTextEdit();prompt.setReadOnly(True);create_layout.addWidget(prompt,1)
        def make_prompt(*_):
            event=prompt_occasion.currentText().strip() or "[az alkalom neve]"
            title=prompt_name.text().strip() or "[a dizájn neve]"
            prompt.setPlainText(
                f"Készíts új, nyomtatható étlaphoz illő vizuális témát: {title}, alkalom: {event}. "
                "Az összhatás legyen ízléses, jól olvasható és az alkalomhoz illő. A lap szélein legyenek visszafogott, de jól "
                "érzékelhető díszítő motívumok, természetesen az alkalomhoz illő stílusban és színekkel. "
                "A motívumok ne alkossanak keretet, és ne nyúljanak be zavaróan az ételszöveg területére. Kerüld a túl nagy, "
                "túl részletgazdag vagy erős, vastag vonalú grafikákat; a középső terület maradjon jól olvasható. "
                "Ne tegyél feliratot, ételnevet, logót vagy vízjelet a grafikákra. "
                "Készíts egy 1440 × 2037 px-es, álló background.png hátteret és öt egymástól jól megkülönböztethető, "
                "1800 × 120 px-es, finom line-art elválasztót: divider_1.png, divider_2.png, divider_3.png, divider_4.png és divider_5.png. "
                "MIND AZ ÖT ELVÁLASZTÓ KÜLÖN KÉPFÁJL LEGYEN: ne tedd őket egy közös képre, kontaktlapra vagy rácsba, "
                "és ne adj előnézeti montázst. Mindegyik önálló, vízszintes, átlátszó hátterű PNG legyen; a motívum finom, "
                "vékony vonalas, az alkalomra utaló, és középen hagyjon tiszta helyet. "
                "A program a külön képeket automatikusan PNG-vé alakítja és megfelelő vászonra illeszti. "
                "Ha valódi ZIP-archívumot tudsz készíteni, abba tedd a background.png, divider.png (az első változat), "
                "divider_1.png–divider_5.png és manifest.json fájlokat közvetlenül a ZIP gyökerébe, almappák nélkül. "
                'A manifest legyen UTF-8 JSON ilyen szerkezettel: {"schema_version":1,"id":"tema_azonosito",'
                '"name":"Dizájn neve","occasion":"Alkalom neve",'
                '"palette":{"primary":"#526044","accent":"#B85A42","background":"#F1E9D7"},'
                '"assets":{"divider":"divider.png","background":"background.png"},'
                '"divider_variants":["divider_1.png","divider_2.png","divider_3.png","divider_4.png","divider_5.png"]}. '
                "Ne adj át ZIP-nek nevezett mappát vagy szöveges fájllistát archívum helyett. Ha nem tudsz valódi ZIP-et "
                "készíteni, add át a háttérképet és mind az öt elválasztót különálló képfájlként; ne egyetlen képre "
                "összeállított montázsként."
            )
        prompt_occasion.currentTextChanged.connect(make_prompt);prompt_name.textChanged.connect(make_prompt);make_prompt()
        actions=QHBoxLayout();create_layout.addLayout(actions)
        copy=button("Prompt másolása",lambda:QApplication.clipboard().setText(prompt.toPlainText()));actions.addWidget(copy)
        zip_button=button("Importálás ZIP-ből…",lambda:self.import_theme_from_dialog(dialog));actions.addWidget(zip_button)
        image_button=button("Képek külön importálása…",lambda:self.import_theme_images_from_dialog(dialog,prompt_name.text().strip(),prompt_occasion.currentText().strip()));actions.addWidget(image_button)

        def refresh_designs(select=None):
            self.reload_themes();designs.clear()
            designs.addItem(QListWidgetItem("Automatikus évszakos téma"));designs.item(0).setData(Qt.ItemDataRole.UserRole,"auto")
            for key in self.theme_keys:
                if key=="auto":continue
                label=self.theme_packs[key][0].get("name",key) if key in self.theme_packs else self.theme.itemText(self.theme.findData(key))
                item=QListWidgetItem(label);item.setData(Qt.ItemDataRole.UserRole,key);designs.addItem(item)
            wanted=select or self.theme.currentData() or "auto"
            for i in range(designs.count()):
                if designs.item(i).data(Qt.ItemDataRole.UserRole)==wanted:
                    designs.setCurrentRow(i);return
            designs.setCurrentRow(0)

        def selected_design():
            item=designs.currentItem()
            return item.data(Qt.ItemDataRole.UserRole) if item else None

        def populate_design(*_):
            key=selected_design()
            custom=bool(key in self.theme_packs and (data_dir()/"themes"/key).is_dir())
            if key in self.theme_packs:
                manifest=self.theme_packs[key][0]
                name.setText(manifest.get("name",key));occasion.setText(manifest.get("occasion",""))
                status.setText("Saját dizájn: a nevet, alkalmat és a törlést itt kezelheted." if custom else "Beépített dizájn: megtekinthető és alkalmazható, de az eredeti fájlok nem módosíthatók.")
            else:
                label=self.theme.itemText(self.theme.findData(key)) if key else "Automatikus évszakos téma"
                name.setText(label);occasion.clear()
                status.setText("A program dátum alapján választ évszakos dizájnt." if key=="auto" else "Beépített dizájn: megtekinthető és alkalmazható, de az eredeti fájlok nem módosíthatók.")
            save_button.setEnabled(custom);delete_button.setEnabled(custom)
            replace_button.setEnabled(custom)
            apply_button.setEnabled(bool(key))

        def apply_design():
            key=selected_design()
            if not key:return
            idx=self.theme.findData(key)
            if idx>=0:
                self.theme.setCurrentIndex(idx);self.save_appearance()
            dialog.accept()

        def save_design_metadata():
            key=selected_design()
            if key not in self.theme_packs or not (data_dir()/"themes"/key).is_dir():return
            title=name.text().strip()
            if not title:
                QMessageBox.information(dialog,"Hiányzó név","A dizájn neve nem lehet üres.");return
            manifest,folder=self.theme_packs[key]
            manifest["name"]=title[:60];manifest["occasion"]=occasion.text().strip()[:100]
            (folder/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
            refresh_designs(key)

        def delete_design():
            key=selected_design()
            folder=data_dir()/"themes"/str(key)
            if key not in self.theme_packs or not folder.is_dir():return
            if QMessageBox.question(dialog,"Dizájn törlése",f"Biztosan törlöd ezt a dizájnt: {name.text()}?")!=QMessageBox.StandardButton.Yes:return
            import shutil
            shutil.rmtree(folder)
            for kind in ("daily","weekly","special"):
                if self.store.setting(kind+"_theme")==key:self.store.set_settings({kind+"_theme":"auto",kind+"_auto_theme":"1"})
            refresh_designs("auto");self.schedule_preview()

        def replace_design_assets():
            key=selected_design()
            target=data_dir()/"themes"/str(key)
            if key not in self.theme_packs or not target.is_dir():return
            from tempfile import TemporaryDirectory
            import shutil
            mode=QMessageBox.question(dialog,"Grafikák cseréje", "ZIP-témacsomagot szeretnél választani?\n\nIgen: ZIP · Nem: külön képfájlok",QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No|QMessageBox.StandardButton.Cancel)
            if mode==QMessageBox.StandardButton.Cancel:return
            try:
                with TemporaryDirectory(prefix="etlap-theme-edit-") as tmp:
                    staging=Path(tmp)/"themes";staging.mkdir()
                    if mode==QMessageBox.StandardButton.Yes:
                        path,_=QFileDialog.getOpenFileName(dialog,"Új témacsomag kiválasztása","","ZIP-témacsomag (*.zip)")
                        if not path:return
                        staged_slug=import_theme(Path(path),staging,set())
                    else:
                        background,_=QFileDialog.getOpenFileName(dialog,"Új háttérkép kiválasztása","","Képfájlok (*.png *.jpg *.jpeg *.webp *.bmp)")
                        if not background:return
                        dividers,_=QFileDialog.getOpenFileNames(dialog,"Válassz 1–5 új elválasztóképet","","Képfájlok (*.png *.jpg *.jpeg *.webp *.bmp)")
                        if not dividers:return
                        staged_slug=import_theme_images(Path(background),[Path(x) for x in dividers],name.text().strip(),occasion.text().strip(),staging,set())
                    staged=staging/staged_slug
                    replacement=json.loads((staged/"manifest.json").read_text(encoding="utf-8"))
                    current=json.loads((target/"manifest.json").read_text(encoding="utf-8"))
                    for filename in {*current.get("assets",{}).values(),*current.get("divider_variants",[])}:
                        old=target/filename
                        if old.is_file():old.unlink()
                    for filename in {*replacement.get("assets",{}).values(),*replacement.get("divider_variants",[])}:
                        shutil.copy2(staged/filename,target/filename)
                    replacement["id"]=key;replacement["name"]=name.text().strip()[:60]
                    replacement["occasion"]=occasion.text().strip()[:100]
                    (target/"manifest.json").write_text(json.dumps(replacement,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
                refresh_designs(key);self.schedule_preview()
                QMessageBox.information(dialog,"Dizájn frissítve","A kiválasztott dizájn grafikái frissültek.")
            except Exception as exc:
                QMessageBox.warning(dialog,APP_NAME,f"A grafikákat nem sikerült lecserélni.\n\nRészletek: {exc}")

        apply_button.clicked.connect(apply_design);save_button.clicked.connect(save_design_metadata)
        replace_button.clicked.connect(replace_design_assets)
        delete_button.clicked.connect(delete_design);designs.currentRowChanged.connect(populate_design)
        refresh_designs();populate_design()
        dialog.refresh_designs=refresh_designs
        close=button("Bezárás",dialog.accept);layout.addWidget(close)
        dialog.exec()

    def activate_imported_theme(self,slug):
        prefix=self.design_kind+"_"
        self.store.set_settings({prefix+"theme":slug,prefix+"auto_theme":"0",prefix+"theme_primary":"",prefix+"theme_accent":""})
        self.reload_themes();self.schedule_preview()

    def import_theme_from_dialog(self,parent_dialog=None):
        path,_=QFileDialog.getOpenFileName(parent_dialog or self,"Témacsomag betöltése","","ZIP-témacsomag (*.zip)")
        if not path:return
        try:
            slug=import_theme(Path(path),data_dir()/"themes",set(self.theme_packs))
            self.activate_imported_theme(slug)
            if parent_dialog and hasattr(parent_dialog,"refresh_designs"):parent_dialog.refresh_designs(slug)
            QMessageBox.information(parent_dialog or self,APP_NAME,"A téma sikeresen betöltődött és ki van választva az aktuális laptípushoz.")
        except Exception as exc:
            QMessageBox.warning(parent_dialog or self,APP_NAME,f"A ZIP-témacsomag nem tölthető be. Ellenőrizd a Témacsomag formátuma leírást, vagy válaszd külön a képfájlokat.\n\nRészletek: {exc}")

    def import_theme_images_from_dialog(self,parent_dialog,name,occasion):
        if not name:
            QMessageBox.information(parent_dialog,"Dizájn neve hiányzik","Adj nevet az új dizájnnak.");return
        background,_=QFileDialog.getOpenFileName(parent_dialog,"Háttérkép kiválasztása","","Képfájlok (*.png *.jpg *.jpeg *.webp *.bmp)")
        if not background:return
        dividers,_=QFileDialog.getOpenFileNames(parent_dialog,"Válassz 1–5 elválasztóképet","","Képfájlok (*.png *.jpg *.jpeg *.webp *.bmp)")
        if not dividers:return
        try:
            slug=import_theme_images(Path(background),[Path(x) for x in dividers],name,occasion,data_dir()/"themes",set(self.theme_packs))
            self.activate_imported_theme(slug)
            if parent_dialog and hasattr(parent_dialog,"refresh_designs"):parent_dialog.refresh_designs(slug)
            QMessageBox.information(parent_dialog,APP_NAME,"A képek beolvasása sikerült. A program létrehozta a témacsomagot, elválasztókat dátum szerint váltogat, és a dizájnt kiválasztotta az aktuális laptípushoz.")
        except Exception as exc:
            QMessageBox.warning(parent_dialog,APP_NAME,f"A képekből nem sikerült témát készíteni. Próbálj másik képfájlt, vagy használj témacsomag-ZIP-et.\n\nRészletek: {exc}")

    def import_theme(self):
        self.import_theme_from_dialog(self)

    def save_settings(self):
        if not hasattr(self,"settings") or not self.settings:return
        self.store.set_settings({key:edit.text().strip() for key,edit in self.settings.items()})
        self.schedule_preview()
    def backup(self):
        path,_=QFileDialog.getSaveFileName(self,"Adatbázis mentése","etlapstudio-mentes.sqlite3","SQLite (*.sqlite3)")
        if path:
            with sqlite3.connect(path) as destination:self.store.db.backup(destination)

    def on_tab(self,index):
        if hasattr(self,"tab_date_controls"):
            if index in (0,1):
                self.tab_date_controls.setCurrentIndex(index);self.tab_date_controls.setVisible(True)
            else:self.tab_date_controls.setVisible(False)
        self.preview_archive=None
        if index==1:
            self.refresh_week_preview()
        else:
            self.schedule_preview()
        self.update_guides()

    def update_guides(self,*_):
        if not hasattr(self,"preview"):return
        self.preview.set_guides(False,{})

    def save_layout_region(self,name,y):
        keys={"Fejléc vége":"header","Heti menü kezdete":"days","Napi menü vége":"menu_end"}
        kind="weekly" if self.tabs.currentIndex()==1 else "daily"
        header=int(self.store.setting(f"guide_{kind}_header","205"));shift=header-205
        saved_y=y if name=="Fejléc vége" else y-shift
        self.store.set_settings({f"guide_{kind}_{keys[name]}":str(saved_y)})
        self.update_guides();self.schedule_preview()
    def preview_source(self):
        index=self.tabs.currentIndex()
        if index==3:
            kind=getattr(self,"design_kind","daily")
            if kind=="weekly":return self.store,"weekly",self.current_week()
            if kind=="special":return self.store,"special",pydate(self.special_date.date())
            return self.store,"daily",self.current_day()
        if index==1:return self.store,"weekly",self.current_week()
        if index==2:return self.store,"special",pydate(self.special_date.date())
        if self.preview_archive is not None:return self.preview_archive
        return self.store,"daily",self.current_day()
    def schedule_preview(self):
        if not hasattr(self,"preview"):return
        if hasattr(self,"tabs") and self.tabs.currentIndex()==1:return
        self.timer.start(180)
    def refresh_preview(self):
        if self.tabs.currentIndex()==1 and not self._manual_week_preview:return
        self._manual_week_preview=False
        try:
            source,kind,target=self.preview_source()
            image=render_image(source,kind,target)
            self._image=image
            self.preview_title.setText(("Napi étlap" if kind=="daily" else "Heti menü" if kind=="weekly" else "Különleges étlap")+" · "+display_date(target)+(" · mentett előnézet" if self.preview_archive else ""))
            self.fit_preview();self.status.setText("A4 álló · 150 dpi · PDF és Facebook PNG")
        except Exception as exc:self.status.setText("Előnézeti hiba: "+str(exc))
    def preview_zoom_mode_changed(self,index):
        manual=index==2
        self.manual_preview_zoom=1.0
        if hasattr(self,"zoom_out_button"):
            self.zoom_out_button.setVisible(manual);self.zoom_in_button.setVisible(manual)
        if hasattr(self,"scroll"):
            self.scroll.setHorizontalScrollBarPolicy(
                Qt.ScrollBarPolicy.ScrollBarAsNeeded if manual else Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        if hasattr(self,"preview"):self.preview.set_manual_pan_zoom(manual)
        self.fit_preview()
    def fit_preview(self):
        if self._image is None:return
        viewport=self.scroll.viewport()
        available_width=viewport.width()-24
        mode=self.zoom.currentIndex()
        if mode==0:
            available_width=min(available_width,(viewport.height()-24)*self._image.width()/max(1,self._image.height()))
        base_width=max(180,min(1000,int(available_width)))
        if mode==2:
            width=max(180,min(4000,round(base_width*self.manual_preview_zoom)))
        else:width=base_width
        self.preview.setPixmap(QPixmap.fromImage(self._image).scaledToWidth(width,Qt.TransformationMode.SmoothTransformation))
        self.preview.adjustSize()
    def zoom_preview_at(self,delta,position):
        if self.zoom.currentIndex()!=2:return
        self._apply_preview_zoom(1.15**(delta/120),position)
    def zoom_preview_step(self,multiplier):
        if self.zoom.currentIndex()!=2 or self._image is None:return
        viewport=self.scroll.viewport()
        anchor=QPoint(viewport.width()//2,viewport.height()//2)
        position=self.preview.mapFrom(viewport,anchor)
        position.setX(max(0,min(self.preview.width(),position.x())))
        position.setY(max(0,min(self.preview.height(),position.y())))
        self._apply_preview_zoom(multiplier,position,anchor)
    def _apply_preview_zoom(self,multiplier,position,viewport_position=None):
        if self.zoom.currentIndex()!=2 or self._image is None:return
        old_width=max(1,self.preview.width())
        if viewport_position is None:
            viewport_position=self.preview.mapTo(self.scroll.viewport(),position)
        self.manual_preview_zoom=max(.2,min(5.0,self.manual_preview_zoom*multiplier))
        self.fit_preview()
        ratio=self.preview.width()/old_width
        QTimer.singleShot(0,lambda:self._restore_preview_zoom_anchor(position,viewport_position,ratio))
    def _restore_preview_zoom_anchor(self,local_position,viewport_position,ratio):
        if self.zoom.currentIndex()!=2:return
        origin=self.preview.mapTo(self.scroll.viewport(),QPoint(0,0))
        horizontal=self.scroll.horizontalScrollBar()
        vertical=self.scroll.verticalScrollBar()
        horizontal.setValue(horizontal.value()+origin.x()+round(local_position.x()*ratio)-viewport_position.x())
        vertical.setValue(vertical.value()+origin.y()+round(local_position.y()*ratio)-viewport_position.y())
    def pan_preview_by(self,delta):
        if self.zoom.currentIndex()!=2:return
        self.scroll.horizontalScrollBar().setValue(self.scroll.horizontalScrollBar().value()-delta.x())
        self.scroll.verticalScrollBar().setValue(self.scroll.verticalScrollBar().value()-delta.y())
    def eventFilter(self,watched,event):
        if watched is getattr(self,"scroll",None) and event.type()==QEvent.Type.Resize:
            QTimer.singleShot(0,self.fit_preview)
        elif hasattr(self,"scroll") and watched is self.scroll.viewport() and event.type()==QEvent.Type.Resize:
            QTimer.singleShot(0,self.fit_preview)
        return super().eventFilter(watched,event)
    def _apply_initial_splitter_layout(self):
        if self._initial_splitter_layout_done or not hasattr(self,"main_splitter"):return
        width=max(1,self.main_splitter.width());height=max(1,self.main_splitter.height())
        if self.main_splitter.orientation()==Qt.Orientation.Vertical:
            self.main_splitter.setSizes([round(height*.44),round(height*.56)])
        else:
            preview_width=max(round(width*.60),round((self.scroll.viewport().height()-24)*W/H+48))
            preview_width=min(preview_width,round(width*.72))
            self.main_splitter.setSizes([width-preview_width,preview_width])
        self._initial_splitter_layout_done=True
        QTimer.singleShot(0,self.fit_preview)
    def showEvent(self,event):
        super().showEvent(event)
        QTimer.singleShot(80,self._apply_initial_splitter_layout)
        QTimer.singleShot(100,self.fit_preview)
    def resizeEvent(self,event):
        super().resizeEvent(event)
        if hasattr(self,"preview"):
            QTimer.singleShot(60,self.fit_preview)
            if hasattr(self,"food_grid"):
                self._responsive_timer.start()
            if hasattr(self,"main_splitter"):
                orientation=Qt.Orientation.Vertical if self.width()<1050 and self.height()>800 else Qt.Orientation.Horizontal
                if orientation!=self._responsive_orientation:
                    self._responsive_orientation=orientation;self.main_splitter.setOrientation(orientation)
                    if orientation==Qt.Orientation.Vertical:self.main_splitter.setSizes([round(self.main_splitter.height()*.44),round(self.main_splitter.height()*.56)])
                    else:self.main_splitter.setSizes([round(self.main_splitter.width()*.40),round(self.main_splitter.width()*.60)])
    def export(self,extension):
        source,kind,target=self.preview_source()
        stem=("napi_etlap_" if kind=="daily" else "heti_menu_" if kind=="weekly" else "kulonleges_etlap_")+target.isoformat()
        image_size=(EXPORT_WIDTH,EXPORT_HEIGHT)
        if kind=="special":
            image_size=(int(self.store.setting("special_canvas_width","1240") or "1240"),
                        int(self.store.setting("special_canvas_height","1754") or "1754"))
        path,_=QFileDialog.getSaveFileName(self,"Étlap exportálása",stem+"."+extension,
                                           "PDF (*.pdf)" if extension=="pdf" else "PNG (*.png)")
        if not path:return
        try:
            if extension=="pdf":export_pdf(path,source,kind,target)
            else:export_png(path,source,kind,target,*image_size)
            QMessageBox.information(self,APP_NAME,"Az étlap elkészült:\n"+path)
        except Exception as exc:QMessageBox.critical(self,APP_NAME,"Az export sikertelen:\n"+str(exc))
    def closeEvent(self,event):self.store.db.close();super().closeEvent(event)


def main():
    app=QApplication(sys.argv);app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setWindowIcon(QIcon(str(app_asset("megyehaza_emblem.png"))))
    palette=QPalette()
    palette.setColor(QPalette.ColorRole.Window,QColor("#f8f3eb"));palette.setColor(QPalette.ColorRole.WindowText,QColor("#362f2b"))
    palette.setColor(QPalette.ColorRole.Base,QColor("#fffdf9"));palette.setColor(QPalette.ColorRole.AlternateBase,QColor("#f3eadf"))
    palette.setColor(QPalette.ColorRole.Text,QColor("#362f2b"));palette.setColor(QPalette.ColorRole.Button,QColor("#d9e5d8"))
    palette.setColor(QPalette.ColorRole.ButtonText,QColor("#344b3a"));palette.setColor(QPalette.ColorRole.Highlight,QColor("#b85a4a"))
    palette.setColor(QPalette.ColorRole.HighlightedText,QColor("#ffffff"));palette.setColor(QPalette.ColorRole.ToolTipBase,QColor("#382f2a"))
    palette.setColor(QPalette.ColorRole.ToolTipText,QColor("#fffaf2"));palette.setColor(QPalette.ColorGroup.Disabled,QPalette.ColorRole.Text,QColor("#999087"))
    palette.setColor(QPalette.ColorGroup.Disabled,QPalette.ColorRole.ButtonText,QColor("#999087"));app.setPalette(palette)
    splash_pixmap=QPixmap(str(app_asset("splash.png")))
    if not splash_pixmap.isNull():
        splash_pixmap=splash_pixmap.scaled(520,260,Qt.AspectRatioMode.KeepAspectRatio,
                                           Qt.TransformationMode.SmoothTransformation)
    else:
        splash_pixmap=QPixmap(520,260);splash_pixmap.fill(QColor("#f8f3eb"))
    splash=QSplashScreen(splash_pixmap,Qt.WindowType.WindowStaysOnTopHint);splash.show();app.processEvents()
    window=MainWindow();window.show();splash.finish(window);sys.exit(app.exec())

if __name__=="__main__":main()

