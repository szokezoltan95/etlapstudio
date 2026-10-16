"""ÉtlapStúdió Qt6 desktop editor with persistent split preview."""
from __future__ import annotations
import hashlib
import shutil
import sqlite3
import sys
from datetime import date, timedelta
from pathlib import Path
from PyQt6.QtCore import QDate, QTimer, Qt
from PyQt6.QtGui import QColor, QFont, QPixmap
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QColorDialog, QComboBox, QDateEdit, QDialog,
    QDialogButtonBox, QFileDialog, QFontComboBox, QFormLayout, QFrame,
    QHBoxLayout, QLabel, QLineEdit, QListWidget, QMainWindow, QMessageBox,
    QPushButton, QScrollArea, QSlider, QSpinBox, QSplitter, QTabWidget,
    QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
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


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__();self.store=Store(data_dir()/"etlapstudio.sqlite3")
        self.setWindowTitle(APP_NAME);self.resize(1450,860);self.setMinimumSize(980,640)
        self._loading=False;self._image=None
        self.timer=QTimer(self);self.timer.setSingleShot(True);self.timer.timeout.connect(self.refresh_preview)
        splitter=QSplitter(Qt.Orientation.Horizontal);self.setCentralWidget(splitter)
        left=QWidget();left_layout=QVBoxLayout(left);left_layout.setContentsMargins(12,12,8,12)
        title=QLabel("ÉTLAPSTÚDIÓ");title.setObjectName("appTitle");left_layout.addWidget(title)
        self.tabs=QTabWidget();left_layout.addWidget(self.tabs,1)
        splitter.addWidget(left)
        right=QWidget();right_layout=QVBoxLayout(right);right_layout.setContentsMargins(8,12,12,12)
        toolbar=QHBoxLayout();self.preview_title=QLabel("Élő előnézet");self.preview_title.setObjectName("previewTitle")
        toolbar.addWidget(self.preview_title);toolbar.addStretch()
        self.zoom=QComboBox();self.zoom.addItems(["Teljes oldal","Szélesség"])
        self.zoom.currentIndexChanged.connect(self.fit_preview);toolbar.addWidget(self.zoom)
        toolbar.addWidget(button("PDF",lambda:self.export("pdf")))
        toolbar.addWidget(button("Facebook PNG",lambda:self.export("png")))
        right_layout.addLayout(toolbar)
        self.scroll=QScrollArea();self.scroll.setWidgetResizable(False);self.scroll.setAlignment(Qt.AlignmentFlag.AlignHCenter|Qt.AlignmentFlag.AlignTop)
        self.preview=QLabel();self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll.setWidget(self.preview);right_layout.addWidget(self.scroll,1)
        self.status=QLabel();right_layout.addWidget(self.status)
        splitter.addWidget(right);splitter.setSizes([600,850]);splitter.setChildrenCollapsible(False)
        self.build_daily();self.build_weekly();self.build_catalog();self.build_archive()
        self.build_appearance();self.build_settings()
        self.tabs.currentChanged.connect(self.on_tab)
        self.refresh_daily();self.refresh_week();self.refresh_catalog();self.refresh_archive()
        self.schedule_preview()
        self.setStyleSheet('''
            QMainWindow,QWidget { background:#f6f8f5; color:#24372f; font-size:13px; }
            QTabWidget::pane { border:1px solid #cbd9d0; border-radius:6px; }
            QTabBar::tab { padding:9px 10px; background:#e8efe9; }
            QTabBar::tab:selected { background:white; color:#146246; font-weight:bold; }
            QPushButton { padding:7px 11px; background:#e2ece5; border:1px solid #b7cbbf; border-radius:5px; }
            QPushButton:hover { background:#cfdfd3; }
            QLineEdit,QComboBox,QSpinBox,QDateEdit,QFontComboBox { background:white; padding:5px; border:1px solid #c5d3c9; border-radius:4px; }
            QTreeWidget,QListWidget { background:white; alternate-background-color:#f4f8f5; border:1px solid #c5d3c9; }
            QLabel#appTitle { color:#11573c; font-size:22px; font-weight:bold; padding:4px; }
            QLabel#previewTitle { color:#11573c; font-size:17px; font-weight:bold; }
        ''')

    def pane(self,title):
        outer=QWidget();layout=QVBoxLayout(outer);layout.setContentsMargins(12,12,12,12)
        layout.addWidget(QLabel(title));return outer,layout

    def build_daily(self):
        page,box=self.pane("Napi étlap · válaszd ki az ételeket és az aznapi akciókat")
        self.tabs.addTab(page,"Napi")
        row=QHBoxLayout();self.day=QDateEdit(qdate(date.today()));self.day.setCalendarPopup(True)
        self.day.setDisplayFormat("yyyy.MM.dd.");self.day.dateChanged.connect(lambda _:self.refresh_daily())
        row.addWidget(QLabel("Dátum"));row.addWidget(self.day);row.addStretch()
        row.addWidget(button("Ma",lambda:self.day.setDate(qdate(date.today()))))
        box.addLayout(row)
        self.daily_special=QLabel();self.daily_special.setWordWrap(True);box.addWidget(self.daily_special)
        self.search=QLineEdit();self.search.setPlaceholderText("Étel keresése…");self.search.textChanged.connect(self.refresh_daily)
        box.addWidget(self.search)
        self.daily_tree=QTreeWidget();self.daily_tree.setHeaderLabels(["Aznap", "Étel", "Kategória", "Ár", "Akció"])
        self.daily_tree.setAlternatingRowColors(True)
        for col,width in enumerate((55,190,100,85,90)):
            self.daily_tree.setColumnWidth(col,width)
        self.daily_tree.itemChanged.connect(self.daily_checked);self.daily_tree.itemDoubleClicked.connect(self.edit_promotion)
        box.addWidget(self.daily_tree,1)
        hint=QLabel("Pipáld be az ételt. Akciós árhoz dupla kattintás vagy az alábbi gomb.")
        hint.setWordWrap(True);box.addWidget(hint)
        row=QHBoxLayout();row.addWidget(button("Akció beállítása…",self.edit_selected_promotion))
        row.addStretch();row.addWidget(button("Napi étlap mentése",self.save_daily));box.addLayout(row)

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
                form.addRow(field,edit);group.append(edit)
            self.week_fields.append(group);innerbox.addLayout(form)
        innerbox.addStretch();scroll.setWidget(inner);box.addWidget(scroll,1)
        box.addWidget(button("Heti menü mentése",self.save_week))

    def build_catalog(self):
        page,box=self.pane("À la carte ételadatbázis")
        self.tabs.addTab(page,"Ételek")
        self.catalog_search=QLineEdit();self.catalog_search.setPlaceholderText("Keresés név vagy kategória szerint…")
        self.catalog_search.textChanged.connect(self.refresh_catalog);box.addWidget(self.catalog_search)
        self.catalog=QTreeWidget();self.catalog.setHeaderLabels(["Étel", "Kategória", "Ár"])
        self.catalog.setColumnWidth(0,260);self.catalog.itemDoubleClicked.connect(lambda *_:self.edit_dish())
        box.addWidget(self.catalog,1)
        row=QHBoxLayout()
        for label,callback in (("Új étel",self.new_dish),("Szerkesztés",self.edit_dish),("Törlés",self.delete_dish)):
            row.addWidget(button(label,callback))
        row.addStretch();box.addLayout(row)

    def build_archive(self):
        page,box=self.pane("Mentett étlapok · a mentéskori nevekkel és árakkal")
        self.tabs.addTab(page,"Mentések")
        self.archive=QTreeWidget();self.archive.setHeaderLabels(["Típus", "Dátum", "Mentve"])
        self.archive.setColumnWidth(0,130);self.archive.setColumnWidth(1,145)
        self.archive.itemSelectionChanged.connect(self.schedule_preview)
        box.addWidget(self.archive,1)
        box.addWidget(QLabel("Válassz egy mentett étlapot: az előnézet és az export ezt a változatot mutatja."))
        box.addWidget(button("Lista frissítése",self.refresh_archive))

    def build_appearance(self):
        page,box=self.pane("Megjelenés · a Windows összes elérhető betűtípusa")
        self.tabs.addTab(page,"Megjelenés")
        scroll=QScrollArea();scroll.setWidgetResizable(True);inner=QWidget();form=QFormLayout(inner)
        self.theme=QComboBox();self.theme_keys=[];self.reload_themes()
        self.theme.currentIndexChanged.connect(self.save_appearance);form.addRow("Téma",self.theme)
        form.addRow("",button("Témacsomag importálása…",self.import_theme))
        self.fonts={}
        for role,label in FONT_ROLES:
            combo=QFontComboBox();saved=self.store.setting("font_"+role,"Segoe UI")
            saved={"Modern sans":"DejaVu Sans","Klasszikus talpas":"DejaVu Serif"}.get(saved,saved)
            combo.setCurrentFont(QFont(saved));combo.currentFontChanged.connect(self.save_appearance)
            self.fonts[role]=combo;form.addRow(label,combo)
        self.leader=QComboBox()
        for label,value in LEADERS.items():self.leader.addItem(label,value)
        index=self.leader.findData(self.store.setting("leader","none"));self.leader.setCurrentIndex(max(index,0))
        self.leader.currentIndexChanged.connect(self.save_appearance);form.addRow("Étel–ár jelölés",self.leader)
        self.decorations=QCheckBox("Díszek és elválasztók")
        self.decorations.setChecked(self.store.setting("decorations","1")=="1")
        self.decorations.toggled.connect(self.save_appearance);form.addRow("",self.decorations)
        self.bg_enabled=QCheckBox("Háttérgrafika bekapcsolása")
        self.bg_enabled.setChecked(self.store.setting("background_enabled","0")=="1")
        self.bg_enabled.toggled.connect(self.save_appearance);form.addRow("",self.bg_enabled)
        form.addRow("",button("Botanikus minta",self.use_sample_background))
        form.addRow("",button("PNG/JPG háttér importálása…",self.import_background))
        form.addRow("",button("Háttér eltávolítása",self.clear_background))
        self.opacity=QSlider(Qt.Orientation.Horizontal);self.opacity.setRange(0,100)
        self.opacity.setValue(int(self.store.setting("background_opacity","30")))
        self.opacity.valueChanged.connect(self.save_appearance);form.addRow("Háttér erőssége",self.opacity)
        self.primary=button("Alapszín…",lambda:self.pick_color("primary"))
        self.accent=button("Kiegészítő szín…",lambda:self.pick_color("accent"))
        form.addRow("Színek",self.primary);form.addRow("",self.accent)
        scroll.setWidget(inner);box.addWidget(scroll,1)

    def build_settings(self):
        page,box=self.pane("Étterem adatai")
        self.tabs.addTab(page,"Adatok")
        form=QFormLayout();self.settings={}
        for key,label in (("restaurant","Étterem neve"),("address","Cím"),("phone","Telefonszám"),("note","Alsó megjegyzés")):
            edit=QLineEdit(self.store.setting(key));edit.textChanged.connect(self.save_settings)
            self.settings[key]=edit;form.addRow(label,edit)
        box.addLayout(form);box.addStretch()
        box.addWidget(QLabel("Adatbázis: "+str(self.store.path)))
        box.addWidget(button("Adatbázis biztonsági másolata…",self.backup))

    def current_day(self):return pydate(self.day.date())
    def current_week(self):return monday(pydate(self.week.date()))

    def refresh_daily(self,*_):
        if not hasattr(self,"daily_tree"):return
        day=self.current_day();soup,a,b=self.store.week_entry(day)
        self.daily_special.setText("Mai menü: "+" · ".join(x for x in (soup,a,b) if x) if any((soup,a,b)) else
                                   "Mai menü: a Heti menü fülön szerkeszthető")
        selected={r["id"]:r for r in self.store.selection(day)}
        self._loading=True;self.daily_tree.clear()
        available=list(self.store.dishes(self.search.text()))
        active_ids={dish["id"] for dish in available}
        # Soft-deleted catalogue entries may still occur on an older dated menu.
        available.extend(row for row in selected.values()
                         if row["id"] not in active_ids and not row["active"]
                         and self.search.text().casefold() in row["name"].casefold())
        for dish in available:
            saved=selected.get(dish["id"])
            promo=bool(saved and saved["promo_enabled"] and saved["promo_price"] is not None)
            label=dish["name"]+(" (törölt az adatbázisból)" if not dish["active"] else "")
            item=QTreeWidgetItem(["",label,dish["category"],price(dish["price"]),
                                  price(saved["promo_price"]) if promo else ""])
            item.setData(0,Qt.ItemDataRole.UserRole,dish["id"])
            item.setFlags(item.flags()|Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(0,Qt.CheckState.Checked if saved else Qt.CheckState.Unchecked)
            if promo:item.setForeground(4,QColor("#ad2929"))
            self.daily_tree.addTopLevelItem(item)
        self._loading=False;self.schedule_preview()

    def daily_checked(self,item,column):
        if self._loading or column!=0:return
        current={row["id"] for row in self.store.selection(self.current_day())}
        dish_id=item.data(0,Qt.ItemDataRole.UserRole)
        if item.checkState(0)==Qt.CheckState.Checked:current.add(dish_id)
        else:current.discard(dish_id)
        self.store.set_selected(self.current_day(),sorted(current));self.schedule_preview()

    def edit_selected_promotion(self):
        item=self.daily_tree.currentItem()
        if item:self.edit_promotion(item,0)

    def edit_promotion(self,item,column):
        if item.checkState(0)!=Qt.CheckState.Checked:
            QMessageBox.information(self,APP_NAME,"Előbb pipáld be az ételt a napi étlaphoz.");return
        dish_id=item.data(0,Qt.ItemDataRole.UserRole)
        row=next((dict(x) for x in self.store.selection(self.current_day()) if x["id"]==dish_id),None)
        if not row:return
        dialog=PromotionDialog(self,row)
        if dialog.exec()==QDialog.DialogCode.Accepted:
            try:self.store.set_daily_promotion(self.current_day(),dish_id,dialog.enabled.isChecked(),dialog.amount.value())
            except ValueError as exc:QMessageBox.warning(self,APP_NAME,str(exc));return
            self.refresh_daily()

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
        self.store.save_menu("daily",self.current_day());self.refresh_archive()
        QMessageBox.information(self,APP_NAME,"A napi étlap mentve az étlap-adatbázisba.")

    def save_week(self):
        self.store.save_menu("weekly",self.current_week());self.refresh_archive()
        QMessageBox.information(self,APP_NAME,"A heti menü mentve az étlap-adatbázisba.")

    def refresh_catalog(self,*_):
        if not hasattr(self,"catalog"):return
        self.catalog.clear()
        for row in self.store.dishes(self.catalog_search.text()):
            item=QTreeWidgetItem([row["name"],row["category"],price(row["price"])])
            item.setData(0,Qt.ItemDataRole.UserRole,row["id"]);self.catalog.addTopLevelItem(item)

    def current_catalog_row(self):
        item=self.catalog.currentItem()
        if not item:return None
        dish_id=item.data(0,Qt.ItemDataRole.UserRole)
        return self.store.db.execute("SELECT * FROM dishes WHERE id=?",(dish_id,)).fetchone()

    def new_dish(self):self.dish_dialog()
    def edit_dish(self):
        row=self.current_catalog_row()
        if row:self.dish_dialog(row)
    def dish_dialog(self,row=None):
        dialog=DishDialog(self,row)
        if dialog.exec()!=QDialog.DialogCode.Accepted:return
        name=dialog.name.text().strip()
        if not name:QMessageBox.warning(self,APP_NAME,"Add meg az étel nevét.");return
        self.store.add_dish(name,dialog.category.currentText(),dialog.amount.value(),row["id"] if row else None)
        self.refresh_catalog();self.refresh_daily()
    def delete_dish(self):
        row=self.current_catalog_row()
        if not row:return
        if QMessageBox.question(self,APP_NAME,"Töröljük ezt az ételt az aktuális kínálatból?")==QMessageBox.StandardButton.Yes:
            self.store.delete_dish(row["id"]);self.refresh_catalog();self.refresh_daily()

    def refresh_archive(self):
        if not hasattr(self,"archive"):return
        chosen=self.archive.currentItem();chosen_id=chosen.data(0,Qt.ItemDataRole.UserRole) if chosen else None
        self.archive.clear()
        for row in self.store.saved_menus():
            item=QTreeWidgetItem(["Napi étlap" if row["kind"]=="daily" else "Heti menü",
                                  row["menu_date"],row["saved_at"].replace("T","  ")[:19]])
            item.setData(0,Qt.ItemDataRole.UserRole,row["id"]);self.archive.addTopLevelItem(item)
            if row["id"]==chosen_id:self.archive.setCurrentItem(item)
        self.schedule_preview()

    def reload_themes(self):
        self.theme_packs=load_themes(BASE/"themes_builtin",data_dir()/"themes")
        self.theme.blockSignals(True)
        self.theme.clear();self.theme_keys=list(self.theme_packs)
        for key in self.theme_keys:self.theme.addItem(self.theme_packs[key][0]["name"],key)
        index=self.theme.findData(self.store.setting("theme","classic"));self.theme.setCurrentIndex(max(index,0))
        self.theme.blockSignals(False)

    def save_appearance(self,*_):
        if not hasattr(self,"opacity"):return
        values={"theme":self.theme.currentData() or "classic","decorations":"1" if self.decorations.isChecked() else "0",
                "leader":self.leader.currentData() or "none","background_enabled":"1" if self.bg_enabled.isChecked() else "0",
                "background_opacity":str(self.opacity.value())}
        values.update({"font_"+key:combo.currentFont().family() for key,combo in self.fonts.items()})
        self.store.set_settings(values);self.schedule_preview()

    def pick_color(self,key):
        chosen=QColorDialog.getColor(QColor(self.store.setting("theme_"+key,"#1d6b50")),self)
        if chosen.isValid():self.store.set_settings({"theme_"+key:chosen.name().upper()});self.schedule_preview()

    def use_sample_background(self):
        self.store.set_settings({"background_builtin":"1","background_file":""})
        self.bg_enabled.setChecked(True);self.schedule_preview()
    def clear_background(self):
        self.store.set_settings({"background_builtin":"0","background_file":""})
        self.bg_enabled.setChecked(False);self.schedule_preview()
    def import_background(self):
        path,_=QFileDialog.getOpenFileName(self,"Háttérgrafika importálása","","PNG/JPEG (*.png *.jpg *.jpeg)")
        if not path:return
        source=Path(path)
        from PyQt6.QtGui import QImageReader
        reader=QImageReader(path);size=reader.size()
        if source.stat().st_size>20_000_000 or size.width()<800 or size.height()<1000 or size.width()*size.height()>36_000_000:
            QMessageBox.warning(self,APP_NAME,"Legalább 800 × 1000 px, legfeljebb 20 MB és 36 MP méretű képet válassz.");return
        folder=data_dir()/"backgrounds";folder.mkdir(exist_ok=True)
        name=hashlib.sha256(source.read_bytes()).hexdigest()[:20]+source.suffix.lower()
        shutil.copyfile(source,folder/name)
        self.store.set_settings({"background_file":name,"background_builtin":"0"})
        self.bg_enabled.setChecked(True);self.schedule_preview()
    def import_theme(self):
        path,_=QFileDialog.getOpenFileName(self,"Témacsomag importálása","","ZIP (*.zip)")
        if not path:return
        try:
            slug=import_theme(Path(path),data_dir()/"themes",set(self.theme_packs))
            self.store.set_settings({"theme":slug,"theme_primary":"","theme_accent":""})
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

    def on_tab(self,index):self.schedule_preview()
    def preview_source(self):
        index=self.tabs.currentIndex()
        if index==1:return self.store,"weekly",self.current_week()
        if index==3:
            item=self.archive.currentItem()
            if item:
                row,definition=self.store.saved_menu(item.data(0,Qt.ItemDataRole.UserRole))
                target=date.fromisoformat(row["menu_date"])
                return ArchivedMenu(row["kind"],target,definition),row["kind"],target
        return self.store,"daily",self.current_day()
    def schedule_preview(self):
        if hasattr(self,"preview"):self.timer.start(180)
    def refresh_preview(self):
        try:
            source,kind,target=self.preview_source()
            image=render_image(source,kind,target)
            self._image=image
            self.preview_title.setText(("Napi étlap" if kind=="daily" else "Heti menü")+" · "+display_date(target))
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
        if hasattr(self,"preview"):QTimer.singleShot(60,self.fit_preview)
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
