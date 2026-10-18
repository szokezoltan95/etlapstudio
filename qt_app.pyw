"""ÉtlapStúdió Qt6 desktop editor with persistent split preview."""
from __future__ import annotations
import sqlite3
import sys
import textwrap
from datetime import date, timedelta
from pathlib import Path
from PyQt6.QtCore import QDate, QTimer, Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QCompleter, QDateEdit, QDialog,
    QDialogButtonBox, QFileDialog, QFontComboBox, QFormLayout, QFrame,
    QDockWidget, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMainWindow, QMessageBox, QPushButton, QScrollArea,
    QSpinBox, QSplitter, QSizePolicy, QTabWidget, QTreeWidget, QTreeWidgetItem,
    QVBoxLayout, QWidget,
)
from menu_core import (APP_NAME, ArchivedMenu, CATEGORIES, WEEKDAYS, Store,
                       data_dir, display_date, monday, price)
from menu_render import export_pdf, export_png, render_image
from themes import load_themes, import_theme

BASE=Path(__file__).resolve().parent
FONT_ROLES=[("restaurant","Étterem neve"),("title","Főcím"),
            ("heading","Alcímek"),("special","Menüszövegek"),("dish","Ételek és árak")]
LEADERS={"Nincs":"none","Pontozott":"dots","Szaggatott":"dashes","Folytonos vonal":"line"}


def qdate(value):return QDate(value.year,value.month,value.day)
def pydate(value):return date(value.year(),value.month(),value.day())


def button(label,callback):
    b=QPushButton(label);b.clicked.connect(callback);return b


class DishDialog(QDialog):
    def __init__(self,parent,row=None):
        super().__init__(parent);self.setWindowTitle("Étel szerkesztése" if row else "Új étel")
        layout=QVBoxLayout(self);form=QFormLayout();layout.addLayout(form)
        self.name=QLineEdit(row["name"] if row else "");form.addRow("Étel neve",self.name)
        self.category=QComboBox();self.category.addItems(CATEGORIES)
        if row:self.category.setCurrentText(row["category"])
        form.addRow("Kategória",self.category)
        self.amount=QSpinBox();self.amount.setRange(0,1_000_000);self.amount.setSuffix(" Ft")
        self.amount.setValue(row["price"] if row else 0);form.addRow("Ár",self.amount)
        self.amount_label=QLabel("A Menü kategóriában a 0 Ft azt jelenti, hogy nincs külön feltüntetett ár.")
        self.amount_label.setWordWrap(True);layout.addWidget(self.amount_label)
        hint=QLabel("A napi akciós árat a Napi étlap fülön, az adott dátumhoz állíthatod be.")
        hint.setWordWrap(True);layout.addWidget(hint)
        controls=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        controls.accepted.connect(self.accept);controls.rejected.connect(self.reject);layout.addWidget(controls)
        self.setMinimumWidth(440)


class PromotionDialog(QDialog):
    def __init__(self,parent,dish):
        super().__init__(parent);self.setWindowTitle("Napi akció · "+dish["name"])
        layout=QVBoxLayout(self);layout.addWidget(QLabel("Normál ár: "+price(dish["price"])))
        self.enabled=QCheckBox("Akciós ár alkalmazása ezen a napon")
        self.enabled.setChecked(bool(dish["promo_enabled"]));layout.addWidget(self.enabled)
        self.amount=QSpinBox();self.amount.setRange(0,max(0,dish["price"]-1));self.amount.setSuffix(" Ft")
        self.amount.setValue(dish["promo_price"] or 0);self.amount.setEnabled(self.enabled.isChecked())
        self.enabled.toggled.connect(self.amount.setEnabled)
        row=QFormLayout();row.addRow("Akciós ár",self.amount);layout.addLayout(row)
        layout.addWidget(QLabel("A kedvezmény csak a kiválasztott napi étlapon jelenik meg."))
        controls=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        controls.accepted.connect(self.accept);controls.rejected.connect(self.reject);layout.addWidget(controls)


