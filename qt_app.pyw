"""ÉtlapStúdió Qt6 desktop editor with persistent split preview."""
from __future__ import annotations
import sqlite3
import json
import sys
from datetime import date, timedelta
from pathlib import Path
from PyQt6.QtCore import QDate, QTimer, Qt, QEvent, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QColor, QFont, QIntValidator, QPainter, QPen, QPixmap, QPalette, QTextCharFormat
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QCompleter, QDateEdit, QDialog,
    QDialogButtonBox, QFileDialog, QFontComboBox, QFormLayout, QFrame,
    QDockWidget, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMainWindow, QMessageBox, QPushButton, QScrollArea,
    QSplitter, QSizePolicy, QStackedWidget, QTabBar, QTabWidget, QTreeWidget, QTreeWidgetItem, QTextEdit, QColorDialog,
    QVBoxLayout, QWidget, QDoubleSpinBox, QGraphicsDropShadowEffect, QSpinBox,
)
from menu_core import (APP_NAME, ArchivedMenu, CATEGORIES, WEEKDAYS, Store,
                       data_dir, display_date, monday, price)
from menu_render import A4_WIDTH_PT, H, W, asset_file, export_pdf, export_png, render_image
from themes import load_themes, import_theme, import_theme_images

BASE=Path(__file__).resolve().parent
TEXT_STYLES=[
    ("header_title","Étterem neve · fejléc-adatmező","Segoe UI",11,"title"),
    ("header_date","Dátum a napi / heti panelben","Segoe UI",16,"special"),
    ("header_contact","Cím, telefonszám és Facebook link","Segoe UI",11,"special"),
    ("daily_title","Napi / heti étlap címsora","Georgia",22,"heading"),
    ("daily_label","Napi menü sorcímkéi · Leves / A / B","Segoe UI",13,"heading"),
    ("daily_value","Napi menü ételnevei","Segoe UI",13,"special"),
    ("menu_price_label","Napi menü árának címkéje","Segoe UI",12,"special"),
    ("menu_price_value","Napi menü ára","Georgia",20,"title"),
    ("category_title","À la carte kategóriacímek","Georgia",14,"heading"),
    ("dish_name","À la carte ételnevek · maximális méret","Segoe UI",12.5,"dish"),
    ("dish_price","À la carte normál árak","Segoe UI",12.5,"dish"),
    ("promo_old_price","Akciós étel régi ára","Segoe UI",7,"dish"),
    ("promo_new_price","Akciós étel új ára","Segoe UI",12.5,"dish"),
    ("promo_badge","AKCIÓ jelzés","Segoe UI",6,"dish"),
    ("weekday_title","Heti menü napnevei","Georgia",16,"heading"),
    ("weekly_label","Heti menü sorcímkéi · Leves / A / B","Segoe UI",15,"heading"),
    ("weekly_value","Heti menü ételnevei","Segoe UI",15,"special"),
    ("footer_note","Alsó megjegyzés","Georgia",10,"special"),
]
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
    def __init__(self,parent,row=None,initial_name=""):
        super().__init__(parent);self.setWindowTitle("Étel szerkesztése" if row else "Új étel")
        layout=QVBoxLayout(self);form=QFormLayout();layout.addLayout(form)
        self.name=QLineEdit(row["name"] if row else initial_name);form.addRow("Étel neve",self.name)
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
            header_shift=self.regions.get("Fejléc vége",205)-205
            limits={"Fejléc vége":(195,235),"Napi menü vége":(420+header_shift,640+header_shift),
                    "Heti menü kezdete":(310+header_shift,430+header_shift)}
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
        self.store.set_settings({"restaurant_name":self.store.setting("restaurant_name","Megyeháza Étterem") or "Megyeháza Étterem",
                                 "address":self.store.setting("address","Miskolc, Városház tér 1.") or "Miskolc, Városház tér 1.",
                                 "phone":self.store.setting("phone","+36 30 / 513 2605") or "+36 30 / 513 2605",
                                 "facebook_url":self.store.setting("facebook_url","https://www.facebook.com/share/1GQgCcNJXE/") or "https://www.facebook.com/share/1GQgCcNJXE/"})
        if self.store.setting("guide_layout_version","0")!="8":
            layout_defaults={"guide_layout_version":"8"}
            for key,value in {"guide_daily_header":"205","guide_daily_menu_end":"438",
                              "guide_weekly_header":"205","guide_weekly_days":"330"}.items():
                if self.store.setting(key) is None:layout_defaults[key]=value
            # Promote only untouched former defaults; preserve sizes the user tuned.
            for role,old,new in (("daily_title","18","22"),("header_date","14","16"),
                                 ("menu_price_label","7.5","12"),("menu_price_value","15","20"),
                                 ("weekday_title","13","16"),("weekly_label","10.5","15"),
                                 ("weekly_value","13","15"),("promo_new_price","8","12.5"),
                                 ("footer_note","7","10")):
                if self.store.setting("font_size_"+role)==old:
                    layout_defaults["font_size_"+role]=new
            if self.store.setting("font_size_header_title")=="19.5":
                layout_defaults["font_size_header_title"]="11"
                if self.store.setting("font_header_title")=="Georgia":
                    layout_defaults["font_header_title"]="Segoe UI"
            self.store.set_settings(layout_defaults)
        self.setWindowTitle(APP_NAME);self.setMinimumSize(760,540)
        screen=QApplication.primaryScreen()
        available=screen.availableGeometry() if screen else None
        if available:self.resize(min(1500,max(760,available.width()-48)),min(900,max(540,available.height()-72)))
        else:self.resize(1280,780)
        self._loading=False;self._image=None;self._date_change_old=None;self.preview_archive=None;self._manual_week_preview=False
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
        self.guides=QCheckBox("Térközök állítása");self.guides.setToolTip("Fogd meg a vízszintes vonalat és húzd fel vagy le a blokkok közötti tér beállításához.")
        self.guides.toggled.connect(self.update_guides);controls.addWidget(self.guides);controls.addStretch()
        self.zoom=QComboBox();self.zoom.addItems(["Teljes oldal","Szélesség"])
        self.zoom.setMaximumWidth(120);self.zoom.currentIndexChanged.connect(self.fit_preview);controls.addWidget(self.zoom)
        right_layout.addLayout(controls)
        self.scroll=QScrollArea();self.scroll.setWidgetResizable(False);self.scroll.setAlignment(Qt.AlignmentFlag.AlignHCenter|Qt.AlignmentFlag.AlignTop)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.viewport().installEventFilter(self)
        self.zoom.setCurrentIndex(0)
        self.preview=PreviewLabel();self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter);self.preview.regionChanged.connect(self.save_layout_region)
        self.scroll.setWidget(self.preview);right_layout.addWidget(self.scroll,1)
        self.status=QLabel();right_layout.addWidget(self.status)
        splitter.addWidget(right);self.preview_panel=right;splitter.setSizes([570,850]);splitter.setChildrenCollapsible(False)
        self.build_daily();self.build_weekly();self.build_special();self.build_appearance();self.build_archive()
        self.archive_dock.hide()
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
            QPushButton[role="food"][selected="true"] { background:#deeadb; color:#263e2e; border:1px solid #7f9c7c; }
            QPushButton[role="foodEdit"] { padding:6px 5px; min-width:54px; background:#f0e5d9; color:#6c4436; border:1px solid #dfcbbb; border-radius:9px; }
            QPushButton[role="foodEdit"]:hover { background:#e7d2c0; color:#55382d; }
            QPushButton[role="foodAction"] { padding:3px; min-width:42px; min-height:30px; background:#dce9d8; color:#31553b; border:1px solid #bdd0b8; border-radius:8px; font-size:17px; }
            QPushButton[role="foodAction"]:hover { background:#c7ddc0; color:#23452d; border:1px solid #789a73; }
            QPushButton[role="foodAction"]:pressed { background:#aac9a2; }
            QPushButton[role="foodRemove"] { padding:3px; min-width:42px; min-height:30px; background:#f5e3df; color:#98463d; border:1px solid #e5c3bb; border-radius:8px; font-size:17px; }
            QPushButton[role="foodRemove"]:hover { background:#edcbc3; color:#7f332d; border:1px solid #ce8e82; }
            QPushButton[role="foodRemove"]:pressed { background:#e1b1a7; }
            QLineEdit,QComboBox,QDateEdit,QFontComboBox { background:#fffdf9; color:#362f2b; padding:8px; border:1px solid #dacbbb; border-radius:9px; selection-background-color:#bc6957; selection-color:#ffffff; }
            QLineEdit:focus,QComboBox:focus,QDateEdit:focus,QFontComboBox:focus { background:#ffffff; border:2px solid #bf715b; color:#2e2824; }
            QLineEdit:disabled,QComboBox:disabled,QDateEdit:disabled,QFontComboBox:disabled { background:#ece5dc; color:#898076; }
            QComboBox::drop-down,QDateEdit::drop-down { background:#eadfd2; border:0; border-top-right-radius:8px; border-bottom-right-radius:8px; width:26px; }
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
        self.day=QDateEdit(qdate(date.today()));self.day.setCalendarPopup(True);self.day.setMaximumWidth(132)
        self.day.setDisplayFormat("yyyy.MM.dd.");self.day.dateChanged.connect(self.daily_date_changed)
        date_row.addWidget(QLabel("Dátum"));date_row.addWidget(self.day)
        date_row.addWidget(button("Ma",lambda:self.day.setDate(qdate(date.today()))))
        self.active_category="Összes";self.build_category_tabs()
        box.addWidget(self.category_tab_widget)
        self.search=QLineEdit();self.search.setPlaceholderText("Keresés az ételek között…");self.search.textChanged.connect(self.refresh_food_grid)
        self.search.returnPressed.connect(self.handle_search_enter)
        self.search.setToolTip("Enter: ugrás az első hozzáadható találatra; találat nélkül új étel felvétele.")
        box.addWidget(self.search)
        order_row=QHBoxLayout();order_row.setSpacing(7)
        order_row.addWidget(QLabel("Sorrend a kész étlapon"))
        self.menu_order=QComboBox();self.menu_order.addItem("Magyar ábécé szerint","name")
        self.menu_order.addItem("Ár szerint növekvő","price_asc")
        self.menu_order.addItem("Ár szerint csökkenő","price_desc")
        saved_order=self.store.setting("daily_menu_sort","name")
        saved_index=self.menu_order.findData(saved_order)
        if saved_index>=0:self.menu_order.setCurrentIndex(saved_index)
        self.menu_order.currentIndexChanged.connect(self.save_menu_order)
        order_row.addWidget(self.menu_order,1);box.addLayout(order_row)
        self.food_scroll=QScrollArea();self.food_scroll.setWidgetResizable(True)
        self.food_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        foods_wrap=QWidget();self.food_grid=QGridLayout(foods_wrap);self.food_grid.setContentsMargins(2,3,8,3);self.food_grid.setSpacing(8)
        self.food_scroll.setWidget(foods_wrap);box.addWidget(self.food_scroll,1)
        self.new_food_button=button("＋  Új étel",self.add_catalogue_dish)
        self.clear_daily_button=button("Étlap kiürítése…",self.clear_daily_menu);self.clear_daily_button.setProperty("role","destructive")
        action_row=QHBoxLayout();action_row.addWidget(self.new_food_button,2);action_row.addWidget(self.clear_daily_button,1);box.addLayout(action_row)
        self.daily_count=QLabel();box.addWidget(self.daily_count)
        box.addWidget(button("Ételadatbázis kezelése…",self.catalog_manager))

    def save_menu_order(self,*_):
        if not hasattr(self,"menu_order"):return
        self.store.set_settings({"daily_menu_sort":self.menu_order.currentData()})
        self.preview_archive=None
        self.schedule_preview()

    def build_category_tabs(self):
        self.category_names=["Összes"]+[name for name in CATEGORIES if name!="Menü"]
        wrapper=QWidget();layout=QVBoxLayout(wrapper);layout.setContentsMargins(0,0,0,0);layout.setSpacing(0)
        self.category_tabs=[];self._category_tab_offsets=[]
        split=(len(self.category_names)+1)//2
        for row_index,(start,end) in enumerate(((0,split),(split,len(self.category_names)))):
            bar=QTabBar();bar.setObjectName("categoryTabs");bar.setShape(QTabBar.Shape.RoundedNorth)
            bar.setExpanding(False);bar.setUsesScrollButtons(True);bar.setElideMode(Qt.TextElideMode.ElideNone)
            for name in self.category_names[start:end]:bar.addTab(name)
            bar.setProperty("inactiveRow",True)
            bar.setCurrentIndex(-1)
            bar.currentChanged.connect(lambda local_index,offset=start:self.choose_category_index(offset+local_index) if local_index>=0 else None)
            layout.addWidget(bar);self.category_tabs.append(bar);self._category_tab_offsets.append(start)
        self.category_tabs[0].setCurrentIndex(0)
        self.category_tab_widget=wrapper

    def choose_category(self,category):
        if category in self.category_names:self.choose_category_index(self.category_names.index(category))

    def choose_category_index(self,index):
        if index<0 or index>=len(self.category_names):return
        self.active_category=self.category_names[index]
        for bar,offset in zip(self.category_tabs,self._category_tab_offsets):
            bar.blockSignals(True)
            row_is_active=offset<=index<offset+bar.count()
            bar.setProperty("inactiveRow",not row_is_active)
            local_index=index-offset if row_is_active else -1
            bar.setCurrentIndex(local_index)
            bar.style().unpolish(bar);bar.style().polish(bar);bar.update()
            bar.blockSignals(False)
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
            cols=max(1,min(3,self.food_scroll.viewport().width()//235))
            self.food_grid.addWidget(card,n//cols,n%cols)
        cols=max(1,min(3,self.food_scroll.viewport().width()//235))
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

    def add_catalogue_dish(self,checked=False,initial_name=""):
        form=DishDialog(self,initial_name=initial_name)
        if form.exec()!=QDialog.DialogCode.Accepted:return
        try:
            dish_id=self.store.add_dish(form.name.text().strip(),form.category.currentText(),int(form.amount.text()))
            self.store.save_daily_dish(self.current_day(),dish_id,int(form.amount.text()),True)
        except (ValueError,sqlite3.Error) as exc:
            QMessageBox.warning(self,APP_NAME,"Nem sikerült elmenteni az új ételt.\n"+str(exc));return
        self.search.clear();self.choose_category("Összes")
        self.refresh_menu_suggestions();self.refresh_daily()
        self.status.setText("Az új étel bekerült az adatbázisba és a kiválasztott napi étlapra.")

    def build_weekly(self):
        page,box=self.pane("Heti menü · leves, A és B menü külön az à la carte kínálattól")
        self.tabs.addTab(page,"Heti")
        self.week_date_controls=QWidget();row=QHBoxLayout(self.week_date_controls);row.setContentsMargins(0,0,0,0);row.setSpacing(5)
        self.week=QDateEdit(qdate(monday(date.today())));self.week.setMaximumWidth(132)
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
        self.special_date=QDateEdit(qdate(date.today()));self.special_date.setCalendarPopup(True)
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
        toolbar=QHBoxLayout();toolbar.setSpacing(5)
        self.special_font=QFontComboBox();self.special_font.setCurrentFont(QFont(self.store.setting("special_font","Georgia")))
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
            "special_show_date":"1" if self.special_show_date.isChecked() else "0"})
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
        self.design_kind="daily"
        self.design_type=QComboBox();self.design_type.addItem("Napi étlap","daily");self.design_type.addItem("Heti étlap","weekly");self.design_type.addItem("Különleges alkalom","special")
        form.addRow("Szerkesztett laptípus",self.design_type)
        for key,label,default in (("restaurant_name","Étterem neve","Megyeháza Étterem"),
                                  ("address","Cím","Miskolc, Városház tér 1."),
                                  ("phone","Telefonszám","+36 30 / 513 2605"),
                                  ("facebook_url","Facebook link","https://www.facebook.com/share/1GQgCcNJXE/"),
                                  ("note","Alsó megjegyzés","")):
            edit=QLineEdit(self.store.setting(key,default));edit.textChanged.connect(self.save_settings)
            self.settings[key]=edit;form.addRow(label,edit)
        self.daily_menu_price=price_edit(self.store.setting("daily_menu_price","2800") or "2800")
        self.daily_menu_price.setToolTip("Ez az ár jelenik meg a napi étlapon és a heti étlap fejlécében is.")
        self.daily_menu_price.editingFinished.connect(self.save_appearance)
        form.addRow("Napi menü ára (Ft)",self.daily_menu_price)
        form.addRow("",button("Ételadatbázis kezelése…",self.catalog_manager))
        form.addRow("",button("Adatbázis biztonsági másolata…",self.backup))
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
        self.glass_opacity=QSpinBox();self.glass_opacity.setRange(25,100);self.glass_opacity.setSuffix(" %")
        self.glass_opacity.setValue(int(self.store.setting("glass_opacity","80") or "80"))
        self.glass_opacity.setToolTip("Nagyobb értéknél a panel jobban takarja a hátteret, így a szöveg könnyebben olvasható.")
        self.glass_opacity.valueChanged.connect(self.save_appearance);form.addRow("Panel fedettsége",self.glass_opacity)
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
        for widget,key,default in ((self.heading_font,"font_heading","Georgia"),(self.body_font,"font_body","Segoe UI")):
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
            self.store.set_settings({key:values.get(key,"") for key in ("special_title","special_html","special_show_title","special_show_date")})
            self.special_title_edit.blockSignals(True);self.special_title_edit.setText(values.get("special_title",""));self.special_title_edit.blockSignals(False)
            self.special_show_title.setChecked(values.get("special_show_title","0")=="1")
            self.special_show_date.setChecked(values.get("special_show_date","0")=="1")
            self.special_text.blockSignals(True);self.special_text.setHtml(values.get("special_html",""));self.special_text.blockSignals(False)
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
        values={"daily_menu_price":self.daily_menu_price.text().strip() or "0"}
        self.store.set_settings(values)
        if hasattr(self,"text_style_widgets"):self.capture_design_kind(getattr(self,"design_kind","daily"))
        self.schedule_preview()

    def reset_design(self):
        with self.store.db:
            self.store.db.execute("DELETE FROM settings WHERE (key LIKE 'guide_%' AND key!='guide_layout_version') OR key LIKE 'layout_%'")
        defaults={"theme":"auto","auto_theme":"1","decorations":"1","glass_panels":"1",
                  "glass_color_mode":"white","glass_color":"#DDE7D8","glass_opacity":"80",
                  "background_path":"","leader":"none","theme_primary":"","theme_accent":"","font_size_unit":"pt_a4",
                  "font_title":"Georgia","font_heading":"Georgia","font_body":"Segoe UI","font_special":"Segoe UI","font_dish":"Segoe UI","advanced_typography":"0",
                  "guide_layout_version":"8"}
        for key,_,family,size,_legacy in TEXT_STYLES:
            defaults["font_"+key]=family;defaults["font_size_"+key]=str(size)
        for kind in ("daily","weekly","special"):
            for key,value in list(defaults.items()):
                if key.startswith(("font_","font_size_","theme","auto_theme","decorations","glass_panels","glass_color_mode","glass_color","glass_opacity","leader")) or key=="advanced_typography":
                    defaults[kind+"_"+key]=value
        self.store.set_settings(defaults)
        self.theme.blockSignals(True);idx=self.theme.findData("auto");self.theme.setCurrentIndex(max(0,idx));self.theme.blockSignals(False)
        self.heading_font.setCurrentFont(QFont("Georgia"));self.body_font.setCurrentFont(QFont("Segoe UI"))
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
        if self.tabs.currentIndex() not in (0,1):
            self.guides.setEnabled(False);self.preview.set_guides(False,{})
            return
        self.guides.setEnabled(True)
        kind="weekly" if self.tabs.currentIndex()==1 else "daily"
        keys={"header":"Fejléc vége","days":"Heti menü kezdete"} if kind=="weekly" else {
            "header":"Fejléc vége","menu_end":"Napi menü vége"}
        defaults={"header":205,"days":330,"menu_end":438}
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
    def fit_preview(self):
        if self._image is None:return
        viewport=self.scroll.viewport()
        available_width=viewport.width()-24
        if self.zoom.currentIndex()==0:
            available_width=min(available_width,(viewport.height()-24)*W/H)
        width=max(180,min(1000,int(available_width)))
        self.preview.setPixmap(QPixmap.fromImage(self._image).scaledToWidth(width,Qt.TransformationMode.SmoothTransformation))
        self.preview.adjustSize()
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

