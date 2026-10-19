"""ÉtlapStúdió Qt6 desktop editor with persistent split preview."""
from __future__ import annotations
import sqlite3
import sys
import textwrap
from datetime import date, timedelta
from pathlib import Path
from PyQt6.QtCore import QDate, QTimer, Qt
from PyQt6.QtGui import QColor, QFont, QIntValidator, QPainter, QPen, QPixmap, QPalette
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QCompleter, QDateEdit, QDialog,
    QDialogButtonBox, QFileDialog, QFontComboBox, QFormLayout, QFrame,
    QDockWidget, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMainWindow, QMessageBox, QPushButton, QScrollArea,
    QSplitter, QSizePolicy, QTabWidget, QTreeWidget, QTreeWidgetItem,
    QVBoxLayout, QWidget,
)
from menu_core import (APP_NAME, ArchivedMenu, CATEGORIES, WEEKDAYS, Store,
                       data_dir, display_date, monday, price)
from menu_render import export_pdf, export_png, render_image
from themes import load_themes, import_theme

BASE=Path(__file__).resolve().parent
FONT_ROLES=[("title","Főcím"),("heading","Alcímek"),
            ("special","Menüszövegek"),("dish","Ételek és árak")]
LEADERS={"Nincs":"none","Pontozott":"dots","Szaggatott":"dashes","Folytonos vonal":"line"}


def qdate(value):return QDate(value.year,value.month,value.day)
def pydate(value):return date(value.year(),value.month(),value.day())


def button(label,callback):
    b=QPushButton(label);b.clicked.connect(callback);return b


def price_edit(value=0):
    edit=QLineEdit(str(value));edit.setValidator(QIntValidator(0,1_000_000,edit))
    edit.setPlaceholderText("Ár forintban");edit.setClearButtonEnabled(True)
    return edit


class DishDialog(QDialog):
    def __init__(self,parent,row=None):
        super().__init__(parent);self.setWindowTitle("Étel szerkesztése" if row else "Új étel")
        layout=QVBoxLayout(self);form=QFormLayout();layout.addLayout(form)
        self.name=QLineEdit(row["name"] if row else "");form.addRow("Étel neve",self.name)
        self.category=QComboBox();self.category.addItems(CATEGORIES)
        if row:self.category.setCurrentText(row["category"])
        form.addRow("Kategória",self.category)
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


class DailyDishDialog(QDialog):
    def __init__(self,parent,dish,selected):
        super().__init__(parent);self.setWindowTitle(dish["name"])
        self.setMinimumWidth(420);layout=QVBoxLayout(self)
        title=QLabel(dish["name"]);title.setStyleSheet("font-size:19px;font-weight:700;color:#173f34")
        layout.addWidget(title)
        self.include=QCheckBox("Felveszem a mai étlapra");self.include.setChecked(selected is not None)
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