class DailyDishDialog(QDialog):
    def __init__(self,parent,dish,selected):
        super().__init__(parent);self.setWindowTitle(dish["name"])
        self.setMinimumWidth(420);layout=QVBoxLayout(self)
        title=QLabel(dish["name"]);title.setStyleSheet("font-size:19px;font-weight:700;color:#173f34")
        layout.addWidget(title)
        self.include=QCheckBox("Felveszem a mai étlapra");self.include.setChecked(selected is not None)
        layout.addWidget(self.include)
        form=QFormLayout();layout.addLayout(form)
        self.regular=QSpinBox();self.regular.setRange(0,1_000_000);self.regular.setSuffix(" Ft")
        self.regular.setValue(dish["price"]);form.addRow("Normál ár",self.regular)
        self.promo=QCheckBox("Akciós ár ezen a napon");self.promo.setChecked(bool(selected and selected["promo_enabled"] and selected["promo_price"] is not None))
        form.addRow("Akció",self.promo)
        self.promo_amount=QSpinBox();self.promo_amount.setRange(0,1_000_000);self.promo_amount.setSuffix(" Ft")
        self.promo_amount.setValue((selected["promo_price"] if selected and selected["promo_price"] is not None else 0))
        self.promo_amount.setEnabled(self.promo.isChecked());self.promo.toggled.connect(self.promo_amount.setEnabled)
        form.addRow("Akciós ár",self.promo_amount)
        layout.addWidget(QLabel("Az új normál ár az étel adatlapján is frissül."))
        controls=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel)
        controls.accepted.connect(self.accept);controls.rejected.connect(self.reject);layout.addWidget(controls)


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
        from PyQt6.QtCore import QRectF
        scale=self.width()/1440;p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing)
        for name,(x,y,w,h) in self.regions.items():
            rect=QRectF(x*scale,y*scale,w*scale,h*scale)
            p.setPen(QPen(QColor("#008a87"),1.5,Qt.PenStyle.DashLine));p.setBrush(Qt.BrushStyle.NoBrush);p.drawRect(rect)
            p.setPen(Qt.PenStyle.NoPen);p.setBrush(QColor("#008a87"));p.drawRect(QRectF(rect.right()-7,rect.bottom()-7,12,12))
            p.setPen(QColor("#006a68"));p.drawText(int(rect.left()+4),int(rect.top()+15),name)
        p.end()
    def mousePressEvent(self,event):
        if self.guides and event.button()==Qt.MouseButton.LeftButton:
            scale=self.width()/1440
            if scale>0:
                point=(event.position().x()/scale,event.position().y()/scale)
                for name,(x,y,w,h) in reversed(list(self.regions.items())):
                    if x+w-24<=point[0]<=x+w+18 and y+h-24<=point[1]<=y+h+18:
                        self._drag=(name,"resize",point,(x,y,w,h));event.accept();return
                    if x<=point[0]<=x+w and y<=point[1]<=y+h:
                        self._drag=(name,"move",point,(x,y,w,h));event.accept();return
        super().mousePressEvent(event)
    def mouseMoveEvent(self,event):
        if self._drag:
            name,mode,start,original=self._drag;scale=self.width()/1440
            point=(event.position().x()/scale,event.position().y()/scale);dx=point[0]-start[0];dy=point[1]-start[1]
            x,y,w,h=original
            if mode=="move":x+=dx;y+=dy
            else:w=max(220,w+dx);h=max(80,h+dy)
            x=max(20,min(1440-w,x));y=max(20,min(1800-h,y))
            self.regions[name]=(round(x),round(y),round(w),round(h));self.regionChanged.emit(name,self.regions[name]);self.update();event.accept();return
        super().mouseMoveEvent(event)
    def mouseReleaseEvent(self,event):
        if self._drag and event.button()==Qt.MouseButton.LeftButton:self._drag=None;event.accept();return
        super().mouseReleaseEvent(event)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__();self.store=Store(data_dir()/"etlapstudio.sqlite3")
        self.setWindowTitle(APP_NAME);self.resize(1620,920);self.setMinimumSize(1180,680)
        self._loading=False;self._image=None;self._date_change_old=None;self.preview_archive=None
        self.timer=QTimer(self);self.timer.setSingleShot(True);self.timer.timeout.connect(self.refresh_preview)
        splitter=QSplitter(Qt.Orientation.Horizontal);self.setCentralWidget(splitter)
        left=QWidget();left_layout=QVBoxLayout(left);left_layout.setContentsMargins(12,12,8,12)
        title=QLabel("ÉTLAPSTÚDIÓ");title.setObjectName("appTitle");left_layout.addWidget(title)
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
        self.guides=QCheckBox("Szerkesztővonalak");self.guides.setToolTip("Húzd a keretet a mozgatáshoz, a jobb alsó fogantyút az átméretezéshez.")
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
            QMainWindow,QWidget { background:#f3f5f4; color:#263640; font-size:13px; }
            QTabWidget::pane { border:1px solid #d7e0e4; border-radius:10px; background:#ffffff; }
            QTabBar::tab { padding:11px 18px; background:#e8edef; border-top-left-radius:8px; border-top-right-radius:8px; }
            QTabBar::tab:selected { background:white; color:#173f52; font-weight:bold; }
            QPushButton { padding:9px 13px; background:#e5edf0; border:1px solid #c9d8de; border-radius:8px; }
            QPushButton:hover { background:#d3e2e8; }
            QPushButton[role="category"] { padding:5px 7px; min-height:28px; background:#e7efec; color:#24473b; font-weight:600; border:0; border-radius:7px; }
            QPushButton[role="category"][active="true"] { background:#486f5e; color:white; }
            QPushButton[role="food"] { padding:10px; min-height:54px; min-width:0; text-align:left; background:white; border:1px solid #dce4e7; }
            QPushButton[role="food"][selected="true"] { background:#e6f0e8; border:1px solid #5e8b6c; }
            QLineEdit,QComboBox,QSpinBox,QDateEdit,QFontComboBox { background:white; padding:8px; border:1px solid #ccd9de; border-radius:7px; }
            QTreeWidget,QListWidget { background:white; alternate-background-color:#f4f7f8; border:1px solid #d0dcdf; }
            QDockWidget::title { background:#e6edef; padding:9px; color:#183e50; font-weight:bold; }
            QLabel#appTitle { color:#174759; font-size:22px; font-weight:bold; padding:4px; }
            QLabel#previewTitle { color:#174759; font-size:17px; font-weight:bold; }
            QFrame[card="true"] { background:white; border:1px solid #dce4e7; border-radius:10px; }
        ''')

    def pane(self,title):
        outer=QWidget();layout=QVBoxLayout(outer);layout.setContentsMargins(12,12,12,12)
        heading=QLabel(title);heading.setWordWrap(True);layout.addWidget(heading);return outer,layout

    def build_daily(self):
        page,box=self.pane("Napi étlap · kattints egy ételre a felvételhez vagy módosításhoz")
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
            label=("✓  " if is_selected else "")+name+"\n"+dish["category"]+"  ·  "+price(dish["price"])
            b=button(label,lambda checked=False,dish_id=dish["id"]:self.edit_daily_dish(dish_id))
            b.setProperty("role","food");b.setProperty("selected",is_selected)
            b.setMinimumHeight(72);b.setMinimumWidth(0);b.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Preferred)
            b.setStyleSheet("text-align:left;white-space:pre-wrap")
            cols=max(1,min(3,self.food_scroll.viewport().width()//235))
            self.food_grid.addWidget(b,n//cols,n%cols)
        cols=max(1,min(3,self.food_scroll.viewport().width()//235))
        for col in range(cols):self.food_grid.setColumnStretch(col,1)
        self.food_grid.setRowStretch((len(foods)+cols-1)//cols,1)
        self.daily_count.setText(f"{len(selected)} étel szerepel a mai étlapon"+ (" · nincs találat" if not foods else ""))
        self.schedule_preview()

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
        for key,label in (("restaurant","Étterem neve"),("address","Cím"),("phone","Telefonszám"),("note","Alsó megjegyzés")):
            edit=QLineEdit(self.store.setting(key));edit.textChanged.connect(self.save_settings)
            self.settings[key]=edit;form.addRow(label,edit)
        form.addRow("",button("Ételadatbázis kezelése…",self.catalog_manager))
        form.addRow("",button("Adatbázis biztonsági másolata…",self.backup))
        self.theme=QComboBox();self.theme_keys=[];self.reload_themes()
        self.theme.currentIndexChanged.connect(self.save_appearance);form.addRow("Színvilág",self.theme)
        self.fonts={}
        for role,label in FONT_ROLES:
            default_font="Georgia" if role in ("restaurant","title","heading") else "Segoe UI"
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
        self.decorations=QCheckBox("Egyszerű ecsetvonásos címsorok és áttetsző elválasztók")
        self.decorations.setChecked(self.store.setting("decorations","1")=="1")
        self.decorations.toggled.connect(self.save_appearance);form.addRow("",self.decorations)
        form.addRow("",button("Témacsomag importálása…",self.import_theme))
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
        new_price=dialog.regular.value();promo=dialog.promo.isChecked()
        promo_price=dialog.promo_amount.value()
        if promo and (new_price<=0 or promo_price>=new_price):
            QMessageBox.warning(self,APP_NAME,"Az akciós ár legyen kisebb a normál árnál.");return
        try:self.store.add_dish(dish["name"],dish["category"],new_price,dish_id)
        except ValueError as exc:QMessageBox.warning(self,APP_NAME,str(exc));return
        active={row["id"] for row in self.store.selection(self.current_day())}
        if dialog.include.isChecked():active.add(dish_id)
        else:active.discard(dish_id)
        self.store.set_selected(self.current_day(),sorted(active))
        if dialog.include.isChecked() and promo:
            self.store.set_daily_promotion(self.current_day(),dish_id,True,promo_price)
        else:self.store.set_daily_promotion(self.current_day(),dish_id,False)
        self.preview_archive=None;self.refresh_daily()

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
            self.store.add_dish(name,form.category.currentText(),form.amount.value(),row["id"] if row else None)
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
        self.theme.clear();self.theme.addItem("Automatikus ünnepi színek","auto");self.theme_keys=["auto",*self.theme_packs]
        for key in self.theme_keys:
            self.theme.addItem("Automatikus ünnepi színek" if key=="auto" else self.theme_packs[key][0]["name"],key)
        default_theme="auto" if self.store.setting("auto_theme","1")=="1" else self.store.setting("theme","classic")
        index=self.theme.findData(default_theme);self.theme.setCurrentIndex(max(index,0))
        self.theme.blockSignals(False)

    def save_appearance(self,*_):
        if not hasattr(self,"glass"):return
        values={"theme":self.theme.currentData() or "auto","auto_theme":"1" if self.theme.currentData()=="auto" else "0",
                "decorations":"1" if self.decorations.isChecked() else "0",
                "glass_panels":"1" if self.glass.isChecked() else "0","leader":self.leader.currentData() or "none",
                "background_enabled":"0"}
        values.update({"font_"+key:combo.currentFont().family() for key,combo in self.fonts.items()})
        self.store.set_settings(values);self.schedule_preview()

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

    def layout_defaults(self):
        if self.tabs.currentIndex()==1:
            return {"header":(80,55,1280,375),"days":(120,520,1200,1120)}
        return {"header":(80,55,1280,375),"daily_menu":(120,475,1200,235),"alacarte":(120,725,1200,990)}

    def update_guides(self,*_):
        if not hasattr(self,"preview"):return
        kind="weekly" if self.tabs.currentIndex()==1 else "daily"
        labels={"header":"Fejléc","daily_menu":"Napi menü","alacarte":"À la carte","days":"Napok"}
        regions={}
        for key,default in self.layout_defaults().items():
            raw=self.store.setting(f"layout_{kind}_{key}")
            try:rect=tuple(map(int,raw.split(","))) if raw else default
            except (ValueError,TypeError):rect=default
            regions[labels[key]]=rect
        self.preview.set_guides(self.guides.isChecked(),regions)

    def save_layout_region(self,name,rect):
        keys={"Fejléc":"header","Napi menü":"daily_menu","À la carte":"alacarte","Napok":"days"}
        kind="weekly" if self.tabs.currentIndex()==1 else "daily"
        self.store.set_settings({f"layout_{kind}_{keys[name]}":",".join(map(str,rect))})
        self.schedule_preview()
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
    window=MainWindow();window.show();sys.exit(app.exec())

if __name__=="__main__":main()
