"""Persistent menu data and dated snapshots shared by the Qt desktop app."""
from __future__ import annotations
import json
import sqlite3
import unicodedata
from datetime import date, datetime, timedelta
from pathlib import Path
from catalog_seed import starter_dishes

APP_NAME = "ÉtlapStúdió"
CATEGORIES = [
    "Levesek", "Főzelékek", "Feltétek", "Köretek", "Savanyúságok",
    "Készételek", "Frissensültek", "Tészták, desszertek", "Mártások, öntetek", "Egyéb", "Menü",
]
WEEKDAYS = ["Hétfő", "Kedd", "Szerda", "Csütörtök", "Péntek"]
GREEN = "#1D6B50"
DEEP = "#123F32"
PAPER = "#F7F8F4"
TEXT = "#21342D"
def data_dir() -> Path:
    root = Path.home() / "Documents" / "EtlapStudio"
    root.mkdir(parents=True, exist_ok=True)
    return root


def monday(day: date) -> date:
    return day - timedelta(days=day.weekday())


def display_date(day: date) -> str:
    return day.strftime("%Y.%m.%d.")


def price(amount: int) -> str:
    return f"{amount:,}".replace(",", " ") + " Ft" if amount else "—"


def normalized_name(name: str) -> str:
    return unicodedata.normalize("NFKC", name).casefold().strip()


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
                    price INTEGER NOT NULL CHECK(price >= 0), active INTEGER NOT NULL DEFAULT 1,
                    promo_enabled INTEGER NOT NULL DEFAULT 0,
                    promo_price INTEGER CHECK(promo_price >= 0)
                );
                CREATE TABLE IF NOT EXISTS daily_selection (
                    day TEXT NOT NULL, dish_id INTEGER NOT NULL REFERENCES dishes(id),
                    PRIMARY KEY(day, dish_id)
                );
                CREATE TABLE IF NOT EXISTS daily_promotions (
                    day TEXT NOT NULL, dish_id INTEGER NOT NULL REFERENCES dishes(id),
                    promo_price INTEGER NOT NULL CHECK(promo_price >= 0),
                    PRIMARY KEY(day,dish_id)
                );
                CREATE TABLE IF NOT EXISTS weekly_menu (
                    day TEXT PRIMARY KEY, soup TEXT NOT NULL DEFAULT '',
                    menu_a TEXT NOT NULL DEFAULT '', menu_b TEXT NOT NULL DEFAULT ''
                );
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY, value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS saved_menus (
                    id INTEGER PRIMARY KEY,
                    kind TEXT NOT NULL CHECK(kind IN ('daily','weekly')),
                    menu_date TEXT NOT NULL,
                    saved_at TEXT NOT NULL,
                    definition TEXT NOT NULL,
                    UNIQUE(kind,menu_date)
                );
            """)
            columns={row[1] for row in self.db.execute("PRAGMA table_info(dishes)")}
            if "promo_enabled" not in columns:
                self.db.execute("ALTER TABLE dishes ADD COLUMN promo_enabled INTEGER NOT NULL DEFAULT 0")
            if "promo_price" not in columns:
                self.db.execute("ALTER TABLE dishes ADD COLUMN promo_price INTEGER")
        self._archive_existing()
        if not self.db.execute("SELECT 1 FROM dishes LIMIT 1").fetchone():
            self.import_starter_catalogue()

    def import_starter_catalogue(self) -> int:
        """Add missing starter dishes; preserve all existing names, prices and deletions."""
        existing = {(row[0], normalized_name(row[1])) for row in
                    self.db.execute("SELECT category,name FROM dishes")}
        additions = []
        for dish in starter_dishes():
            key = (dish.category, normalized_name(dish.name))
            if key not in existing:
                additions.append((dish.name, dish.category, dish.price))
                existing.add(key)
        with self.db:
            self.db.executemany("INSERT INTO dishes(name,category,price) VALUES(?,?,?)", additions)
        return len(additions)

    def dishes(self, query: str = ""):
        return self.db.execute(
            "SELECT * FROM dishes WHERE active=1 AND (name LIKE ? OR category LIKE ?) "
            "ORDER BY category, name COLLATE NOCASE, id",
            (f"%{query}%", f"%{query}%"),
        ).fetchall()

    def daily_dishes(self, query: str = ""):
        return [row for row in self.dishes(query) if row["category"] != "Menü"]

    def menu_suggestions(self):
        return [row[0] for row in self.db.execute(
            "SELECT name FROM dishes WHERE active=1 AND category='Menü' "
            "ORDER BY name COLLATE NOCASE")]

    def add_dish(self, name: str, category: str, amount: int, dish_id=None,
                 promo_enabled=False, promo_price=None):
        if promo_enabled and (promo_price is None or not 0 <= promo_price < amount):
            raise ValueError("Az akciós árnak kisebbnek kell lennie a normál árnál.")
        promo_price=promo_price if promo_enabled else None
        with self.db:
            if dish_id:
                self.db.execute("UPDATE dishes SET name=?, category=?, price=?,promo_enabled=?,promo_price=? WHERE id=?",
                                (name, category, amount, int(promo_enabled),promo_price,dish_id))
                self.db.execute("DELETE FROM daily_promotions WHERE dish_id=? AND promo_price>=?",
                                (dish_id,amount))
            else:
                self.db.execute("INSERT INTO dishes(name,category,price,promo_enabled,promo_price) VALUES(?,?,?,?,?)",
                                (name, category, amount,int(promo_enabled),promo_price))

    def delete_dish(self, dish_id: int):
        with self.db:
            # Soft delete keeps old dated selections and their PDF export intact.
            self.db.execute("UPDATE dishes SET active=0 WHERE id=?", (dish_id,))

    def selection(self, day: date):
        return self.db.execute("""
            SELECT d.id,d.name,d.category,d.price,d.active,
                   CASE WHEN dp.promo_price IS NOT NULL THEN 1 ELSE d.promo_enabled END AS promo_enabled,
                   COALESCE(dp.promo_price,d.promo_price) AS promo_price
            FROM daily_selection s JOIN dishes d ON d.id=s.dish_id
            LEFT JOIN daily_promotions dp ON dp.day=s.day AND dp.dish_id=d.id
            WHERE s.day=? ORDER BY d.category, d.name COLLATE NOCASE
        """, (day.isoformat(),)).fetchall()

    def set_selected(self, day: date, dish_ids: list[int]):
        with self.db:
            self.db.execute("DELETE FROM daily_selection WHERE day=?", (day.isoformat(),))
            self.db.executemany("INSERT INTO daily_selection(day,dish_id) VALUES(?,?)",
                                [(day.isoformat(), x) for x in dish_ids])
            if dish_ids:
                self.db.execute("DELETE FROM daily_promotions WHERE day=? AND dish_id NOT IN ("+
                                ",".join("?"*len(dish_ids))+")",(day.isoformat(),*dish_ids))
            else:self.db.execute("DELETE FROM daily_promotions WHERE day=?",(day.isoformat(),))

    def copy_previous_daily(self, day: date) -> bool:
        """Use the most recent saved working selection as the starting point for a new day."""
        current=day.isoformat()
        if self.db.execute("SELECT 1 FROM saved_menus WHERE kind='daily' AND menu_date=?",(current,)).fetchone():
            return False
        if self.db.execute("SELECT 1 FROM daily_selection WHERE day=? LIMIT 1",(current,)).fetchone():
            return False
        previous=self.db.execute("SELECT MAX(day) FROM daily_selection WHERE day<?",(current,)).fetchone()[0]
        if previous:
            with self.db:
                rows=self.db.execute("SELECT dish_id FROM daily_selection WHERE day=?",(previous,)).fetchall()
                self.db.executemany("INSERT OR IGNORE INTO daily_selection(day,dish_id) VALUES(?,?)",
                                    [(current,row[0]) for row in rows])
                promos=self.db.execute("SELECT dish_id,promo_price FROM daily_promotions WHERE day=?",(previous,)).fetchall()
                self.db.executemany("INSERT OR IGNORE INTO daily_promotions(day,dish_id,promo_price) VALUES(?,?,?)",
                                    [(current,row[0],row[1]) for row in promos])
        prior_day=day-timedelta(days=1)
        prior_special=self.week_entry(prior_day)
        current_special=self.week_entry(day)
        if any(prior_special) and not any(current_special):
            self.set_week_entry(day,*prior_special)
        return bool(previous or any(prior_special))

    def set_daily_promotion(self, day: date, dish_id: int, enabled: bool, amount=None):
        regular=self.db.execute("SELECT price FROM dishes WHERE id=?",(dish_id,)).fetchone()
        if regular is None:raise ValueError("Az étel nem található.")
        if enabled and (amount is None or not 0<=amount<regular[0]):
            raise ValueError("Az akciós ár legyen kisebb a normál árnál.")
        with self.db:
            if enabled:
                self.db.execute("""INSERT INTO daily_promotions(day,dish_id,promo_price)
                    VALUES(?,?,?) ON CONFLICT(day,dish_id) DO UPDATE SET promo_price=excluded.promo_price""",
                    (day.isoformat(),dish_id,amount))
            else:self.db.execute("DELETE FROM daily_promotions WHERE day=? AND dish_id=?",
                                 (day.isoformat(),dish_id))

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

    def menu_settings(self):
        return {row["key"]:row["value"] for row in
                self.db.execute("SELECT key,value FROM settings")}

    def snapshot(self, kind: str, day: date):
        if kind == "daily":
            soup,a,b=self.week_entry(day)
            return {"settings":self.menu_settings(),"special":{"soup":soup,"menu_a":a,"menu_b":b},
                    "dishes":[{key:row[key] for key in ("id","name","category","price","promo_enabled","promo_price")}
                              for row in self.selection(day)]}
        mon=monday(day)
        return {"settings":self.menu_settings(),"days":[
            dict(zip(("soup","menu_a","menu_b"),self.week_entry(mon+timedelta(days=i))))
            for i in range(5)]}

    def save_menu(self, kind: str, day: date):
        if kind not in ("daily","weekly"):raise ValueError("Ismeretlen étlaptípus.")
        day=monday(day) if kind=="weekly" else day
        definition=self.snapshot(kind,day)
        now=datetime.now().astimezone().isoformat(timespec="seconds")
        with self.db:
            self.db.execute("""INSERT INTO saved_menus(kind,menu_date,saved_at,definition)
                VALUES(?,?,?,?) ON CONFLICT(kind,menu_date) DO UPDATE SET
                saved_at=excluded.saved_at,definition=excluded.definition""",
                (kind,day.isoformat(),now,json.dumps(definition,ensure_ascii=False)))

    def saved_menus(self):
        return self.db.execute("SELECT id,kind,menu_date,saved_at FROM saved_menus "
                               "ORDER BY menu_date DESC,kind,id DESC").fetchall()

    def saved_menu(self, menu_id: int):
        row=self.db.execute("SELECT * FROM saved_menus WHERE id=?",(menu_id,)).fetchone()
        if row is None:raise ValueError("A mentett étlap nem található.")
        return row, json.loads(row["definition"])

    def _archive_existing(self):
        # Old installations already contain dated selections, but no snapshots.
        dates=self.db.execute("SELECT DISTINCT day FROM daily_selection").fetchall()
        weeks=self.db.execute("SELECT DISTINCT day FROM weekly_menu WHERE "
                              "soup<>'' OR menu_a<>'' OR menu_b<>''").fetchall()
        for (raw,) in dates:
            if not self.db.execute("SELECT 1 FROM saved_menus WHERE kind='daily' AND menu_date=?",(raw,)).fetchone():
                self.save_menu("daily",date.fromisoformat(raw))
        for mon in {monday(date.fromisoformat(row[0])) for row in weeks}:
            if not self.db.execute("SELECT 1 FROM saved_menus WHERE kind='weekly' AND menu_date=?",(mon.isoformat(),)).fetchone():
                self.save_menu("weekly",mon)


class ArchivedMenu:
    """Read-only Store interface for PDF/PNG export of an exact saved definition."""
    def __init__(self, kind, menu_date, definition):
        self.kind,self.menu_date,self.definition=kind,menu_date,definition

    def setting(self,key,default=""):
        return self.definition.get("settings",{}).get(key,default)

    def selection(self,day):
        return self.definition.get("dishes",[]) if self.kind=="daily" and day==self.menu_date else []

    def week_entry(self,day):
        if self.kind=="daily":
            data=self.definition.get("special",{}) if day==self.menu_date else {}
        else:
            offset=(day-self.menu_date).days
            days=self.definition.get("days",[])
            data=days[offset] if 0<=offset<len(days) else {}
        return tuple(data.get(key,"") for key in ("soup","menu_a","menu_b"))