class PreviewLabel(QLabel):
    """Preview canvas with draggable guides for the printed sections."""
    from PyQt6.QtCore import pyqtSignal
    regionChanged = pyqtSignal(str, object)
    def __init__(self,parent=None):
        super().__init__(parent);self.guides=False;self.regions={};self._drag=None
        self.setMouseTracking(True)
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
        super().mousePressEvent(event)
    def mouseMoveEvent(self,event):
        if self._drag:
            name,start,original=self._drag;scale=self.pixmap().width()/1440
            header_shift=self.regions.get("Fejléc vége",270)-270
            limits={"Fejléc vége":(195,235),"Napi menü vége":(420+header_shift,640+header_shift),
                    "Heti menü kezdete":(200+header_shift,430+header_shift)}
            low,high=limits.get(name,(100,1700))
            y=round(max(low,min(high,event.position().y()/scale)))
            self.regions[name]=y;self.regionChanged.emit(name,y);self.update();event.accept();return
        super().mouseMoveEvent(event)
    def mouseReleaseEvent(self,event):
        if self._drag and event.button()==Qt.MouseButton.LeftButton:
            self._drag=None;self.unsetCursor();event.accept();return
        super().mouseReleaseEvent(event)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__();self.store=Store(data_dir()/"etlapstudio.sqlite3")
        if self.store.setting("guide_layout_version","0")!="3":
            self.store.set_settings({"guide_layout_version":"3","guide_daily_header":"205",
                                     "guide_daily_menu_end":"438","guide_weekly_header":"205",
                                     "guide_weekly_days":"220"})
        self.setWindowTitle(APP_NAME);self.resize(1620,920);self.setMinimumSize(1180,680)
        self._loading=False;self._image=None;self._date_change_old=None;self.preview_archive=None
        self.timer=QTimer(self);self.timer.setSingleShot(True);self.timer.timeout.connect(self.refresh_preview)
        splitter=QSplitter(Qt.Orientation.Horizontal);self.setCentralWidget(splitter)
        left=QWidget();left_layout=QVBoxLayout(left);left_layout.setContentsMargins(12,12,8,12)
        brand=QHBoxLayout();logo=QLabel();logo.setFixedSize(48,48)
        logo_path=BASE/"design_assets"/"megyehaza_emblem.png"
        if logo_path.is_file():logo.setPixmap(QPixmap(str(logo_path)).scaled(46,46,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation))
        brand.addWidget(logo);title=QLabel("ÉTLAPSTÚDIÓ\nMegyeháza Étterem");title.setObjectName("appTitle");brand.addWidget(title,1)
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
        self.guides=QCheckBox("Térközök állítása");self.guides.setToolTip("Fogd meg a vízszintes vonalat és húzd fel vagy le a blokkok közötti tér beállításához.")
        self.guides.toggled.connect(self.update_guides);controls.addWidget(self.guides);controls.addStretch()
        self.zoom=QComboBox();self.zoom.addItems(["Teljes oldal","Szélesség"])
        self.zoom.setMaximumWidth(120);self.zoom.currentIndexChanged.connect(self.fit_preview);controls.addWidget(self.zoom)
        right_layout.addLayout(controls)
        self.scroll=QScrollArea();self.scroll.setWidgetResizable(False);self.scroll.setAlignment(Qt.AlignmentFlag.AlignHCenter|Qt.AlignmentFlag.AlignTop)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.preview=PreviewLabel();self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter);self.preview.regionChanged.connect(self.save_layout_region)
        self.scroll.setWidget(self.preview);right_layout.addWidget(self.scroll,1)
        self.status=QLabel();right_layout.addWidget(self.status)
        splitter.addWidget(right);splitter.setSizes([540,820]);splitter.setChildrenCollapsible(False)
        self.build_daily();self.build_weekly();self.build_appearance();self.build_archive()
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
            QTabBar::tab { padding:11px 18px; margin-right:4px; background:#e6d8c8; color:#604c42; border-radius:11px 11px 0 0; font-weight:600; }
            QTabBar::tab:selected { background:#fffaf2; color:#963f36; }
            QTabBar::tab:hover { background:#f1e4d6; color:#793c32; }
            QPushButton { padding:9px 13px; background:#d9e5d8; color:#344b3a; border:0; border-radius:10px; font-weight:600; }
            QPushButton:hover { background:#c2d5c1; color:#263e2e; }
            QPushButton:pressed { background:#a8c1a9; color:#203b2a; }
            QPushButton:disabled { background:#e8e1d8; color:#999087; }
            QPushButton[role="category"] { padding:4px 6px; min-height:25px; background:#f0e3d1; color:#66503f; font-size:12px; font-weight:650; border:0; border-radius:8px; }
            QPushButton[role="category"][active="true"] { background:#b85a4a; color:#ffffff; }
            QPushButton[role="food"] { padding:8px; min-height:54px; min-width:0; text-align:left; background:#fffdf8; color:#38332f; border:1px solid #eadfce; border-radius:12px; }
            QPushButton[role="food"][selected="true"] { background:#deeadb; color:#263e2e; border:1px solid #7f9c7c; }
            QPushButton[role="foodEdit"] { padding:6px 5px; min-width:54px; background:#f0e5d9; color:#6c4436; border:1px solid #dfcbbb; border-radius:9px; }
            QPushButton[role="foodEdit"]:hover { background:#e7d2c0; color:#55382d; }
            QLineEdit,QComboBox,QDateEdit,QFontComboBox { background:#fffdf9; color:#362f2b; padding:8px; border:1px solid #dacbbb; border-radius:9px; selection-background-color:#bc6957; selection-color:#ffffff; }
            QLineEdit:focus,QComboBox:focus,QDateEdit:focus,QFontComboBox:focus { background:#ffffff; border:2px solid #bf715b; color:#2e2824; }
            QLineEdit:disabled,QComboBox:disabled,QDateEdit:disabled,QFontComboBox:disabled { background:#ece5dc; color:#898076; }
            QComboBox::drop-down,QDateEdit::drop-down { background:#eadfd2; border:0; border-top-right-radius:8px; border-bottom-right-radius:8px; width:26px; }
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
            QLabel#appTitle { color:#874739; font-size:20px; font-weight:bold; padding:4px; }
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
        page,box=self.pane("Napi étlap · az étel gombja hozzáad vagy levesz, a Szerk. gombbal az ár és az akció módosítható")
        self.tabs.addTab(page,"Napi")
        row=QHBoxLayout();self.day=QDateEdit(qdate(date.today()));self.day.setCalendarPopup(True)
        self.day.setDisplayFormat("yyyy.MM.dd.");self.day.dateChanged.connect(self.daily_date_changed)
        row.addWidget(QLabel("Dátum"));row.addWidget(self.day);row.addStretch()
        row.addWidget(button("Ma",lambda:self.day.setDate(qdate(date.today()))))
        box.addLayout(row)
        self.daily_special=QLabel();self.daily_special.setWordWrap(True);self.daily_special.setObjectName("dailySpecial")
        self.daily_special.setStyleSheet("padding:12px;background:#e9f1ed;border-radius:8px;color:#315644")
        box.addWidget(self.daily_special)
        self.search=QLineEdit();self.search.setPlaceholderText("Kezdj el gépelni egy ételnevet…");self.search.textChanged.connect(self.refresh_food_grid)
        box.addWidget(self.search)
        category_wrap=QWidget();self.category_grid=QGridLayout(category_wrap);self.category_grid.setContentsMargins(0,2,0,2);self.category_grid.setSpacing(5)
        box.addWidget(category_wrap)
        self.active_category="Összes";self.category_buttons={}
        self.build_category_buttons()
        self.food_scroll=QScrollArea();self.food_scroll.setWidgetResizable(True)
        self.food_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        foods_wrap=QWidget();self.food_grid=QGridLayout(foods_wrap);self.food_grid.setContentsMargins(2,3,8,3);self.food_grid.setSpacing(8)
        self.food_scroll.setWidget(foods_wrap);box.addWidget(self.food_scroll,1)
        self.daily_count=QLabel();box.addWidget(self.daily_count)
        box.addWidget(button("Ételadatbázis kezelése…",self.catalog_manager))

    def build_category_buttons(self):
        categories=["Összes"]+[name for name in CATEGORIES if name!="Menü"]
        short={"Főzelékek":"Főzelék","Feltétek":"Feltét","Köretek":"Köret",
               "Savanyúságok":"Savanyúság","Frissensültek":"Frissensült",
               "Tészták, desszertek":"Tészta / desszert","Mártások, öntetek":"Mártás"}
        for i,name in enumerate(categories):
            b=button(name,lambda checked=False,category=name:self.choose_category(category))
            b.setText(short.get(name,name));b.setToolTip(name)
            b.setProperty("role","category");b.setProperty("active",name==self.active_category)
            b.style().unpolish(b);b.style().polish(b)
            b.setMinimumHeight(30);b.setMinimumWidth(0);b.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Fixed)
            self.category_grid.addWidget(b,i//3,i%3);self.category_buttons[name]=b
        for col in range(3):self.category_grid.setColumnStretch(col,1)

    def choose_category(self,category):
        self.active_category=category
        for name,b in self.category_buttons.items():
            b.setProperty("active",name==category);b.style().unpolish(b);b.style().polish(b)
        self.refresh_food_grid()

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
        self._food_rows={r["id"]:r for r in foods}
        for n,dish in enumerate(foods):
            is_selected=dish["id"] in selected
            cols=max(1,min(3,self.food_scroll.viewport().width()//235))
            chars=max(15,int((self.food_scroll.viewport().width()/cols-40)/8))
            name="\n".join(textwrap.wrap(dish["name"],width=chars,break_long_words=True,break_on_hyphens=False))
            promo=bool(dish["promo_enabled"] and dish["promo_price"] is not None)
            label=("✓  " if is_selected else "+  ")+name+"\n"+price(dish["price"])+("  ·  AKCIÓ "+price(dish["promo_price"]) if promo else "")
            card=QWidget();card.setStyleSheet("background:transparent")
            cardbox=QHBoxLayout(card);cardbox.setContentsMargins(0,0,0,0);cardbox.setSpacing(5)
            b=button(label,lambda checked=False,dish_id=dish["id"]:self.toggle_daily_dish(dish_id))
            b.setProperty("role","food");b.setProperty("selected",is_selected)
            lines=len(name.splitlines())+1
            b.setMinimumHeight(max(72,24+lines*21));b.setMinimumWidth(0);b.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Preferred)
            b.setStyleSheet("text-align:left;white-space:pre-wrap")
            edit=button("Szerk.",lambda checked=False,dish_id=dish["id"]:self.edit_daily_dish(dish_id))
            edit.setProperty("role","foodEdit");edit.setToolTip("Étel, ár és napi akció szerkesztése")
            edit.setAccessibleName("Szerkesztés: "+dish["name"]);edit.setMinimumHeight(48);edit.setSizePolicy(QSizePolicy.Policy.Fixed,QSizePolicy.Policy.Fixed)
            cardbox.addWidget(b,1);cardbox.addWidget(edit)
            cols=max(1,min(3,self.food_scroll.viewport().width()//235))
            self.food_grid.addWidget(card,n//cols,n%cols)
        cols=max(1,min(3,self.food_scroll.viewport().width()//235))
        for col in range(cols):self.food_grid.setColumnStretch(col,1)
        self.food_grid.setRowStretch((len(foods)+cols-1)//cols,1)
        self.daily_count.setText(f"{len(selected)} étel szerepel a mai étlapon"+ (" · nincs találat" if not foods else ""))
        self.schedule_preview()

    def toggle_daily_dish(self,dish_id):
        selected={row["id"]:dict(row) for row in self.store.selection(self.current_day())}
        if dish_id in selected:
            row=selected.pop(dish_id)
            self.store.save_daily_dish(self.current_day(),dish_id,int(row["price"]),False)
            self.status.setText("Az étel lekerült a mai étlapról.")
        else:
            dish=self.store.db.execute("SELECT price FROM dishes WHERE id=? AND active=1",(dish_id,)).fetchone()
            if not dish:return
            self.store.save_daily_dish(self.current_day(),dish_id,int(dish["price"]),True)
            self.status.setText("Az étel felkerült a mai étlapra.")
        self.preview_archive=None;self.refresh_daily();self.refresh_archive()

    def build_weekly(self):
        page,box=self.pane("Heti menü · leves, A és B menü külön az à la carte kínálattól")
        self.tabs.addTab(page,"Heti")
        row=QHBoxLayout();self.week=QDateEdit(qdate(monday(date.today())))
        self.week.setCalendarPopup(True);self.week.setDisplayFormat("yyyy.MM.dd.")
        self.week.dateChanged.connect(lambda _:self.refresh_week())
        row.addWidget(QLabel("Hét dátuma"));row.addWidget(self.week);box.addLayout(row)
        self.week_fields=[]
        scroll=QScrollArea();scroll.setWidgetResizable(True)
        inner=QWidget();innerbox=QVBoxLayout(inner)
        for i,label in enumerate(WEEKDAYS):
            heading=QLabel(label);heading.setStyleSheet("font-weight:bold;color:#176246;margin-top:8px;")
            innerbox.addWidget(heading);form=QFormLayout();group=[]
            for field in ("Leves","A menü","B menü"):
                edit=QLineEdit();edit.textChanged.connect(self.schedule_week_save)
                completer=QCompleter(self.store.menu_suggestions(),edit)
                completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
                completer.setFilterMode(Qt.MatchFlag.MatchContains)
                edit.setCompleter(completer)
                form.addRow(field,edit);group.append(edit)
            self.week_fields.append(group);innerbox.addLayout(form)
        innerbox.addStretch();scroll.setWidget(inner);box.addWidget(scroll,1)
        note=QLabel("A szerkesztett heti menüt a jobb felső Mentés gombbal rögzítheted.")
        note.setWordWrap(True);box.addWidget(note)

    def build_archive(self):
        dock=QDockWidget("Korábbi étlapok · hetek szerint",self)
        dock.setObjectName("savedMenusDock");dock.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea|Qt.DockWidgetArea.RightDockWidgetArea)
        self.archive=QTreeWidget();self.archive.setHeaderHidden(True);self.archive.setIndentation(18)
        self.archive.itemClicked.connect(self.preview_saved_menu);self.archive.itemDoubleClicked.connect(self.edit_saved_menu)
        body=QWidget();body_layout=QVBoxLayout(body);body_layout.setContentsMargins(7,7,7,7)
        info=QLabel("Egy kattintás: előnézet\nDupla kattintás: szerkesztés")
        info.setStyleSheet("color:#60747d;padding:5px")
        body_layout.addWidget(info);body_layout.addWidget(self.archive,1)
        dock.setWidget(body);self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea,dock)
        dock.setMinimumWidth(230);self.archive_dock=dock
        action=dock.toggleViewAction();action.setText("Korábbi étlapok");self.menuBar().addAction(action)

    def build_appearance(self):
        page,box=self.pane("Dizájn · ünnepi színek, betűtípusok és visszafogott grafikai elemek")
        self.tabs.addTab(page,"Dizájn")
        scroll=QScrollArea();scroll.setWidgetResizable(True);inner=QWidget();form=QFormLayout(inner)
        self.settings={}
        for key,label in (("address","Cím"),("phone","Telefonszám"),("note","Alsó megjegyzés")):
            edit=QLineEdit(self.store.setting(key));edit.textChanged.connect(self.save_settings)
            self.settings[key]=edit;form.addRow(label,edit)
        self.daily_menu_price=price_edit(self.store.setting("daily_menu_price","2800") or "2800")
        self.daily_menu_price.setToolTip("Ez az ár jelenik meg a napi étlapon és a heti étlap fejlécében is.")
        self.daily_menu_price.editingFinished.connect(self.save_appearance)
        form.addRow("Napi menü ára (Ft)",self.daily_menu_price)
        form.addRow("",button("Ételadatbázis kezelése…",self.catalog_manager))
        form.addRow("",button("Adatbázis biztonsági másolata…",self.backup))
        self.theme=QComboBox();self.theme_keys=[];self.reload_themes()
        self.theme.currentIndexChanged.connect(self.save_appearance);form.addRow("Téma · színek és háttér",self.theme)
        self.fonts={}
        for role,label in FONT_ROLES:
            default_font="Georgia" if role in ("title","heading") else "Segoe UI"
            combo=QFontComboBox();saved=self.store.setting("font_"+role,default_font)
            saved={"Modern sans":"DejaVu Sans","Klasszikus talpas":"DejaVu Serif"}.get(saved,saved)
            combo.setCurrentFont(QFont(saved));combo.currentFontChanged.connect(self.save_appearance)
            self.fonts[role]=combo;form.addRow(label,combo)
        self.leader=QComboBox()
        for label,value in LEADERS.items():self.leader.addItem(label,value)
        index=self.leader.findData(self.store.setting("leader","none"));self.leader.setCurrentIndex(max(index,0))
        self.leader.currentIndexChanged.connect(self.save_appearance);form.addRow("Étel–ár jelölés",self.leader)
        self.glass=QCheckBox("Félig áttetsző üveghatású panelek az olvashatóságért")
        self.glass.setChecked(self.store.setting("glass_panels","1")=="1")
        self.glass.toggled.connect(self.save_appearance);form.addRow("",self.glass)
        self.decorations=QCheckBox("Áttetsző szezonális elválasztók")
        self.decorations.setChecked(self.store.setting("decorations","1")=="1")
        self.decorations.toggled.connect(self.save_appearance);form.addRow("",self.decorations)
        form.addRow("",button("Témacsomag importálása…",self.import_theme))
        reset=button("Dizájn visszaállítása alapértékre",self.reset_design);reset.setObjectName("resetButton")
        form.addRow("",reset)
        scroll.setWidget(inner);box.addWidget(scroll,1)

    def current_day(self):return pydate(self.day.date())
    def current_week(self):return monday(pydate(self.week.date()))

    def refresh_daily(self,*_):
        if not hasattr(self,"daily_special"):return
        day=self.current_day();soup,a,b=self.store.week_entry(day)
        self.daily_special.setText("Mai menü: "+"  ·  ".join(x for x in (soup,a,b) if x) if any((soup,a,b)) else
                                   "A leves és az A/B menü a Heti menü fülön szerkeszthető.")
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
            for widget,value in zip(group,self.store.week_entry(mon+timedelta(days=i))):widget.setText(value)
        self._loading=False;self.schedule_preview()

    def schedule_week_save(self):
        if self._loading:return
        for i,group in enumerate(self.week_fields):
            self.store.set_week_entry(self.current_week()+timedelta(days=i),*(edit.text() for edit in group))
        self.refresh_daily();self.schedule_preview()

    def save_daily(self):
        self.store.save_menu("daily",self.current_day());self.preview_archive=None;self.refresh_archive()
        QMessageBox.information(self,APP_NAME,"A napi étlap mentve az étlap-adatbázisba.")

    def save_week(self):
        self.store.save_menu("weekly",self.current_week());self.refresh_archive()
        self.preview_archive=None;QMessageBox.information(self,APP_NAME,"A heti menü mentve az étlap-adatbázisba.")

    def save_current(self):
        if self.preview_archive is not None:
            self.edit_saved_menu(self.archive.currentItem(),0);return
        if self.tabs.currentIndex()==1:self.save_week()
        else:self.save_daily()

    def refresh_menu_suggestions(self):
        suggestions=self.store.menu_suggestions()
        for group in self.week_fields:
            for edit in group:edit.completer().model().setStringList(suggestions)

    def import_starter(self):
        count=self.store.import_starter_catalogue()
        self.refresh_daily();self.refresh_menu_suggestions()
        QMessageBox.information(self,APP_NAME,f"{count} hiányzó étel bekerült az adatbázisba.")

    def catalog_manager(self):
        dialog=QDialog(self);dialog.setWindowTitle("Ételadatbázis kezelése");dialog.resize(650,560)
        layout=QVBoxLayout(dialog);search=QLineEdit();search.setPlaceholderText("Keresés név vagy kategória szerint…")
        layout.addWidget(search);tree=QTreeWidget();tree.setHeaderLabels(["Étel","Kategória","Normál ár"])
        layout.addWidget(tree,1)
        def reload(*_):
            tree.clear()
            for row in self.store.dishes(search.text()):
                item=QTreeWidgetItem([row["name"],row["category"],price(row["price"])])
                item.setData(0,Qt.ItemDataRole.UserRole,row["id"]);tree.addTopLevelItem(item)
        def selected_row():
            item=tree.currentItem()
            return self.store.db.execute("SELECT * FROM dishes WHERE id=?",(item.data(0,Qt.ItemDataRole.UserRole),)).fetchone() if item else None
        def edit(row=None):
            form=DishDialog(dialog,row)
            if form.exec()!=QDialog.DialogCode.Accepted:return
            name=form.name.text().strip()
            if not name:QMessageBox.warning(dialog,APP_NAME,"Add meg az étel nevét.");return
            self.store.add_dish(name,form.category.currentText(),int(form.amount.text()),row["id"] if row else None)
            reload();self.refresh_daily();self.refresh_menu_suggestions()
        actions=QHBoxLayout();add=button("Új étel",lambda:edit())
        change=button("Szerkesztés",lambda:edit(selected_row()))
        def delete():
            row=selected_row()
            if row and QMessageBox.question(dialog,APP_NAME,"Eltávolítsuk ezt az ételt a napi kínálatból?")==QMessageBox.StandardButton.Yes:
                self.store.delete_dish(row["id"]);reload();self.refresh_daily();self.refresh_menu_suggestions()
        actions.addWidget(add);actions.addWidget(change);actions.addWidget(button("Eltávolítás",delete));actions.addStretch()
        layout.addLayout(actions);layout.addWidget(button("Hiányzó alapételek betöltése",self.import_starter))
        search.textChanged.connect(reload);tree.itemDoubleClicked.connect(lambda *_:edit(selected_row()))
        reload();dialog.exec()

    def refresh_archive(self):
        if not hasattr(self,"archive"):return
        self.archive.clear();groups={}
        for row in self.store.saved_menus():
            day=date.fromisoformat(row["menu_date"]);week=monday(day)
            key=week.isoformat()
            if key not in groups:
                group=QTreeWidgetItem([f"{week:%Y.%m.%d.} – {(week+timedelta(days=6)):%m.%d.}"])
                group.setData(0,Qt.ItemDataRole.UserRole,None);self.archive.addTopLevelItem(group);groups[key]=group
            label=("📅  " if row["kind"]=="daily" else "🗓  ")+day.strftime("%Y.%m.%d.")
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
        row,_=self.store.saved_menu(item.data(0,Qt.ItemDataRole.UserRole));day=date.fromisoformat(row["menu_date"])
        self.preview_archive=None
        if row["kind"]=="weekly":self.tabs.setCurrentIndex(1);self.week.setDate(qdate(day))
        else:self.tabs.setCurrentIndex(0);self.day.setDate(qdate(day))

    def reload_themes(self):
        self.theme_packs=load_themes(BASE/"themes_builtin",data_dir()/"themes")
        self.theme.blockSignals(True)
        self.theme.clear();self.theme.addItem("Automatikus évszakos téma · színek + háttér","auto");self.theme_keys=["auto",*self.theme_packs]
        for key in self.theme_keys:
            self.theme.addItem("Automatikus évszakos téma · színek + háttér" if key=="auto" else self.theme_packs[key][0]["name"],key)
        default_theme="auto" if self.store.setting("auto_theme","1")=="1" else self.store.setting("theme","classic")
        index=self.theme.findData(default_theme);self.theme.setCurrentIndex(max(index,0))
        self.theme.blockSignals(False)

    def save_appearance(self,*_):
        if not hasattr(self,"glass"):return
        values={"theme":self.theme.currentData() or "auto","auto_theme":"1" if self.theme.currentData()=="auto" else "0",
                "decorations":"1" if self.decorations.isChecked() else "0",
                "glass_panels":"1" if self.glass.isChecked() else "0","leader":self.leader.currentData() or "none",
                "daily_menu_price":self.daily_menu_price.text().strip() or "0"}
        values.update({"font_"+key:combo.currentFont().family() for key,combo in self.fonts.items()})
        self.store.set_settings(values);self.schedule_preview()

    def reset_design(self):
        with self.store.db:
            self.store.db.execute("DELETE FROM settings WHERE (key LIKE 'guide_%' AND key!='guide_layout_version') OR key LIKE 'layout_%'")
        self.store.set_settings({"theme":"auto","auto_theme":"1","decorations":"1","glass_panels":"1",
                                 "background_path":"","leader":"none",
                                 "theme_primary":"","theme_accent":"",
                                 "font_title":"Georgia","font_heading":"Georgia",
                                 "font_special":"Segoe UI","font_dish":"Segoe UI",
                                 "guide_layout_version":"3"})
        self.theme.blockSignals(True);idx=self.theme.findData("auto");self.theme.setCurrentIndex(max(0,idx));self.theme.blockSignals(False)
        for role,combo in self.fonts.items():
            combo.blockSignals(True);combo.setCurrentFont(QFont("Georgia" if role in ("title","heading") else "Segoe UI"));combo.blockSignals(False)
        self.glass.setChecked(True);self.decorations.setChecked(True)
        idx=self.leader.findData("none");self.leader.setCurrentIndex(max(0,idx))
        self.update_guides();self.schedule_preview()

    def import_theme(self):
        path,_=QFileDialog.getOpenFileName(self,"Témacsomag importálása","","ZIP (*.zip)")
        if not path:return
        try:
            slug=import_theme(Path(path),data_dir()/"themes",set(self.theme_packs))
            self.store.set_settings({"theme":slug,"auto_theme":"0","theme_primary":"","theme_accent":""})
            self.reload_themes();self.schedule_preview()
        except Exception as exc:QMessageBox.warning(self,APP_NAME,str(exc))

    def save_settings(self):
        if not hasattr(self,"settings") or len(self.settings)!=4:return
        self.store.set_settings({key:edit.text().strip() for key,edit in self.settings.items()})
        self.schedule_preview()
    def backup(self):
        path,_=QFileDialog.getSaveFileName(self,"Adatbázis mentése","etlapstudio-mentes.sqlite3","SQLite (*.sqlite3)")
        if path:
            with sqlite3.connect(path) as destination:self.store.db.backup(destination)

    def on_tab(self,index):
        self.preview_archive=None;self.schedule_preview()
        self.update_guides()

    def update_guides(self,*_):
        if not hasattr(self,"preview"):return
        kind="weekly" if self.tabs.currentIndex()==1 else "daily"
        keys={"header":"Fejléc vége","days":"Heti menü kezdete"} if kind=="weekly" else {
            "header":"Fejléc vége","menu_end":"Napi menü vége"}
        defaults={"header":205,"days":220,"menu_end":438}
        header=int(self.store.setting(f"guide_{kind}_header",str(defaults["header"])))
        shift=header-defaults["header"]
        regions={label:header if key=="header" else int(self.store.setting(f"guide_{kind}_{key}",str(defaults[key])))+shift
                 for key,label in keys.items()}
        self.preview.set_guides(self.guides.isChecked(),regions)

    def save_layout_region(self,name,y):
        keys={"Fejléc vége":"header","Heti menü kezdete":"days","Napi menü vége":"menu_end"}
        kind="weekly" if self.tabs.currentIndex()==1 else "daily"
        header=int(self.store.setting(f"guide_{kind}_header","205"));shift=header-205
        saved_y=y if name=="Fejléc vége" else y-shift
        self.store.set_settings({f"guide_{kind}_{keys[name]}":str(saved_y)})
        self.update_guides();self.schedule_preview()
    def preview_source(self):
        index=self.tabs.currentIndex()
        if index==1:return self.store,"weekly",self.current_week()
        if self.preview_archive is not None:return self.preview_archive
        return self.store,"daily",self.current_day()
    def schedule_preview(self):
        if hasattr(self,"preview"):self.timer.start(180)
    def refresh_preview(self):
        try:
            source,kind,target=self.preview_source()
            image=render_image(source,kind,target)
            self._image=image
            self.preview_title.setText(("Napi étlap" if kind=="daily" else "Heti menü")+" · "+display_date(target)+(" · mentett előnézet" if self.preview_archive else ""))
            self.fit_preview();self.status.setText("1440 × 1800 px · A4 PDF és Facebook PNG")
        except Exception as exc:self.status.setText("Előnézeti hiba: "+str(exc))
    def fit_preview(self):
        if self._image is None:return
        available=self.scroll.viewport().width()-24
        if self.zoom.currentIndex()==0:
            available=min(available,(self.scroll.viewport().height()-24)*1440/1800)
        width=max(180,min(1000,int(available)))
        self.preview.setPixmap(QPixmap.fromImage(self._image).scaledToWidth(width,Qt.TransformationMode.SmoothTransformation))
        self.preview.adjustSize()
    def resizeEvent(self,event):
        super().resizeEvent(event)
        if hasattr(self,"preview"):
            QTimer.singleShot(60,self.fit_preview)
            if hasattr(self,"food_grid"):QTimer.singleShot(100,self.refresh_food_grid)
    def export(self,extension):
        source,kind,target=self.preview_source()
        stem=("napi_etlap_" if kind=="daily" else "heti_menu_")+target.isoformat()
        path,_=QFileDialog.getSaveFileName(self,"Étlap exportálása",stem+"."+extension,
                                           "PDF (*.pdf)" if extension=="pdf" else "PNG (*.png)")
        if not path:return
        try:
            if extension=="pdf":export_pdf(path,source,kind,target)
            else:export_png(path,source,kind,target)
            QMessageBox.information(self,APP_NAME,"Az étlap elkészült:\n"+path)
        except Exception as exc:QMessageBox.critical(self,APP_NAME,"Az export sikertelen:\n"+str(exc))
    def closeEvent(self,event):self.store.db.close();super().closeEvent(event)


def main():
    app=QApplication(sys.argv);app.setApplicationName(APP_NAME)
    palette=QPalette()
    palette.setColor(QPalette.ColorRole.Window,QColor("#f8f3eb"));palette.setColor(QPalette.ColorRole.WindowText,QColor("#362f2b"))
    palette.setColor(QPalette.ColorRole.Base,QColor("#fffdf9"));palette.setColor(QPalette.ColorRole.AlternateBase,QColor("#f3eadf"))
    palette.setColor(QPalette.ColorRole.Text,QColor("#362f2b"));palette.setColor(QPalette.ColorRole.Button,QColor("#d9e5d8"))
    palette.setColor(QPalette.ColorRole.ButtonText,QColor("#344b3a"));palette.setColor(QPalette.ColorRole.Highlight,QColor("#b85a4a"))
    palette.setColor(QPalette.ColorRole.HighlightedText,QColor("#ffffff"));palette.setColor(QPalette.ColorRole.ToolTipBase,QColor("#382f2a"))
    palette.setColor(QPalette.ColorRole.ToolTipText,QColor("#fffaf2"));palette.setColor(QPalette.ColorGroup.Disabled,QPalette.ColorRole.Text,QColor("#999087"))
    palette.setColor(QPalette.ColorGroup.Disabled,QPalette.ColorRole.ButtonText,QColor("#999087"));app.setPalette(palette)
    window=MainWindow();window.show();sys.exit(app.exec())

if __name__=="__main__":main()
