"""Clean seasonal menu artwork and full-bleed PDF/PNG rendering."""
from __future__ import annotations

from datetime import date, timedelta
import math
from pathlib import Path
import sys
from PyQt6.QtCore import QMarginsF, QPointF, QRectF, Qt
from PyQt6.QtGui import (QColor, QFont, QFontMetricsF, QImage, QPainter,
                         QPageSize, QPdfWriter, QPainterPath, QPen, QTextDocument)
from themes import HEX, load_themes
from menu_core import CATEGORIES, WEEKDAYS, data_dir, display_date, monday, price

W=1440
H=round(W*297/210)
A4_WIDTH_PT=595.27559055
COORD_UNITS_PER_POINT=W/A4_WIDTH_PT
EXPORT_DPI=150
EXPORT_WIDTH=round(210/25.4*EXPORT_DPI)
EXPORT_HEIGHT=round(297/25.4*EXPORT_DPI)
BASE=Path(__file__).resolve().parent


def setting(source,key,default=""):
    return source.setting(key,default)


def style_size(source,role,default):
    try:
        if setting(source,"advanced_typography","0")!="1":
            return float(default)*COORD_UNITS_PER_POINT
        stored=setting(source,"font_size_"+role)
        value=float(stored) if stored else float(default)
        if stored and setting(source,"font_size_unit","px") not in ("pt_a4_300","pt_a4"):value*=A4_WIDTH_PT/W
        return max(4.0,min(48.0,value))*COORD_UNITS_PER_POINT
    except (TypeError,ValueError):return default*COORD_UNITS_PER_POINT


def asset_file(name):
    candidates=[BASE/"design_assets"/name,
                Path(getattr(sys,"_MEIPASS",BASE))/"design_assets"/name,
                Path(sys.executable).resolve().parent/"design_assets"/name,
                Path.cwd()/"design_assets"/name]
    return next((path for path in candidates if path.is_file()),candidates[0])


def font(source,role,size,bold=False):
    defaults={"header_title":"Segoe UI","header_date":"Segoe UI","header_contact":"Segoe UI",
              "daily_title":"Georgia","daily_label":"Segoe UI","daily_value":"Segoe UI",
              "menu_price_label":"Segoe UI","menu_price_value":"Georgia",
              "category_title":"Georgia","dish_name":"Segoe UI","dish_price":"Segoe UI",
              "promo_old_price":"Segoe UI","promo_new_price":"Segoe UI","promo_badge":"Segoe UI",
              "weekday_title":"Georgia","weekly_label":"Segoe UI","weekly_value":"Segoe UI",
              "footer_note":"Georgia"}
    legacy={"header_title":"title","header_date":"special","header_contact":"special",
            "daily_title":"heading","daily_label":"heading","daily_value":"special",
            "menu_price_label":"special","menu_price_value":"title","category_title":"heading",
            "dish_name":"dish","dish_price":"dish","promo_old_price":"dish",
            "promo_new_price":"dish","promo_badge":"dish","weekday_title":"heading",
            "weekly_label":"heading","weekly_value":"special","footer_note":"special"}
    if setting(source,"advanced_typography","0")=="1":
        family=setting(source,"font_"+role) or setting(source,"font_"+legacy.get(role,""),defaults.get(role,"Segoe UI"))
    else:
        heading_roles={"header_title","daily_title","menu_price_value","category_title","weekday_title"}
        family=setting(source,"font_heading" if role in heading_roles else "font_body",
                       "Georgia" if role in heading_roles else "Segoe UI")
    family={"Modern sans":"DejaVu Sans","Klasszikus talpas":"DejaVu Serif"}.get(family,family)
    f=QFont(family);f.setPixelSize(max(1,round(size)));f.setBold(bold)
    return f


def text(p,source,role,size,color,x,y,w,h,value,bold=False,align=Qt.AlignmentFlag.AlignLeft):
    p.setFont(font(source,role,size,bold));p.setPen(QColor(color))
    p.drawText(QRectF(x,y,w,h),Qt.TextFlag.TextWordWrap|align,str(value))


def measure(value,source,role,size,width,bold=False):
    metrics=QFontMetricsF(font(source,role,size,bold))
    rect=metrics.boundingRect(QRectF(0,0,width,3000),Qt.TextFlag.TextWordWrap,str(value))
    return max(metrics.height(),rect.height())


def wrapped_lines(value,source,role,size,width,bold=False):
    """Word-wrap explicitly so the price can align with the dish's final line."""
    metrics=QFontMetricsF(font(source,role,size,bold));lines=[]
    for paragraph in str(value).splitlines() or [""]:
        words=paragraph.split();line=""
        for word in words:
            candidate=(line+" "+word).strip()
            if line and metrics.horizontalAdvance(candidate)>width:
                lines.append(line);line=word
            else:line=candidate
        lines.append(line)
    return lines


def text_singleline(p,source,role,size,color,x,y,w,h,value,bold=False,align=Qt.AlignmentFlag.AlignLeft):
    p.setFont(font(source,role,size,bold));p.setPen(QColor(color))
    p.drawText(QRectF(x,y,w,h),align|Qt.AlignmentFlag.AlignVCenter,str(value))


def _easter_sunday(year):
    a=year%19;b=year//100;c=year%100;d=b//4;e=b%4;f=(b+8)//25;g=(b-f+1)//3
    h=(19*a+b-d-g+15)%30;i=c//4;k=c%4;l=(32+2*e+2*i-h-k)%7;m=(a+11*h+22*l)//451
    month=(h+l-7*m+114)//31;day=(h+l-7*m+114)%31+1
    return date(year,month,day)


def is_easter_period(target):
    """Easter styling runs for weekdays in the two weeks before Easter Sunday."""
    easter=_easter_sunday(target.year)
    return target.weekday()<5 and easter-timedelta(days=14)<=target<easter


def is_christmas_period(target):
    """Christmas styling is reserved for open days before Christmas Eve."""
    return target.month==12 and 1<=target.day<=23


def is_workday_window_before(target,holiday,workdays=5):
    """True for the last N Monday-Friday dates before a fixed holiday."""
    end=holiday-timedelta(days=1)
    while end.weekday()>=5:end-=timedelta(days=1)
    start=end;remaining=max(1,workdays)-1
    while remaining:
        start-=timedelta(days=1)
        if start.weekday()<5:remaining-=1
    return target.weekday()<5 and start<=target<=end


def is_valentine_period(target):
    """Last workweek before Valentine's Day, plus the day itself if the restaurant is open."""
    holiday=date(target.year,2,14)
    return is_workday_window_before(target,holiday,5) or (target==holiday and target.weekday()<5)


def seasonal_colors(target):
    """Seasonal palette with clearer color and stronger contrast."""
    if is_easter_period(target):
        return ("#3F6A3C","#D34A37","#F2DDB4")
    if is_valentine_period(target):
        return ("#71283C","#D44855","#F2D5D5")
    if is_workday_window_before(target,date(target.year,8,20),5):
        return ("#285E42","#D33C32","#F1DDB5")
    if target.month==10 and target.day>=20:
        return ("#803D25","#D14B28","#F0D3A8")
    if is_christmas_period(target):
        return ("#285943","#C83A32","#EDE0C1")
    if target.month in (1,2):return ("#496578","#B84338","#E0E8E9")
    if target.month in (6,7,8):return ("#4A6938","#D94E2E","#F4D99A")
    if target.month in (9,10,11):return ("#803D25","#D14B28","#F0D3A8")
    return ("#3F6A3C","#D34A37","#F2DDB4")


def colors(source,target):
    key=setting(source,"theme","auto")
    if key=="valentine":return ("#71283C","#D44855","#F2D5D5")
    if key in ("august20","national_day"):return ("#285E42","#D33C32","#F1DDB5")
    if key=="auto" or setting(source,"auto_theme","1")=="1":return seasonal_colors(target)
    packs=load_themes(BASE/"themes_builtin",data_dir()/"themes")
    if key in packs:
        palette=packs[key][0]["palette"]
        return palette["primary"],palette["accent"],palette["background"]
    p=setting(source,"theme_primary");a=setting(source,"theme_accent")
    default=seasonal_colors(target)
    return (p if HEX.fullmatch(p) else default[0],a if HEX.fullmatch(a) else default[1],default[2])


def theme_assets(source,target):
    key=setting(source,"theme","auto")
    automatic=key=="auto" or setting(source,"auto_theme","1")=="1"
    root=BASE/"design_assets"/"dividers"
    if automatic:
        return {"background":theme_background_path("auto",target),"divider_root":root,"divider_theme":None}
    packs=load_themes(BASE/"themes_builtin",data_dir()/"themes")
    if key not in packs:
        return {"background":theme_background_path(key,target),"divider_root":root,
                "divider_theme":theme_season(key,target)}
    manifest,folder=packs[key]
    assets={name:folder/filename for name,filename in manifest.get("assets",{}).items()
            if name in ("divider","background") and filename.lower().endswith((".png",".jpg",".jpeg")) and (folder/filename).is_file()}
    variants=[folder/name for name in manifest.get("divider_variants",[]) if (folder/name).is_file()]
    if variants:assets["divider_variants"]=variants
    assets.setdefault("background",theme_background_path(key,target))
    assets["divider_root"]=root
    assets["divider_theme"]=theme_season(key,target)
    return assets


def draw_theme_asset(p,assets,key,rect,opacity=0.75):
    path=assets.get(key)
    if not path:return False
    image=QImage(str(path))
    if image.isNull():return False
    p.save();p.setOpacity(opacity);p.drawImage(rect,image);p.restore();return True


def guide(source,kind,name,default):
    try:return max(80,min(H-70,int(setting(source,f"guide_{kind}_{name}",str(default)))))
    except (ValueError,TypeError):return default


def season_key(target):
    if is_easter_period(target):return "spring"
    if is_valentine_period(target):return "valentine"
    if is_workday_window_before(target,date(target.year,8,20),5):return "august20"
    if target.month in (12,1,2):return "winter"
    if target.month in (6,7,8):return "summer"
    if target.month in (9,10,11):return "autumn"
    return "spring"


def divider_season_key(target):
    if is_easter_period(target):return "easter"
    if is_christmas_period(target):return "christmas"
    if is_valentine_period(target):return "valentine"
    if is_workday_window_before(target,date(target.year,8,20),5):return "august20"
    return season_key(target)


def theme_season(key,target):
    key=(key or "").casefold()
    for tokens,season in ((('christmas',),'christmas'),(('easter',),'easter'),
                          (('valentine',),'valentine'),(('august20','national_day'),'august20'),
                          (('winter',),'winter'),(('autumn','fall'),'autumn'),
                          (('summer',),'summer'),(('spring',),'spring'),(('classic',),'classic')):
        if any(token in key for token in tokens):return season
    return divider_season_key(target)


def theme_background_path(key,target):
    """Holiday art stays distinct from its generic seasonal counterpart."""
    name=(key or "auto").casefold()
    if name=="auto":
        if is_easter_period(target):name="easter"
        elif is_christmas_period(target):name="christmas"
        elif is_valentine_period(target):name="valentine"
        elif is_workday_window_before(target,date(target.year,8,20),5):name="august20"
        else:name=season_key(target)
    if "valentine" in name:return BASE/"design_assets"/"valentine_background.jpg"
    if "august20" in name:return BASE/"design_assets"/"august20_background.jpg"
    if "easter" in name:return BASE/"design_assets"/"spring_background.jpg"
    if "christmas" in name:return BASE/"design_assets"/"winter_background.jpg"
    if "spring" in name:return BASE/"design_assets"/"spring_generic_background.jpg"
    if "winter" in name:return BASE/"design_assets"/"winter_generic_background.jpg"
    if "summer" in name:return BASE/"design_assets"/"summer_background.jpg"
    if "autumn" in name or "fall" in name:return BASE/"design_assets"/"autumn_background.jpg"
    return BASE/"design_assets"/f"{season_key(target)}_background.jpg"


def seasonal_art(target,kind):
    path=BASE/"design_assets"/f"{season_key(target)}_{kind}.jpg"
    if path.is_file():
        image=QImage(str(path))
        if not image.isNull():return image


def glass(p,rect,opacity=205,radius=20,tint="#4D6A43",source=None):
    """Readable pastel-tinted glass, with per-template color and opacity controls."""
    if source is not None:
        try:opacity=round(255*max(25,min(100,int(setting(source,"glass_opacity","80"))))/100)
        except (TypeError,ValueError):opacity=204
        if setting(source,"glass_color_mode","auto")=="custom":
            candidate=QColor(setting(source,"glass_color","#DDE7D8"))
            if candidate.isValid():tint=candidate.name()
    shade=QColor(tint);mix=.38
    fill=QColor(round(255*(1-mix)+shade.red()*mix),
                round(255*(1-mix)+shade.green()*mix),
                round(255*(1-mix)+shade.blue()*mix),max(0,min(255,opacity)))
    p.save();p.setPen(Qt.PenStyle.NoPen);p.setBrush(fill);p.drawRoundedRect(rect,radius,radius);p.restore()


def divider(p,primary,accent,y,assets=None,target=None,height=30):
    """Thin seasonal line-art divider; deliberately avoids filled image blocks."""
    variants=assets.get("divider_variants",[]) if assets else []
    if variants:
        variant=variants[(target.toordinal() if target else 0)%len(variants)]
        if draw_theme_asset(p,{"divider":variant},"divider",QRectF(120,y-height/2,W-240,height),.95):return
    path=assets.get("divider") if assets else None
    if path and Path(path).suffix.lower()==".png" and draw_theme_asset(p,assets,"divider",QRectF(120,y-height/2,W-240,height),.95):return
    root=assets.get("divider_root") if assets else None
    if root:
        season=assets.get("divider_theme") or divider_season_key(target) if target else (assets.get("divider_theme") or "winter")
        variants=sorted((Path(root)/season).glob("divider_*.png"))
        if variants:
            variant=variants[(target.toordinal() if target else 0)%len(variants)]
            if draw_theme_asset(p,{"divider":variant},"divider",QRectF(120,y-height/2,W-240,height),.92):return
    month=target.month if target else 1
    season="winter" if month in (12,1,2) else "spring" if month in (3,4,5) else "summer" if month in (6,7,8) else "autumn"
    p.save();p.translate(0,y);p.scale(1,height/80);p.translate(0,-y)
    line=QColor(accent);line.setAlpha(145);orn=QColor(primary);orn.setAlpha(185)
    p.setBrush(Qt.BrushStyle.NoBrush);pen=QPen(line,1.7);pen.setCapStyle(Qt.PenCapStyle.RoundCap);pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin);p.setPen(pen)
    mid=W/2;gap=68
    p.drawLine(55,y,mid-gap,y);p.drawLine(mid+gap,y,W-55,y)
    # Short accent strokes soften the ends and connect the motif to the line.
    p.setPen(QPen(orn,1.25))
    if season=="winter":
        for cx,cy,r in ((mid,y,17),(mid-34,y,8),(mid+34,y,8)):
            for angle in (0,60,120):
                dx=r*math.cos(math.radians(angle));dy=r*math.sin(math.radians(angle))
                p.drawLine(QPointF(cx-dx,cy-dy),QPointF(cx+dx,cy+dy))
    elif season=="spring":
        for cx in (mid-34,mid,mid+34):
            p.drawEllipse(QPointF(cx,y),3.2,3.2)
            for angle in range(0,360,72):
                rad=math.radians(angle);p.drawEllipse(QPointF(cx+8*math.cos(rad),y+8*math.sin(rad)),3.2,3.2)
        p.drawLine(QPointF(mid-60,y),QPointF(mid-43,y));p.drawLine(QPointF(mid+43,y),QPointF(mid+60,y))
    elif season=="summer":
        p.drawLine(QPointF(mid-47,y+6),QPointF(mid+47,y-6))
        for offset in (-30,-10,10,30):
            yy=y-offset*.13
            leaf=QPainterPath();leaf.moveTo(mid+offset,yy);leaf.quadTo(mid+offset-12,yy-13,mid+offset-20,yy-2);leaf.quadTo(mid+offset-12,yy+5,mid+offset,yy);p.drawPath(leaf)
            leaf=QPainterPath();leaf.moveTo(mid+offset,yy);leaf.quadTo(mid+offset+12,yy+13,mid+offset+20,yy+2);leaf.quadTo(mid+offset+12,yy-5,mid+offset,yy);p.drawPath(leaf)
    else:
        for cx,tilt in ((mid-28,-1),(mid,1),(mid+28,-1)):
            leaf=QPainterPath();leaf.moveTo(cx,y+13);leaf.cubicTo(cx-tilt*15,y+4,cx-tilt*12,y-10,cx,y-17);leaf.cubicTo(cx+tilt*14,y-9,cx+tilt*15,y+5,cx,y+13);leaf.moveTo(cx,y+13);leaf.lineTo(cx,y-15);leaf.moveTo(cx,y+3);leaf.lineTo(cx-tilt*7,y-3);leaf.moveTo(cx,y-5);leaf.lineTo(cx+tilt*7,y-11);p.drawPath(leaf)
    p.restore()


def draw_header(p,source,kind,target,primary,accent,dark,paper,decorated,glass_enabled,assets):
    if glass_enabled:glass(p,QRectF(40,28,W-80,176),205,8,primary,source)
    logo=asset_file("megyehaza_wordmark.png")
    if logo.is_file():
        image=QImage(str(logo))
        if not image.isNull():
            box=QRectF(62,47,370,140)
            scale=min(box.width()/image.width(),box.height()/image.height())
            width=image.width()*scale;height=image.height()*scale
            p.drawImage(QRectF(box.x()+(box.width()-width)/2,box.y()+(box.height()-height)/2,width,height),image)
    name=setting(source,"restaurant_name","Megyeháza Étterem") or "Megyeháza Étterem"
    details=(setting(source,"address","Miskolc, Városház tér 1."),
             setting(source,"phone","+36 30 / 513 2605"),
             setting(source,"facebook_url","https://www.facebook.com/share/1GQgCcNJXE/"))
    title=(setting(source,"special_title","") or "") if kind=="special" else ("Napi étlap" if kind=="daily" else "Heti menü")
    stamp=display_date(target) if kind in ("daily","special") else display_date(monday(target))+" – "+display_date(monday(target)+timedelta(days=4))
    title_size=style_size(source,"daily_title",22)
    if kind!="special" or setting(source,"special_show_title","0")=="1":
        if title:text_singleline(p,source,"daily_title",title_size,primary,470,66,500,55,title,True,Qt.AlignmentFlag.AlignHCenter|Qt.AlignmentFlag.AlignVCenter)
    if kind!="special" or setting(source,"special_show_date","0")=="1":
        text_singleline(p,source,"header_date",style_size(source,"header_date",16),dark,470,122,500,42,stamp,True,Qt.AlignmentFlag.AlignHCenter|Qt.AlignmentFlag.AlignVCenter)
    name_size=style_size(source,"header_title",11)
    name_metrics=QFontMetricsF(font(source,"header_title",name_size)).horizontalAdvance(name)
    if name_metrics>410:name_size=max(6,name_size*410/name_metrics)
    text_singleline(p,source,"header_title",name_size,dark,970,47,410,32,name,False,Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter)
    contact_size=style_size(source,"header_contact",11)
    for index,value in enumerate(details):
        if value.strip():
            size=contact_size
            width=QFontMetricsF(font(source,"header_contact",size)).horizontalAdvance(value)
            if width>410:size=max(6,size*410/width)
            text_singleline(p,source,"header_contact",size,dark,970,82+index*35,410,32,value,False,Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter)


class KindSettings:
    """Overlay per-menu design keys while sharing restaurant and content settings."""
    def __init__(self,source,kind):self.source,self.kind=source,kind
    def setting(self,key,default=""):
        specific=self.source.setting(self.kind+"_"+key,None)
        return self.source.setting(key,default) if specific is None else specific
    def __getattr__(self,name):return getattr(self.source,name)


def draw_menu(p,source,kind,target):
    source=KindSettings(source,kind)
    p.save();p.setRenderHint(QPainter.RenderHint.Antialiasing);p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    primary,accent,paper=colors(source,target);dark="#2D342E"
    assets=theme_assets(source,target)
    p.fillRect(QRectF(0,0,W,H),QColor(paper))
    background_path=assets.get("background") if assets else None
    background=QImage(str(background_path)) if background_path else seasonal_art(target,"background")
    if background is not None and background.isNull():background=seasonal_art(target,"background")
    if background is not None:
        p.save();p.setOpacity(.62);p.drawImage(QRectF(0,0,W,H),background);p.restore()
        p.fillRect(QRectF(0,0,W,H),QColor(QColor(paper).red(),QColor(paper).green(),QColor(paper).blue(),85))
    glass_enabled=setting(source,"glass_panels","1")=="1"
    decorated=setting(source,"decorations","1")=="1"
    header_default=205
    header_y=guide(source,kind,"header",header_default)
    p.save();p.translate(0,header_y-header_default)
    draw_header(p,source,kind,target,primary,accent,dark,paper,decorated,glass_enabled,assets)
    p.restore()
    if kind=="daily":
        menu_end=guide(source,kind,"menu_end",438)
        draw_daily(p,source,target,primary,accent,dark,decorated,glass_enabled,assets,
                   header_y-header_default,menu_end-438)
    elif kind=="weekly":
        panel_shift=header_y-header_default
        if glass_enabled:glass(p,QRectF(40,220+panel_shift,W-80,88),205,8,primary,source)
        try:menu_price=int(setting(source,"daily_menu_price","2800") or "0")
        except (TypeError,ValueError):menu_price=2800
        text_singleline(p,source,"menu_price_label",style_size(source,"menu_price_label",12),primary,470,222+panel_shift,500,30,"Napi menü ára",True,Qt.AlignmentFlag.AlignHCenter|Qt.AlignmentFlag.AlignVCenter)
        text_singleline(p,source,"menu_price_value",style_size(source,"menu_price_value",20),dark,470,252+panel_shift,500,52,price(menu_price),True,Qt.AlignmentFlag.AlignHCenter|Qt.AlignmentFlag.AlignVCenter)
        days_y=guide(source,kind,"days",330)
        draw_weekly(p,source,target,primary,accent,dark,decorated,glass_enabled,assets,
                    days_y-330+panel_shift)
    else:
        top=225+(header_y-header_default)
        bottom=H-100
        panel=QRectF(52,top,W-104,bottom-top)
        if glass_enabled:glass(p,panel,205,12,primary,source)
        document=QTextDocument()
        document.setDefaultFont(font(source,"weekly_value",style_size(source,"weekly_value",16)))
        document.setDocumentMargin(28)
        document.setHtml(setting(source,"special_html","") or "<p></p>")
        document.setTextWidth(panel.width()-56)
        content_width=panel.width()-56;content_height=panel.height()-52
        fit=min(1.0,content_height/max(1.0,document.size().height()))
        p.save();p.setClipRect(panel.adjusted(20,18,-20,-18));p.translate(panel.left()+28,panel.top()+26);p.scale(fit,fit)
        document.drawContents(p,QRectF(0,0,content_width,document.size().height()));p.restore()
    note=setting(source,"note").strip()
    if note:
        # Keep the footer close to the bottom edge of the A4 canvas. The old
        # fixed daily coordinate left a large, unused strip below the note.
        note_y=H-76
        if glass_enabled:glass(p,QRectF(40,note_y,W-80,58),195,8,primary,source)
        text(p,source,"footer_note",style_size(source,"footer_note",10),dark,60,note_y+10,W-120,38,note[:130],align=Qt.AlignmentFlag.AlignHCenter)
    p.restore()


def draw_daily(p,source,target,primary,accent,dark,decorated,glass_enabled,assets,header_shift=0,menu_gap_shift=0):
    soup,a,b=source.week_entry(target)
    menu_shift=header_shift
    menu_y=220+menu_shift
    if glass_enabled:glass(p,QRectF(40,menu_y,W-80,205),205,8,primary,source)
    fields=[("Leves",soup or "—"),("A menü",a or "—"),("B menü",b or "—")]
    label_size=style_size(source,"daily_label",13)
    value_size=style_size(source,"daily_value",13)
    label_size=min(label_size,max(6,int(label_size*150/max(1,max(QFontMetricsF(font(source,"daily_label",label_size)).horizontalAdvance(label) for label,_ in fields)))))
    value_size=min(value_size,max(6,int(value_size*760/max(1,max(QFontMetricsF(font(source,"daily_value",value_size)).horizontalAdvance(value) for _,value in fields)))))
    y=menu_y+38
    for label,value in fields:
        height=42
        text_singleline(p,source,"daily_label",label_size,primary,80,y,150,height,label,True)
        text_singleline(p,source,"daily_value",value_size,dark,245,y,760,height,value)
        y+=44
    try:menu_price=int(setting(source,"daily_menu_price","2800") or "0")
    except (TypeError,ValueError):menu_price=2800
    text_singleline(p,source,"menu_price_label",style_size(source,"menu_price_label",12),primary,1085,menu_y+58,260,34,"Napi menü ára",True,Qt.AlignmentFlag.AlignHCenter|Qt.AlignmentFlag.AlignVCenter)
    text_singleline(p,source,"menu_price_value",style_size(source,"menu_price_value",20),dark,1085,menu_y+92,260,58,price(menu_price),True,Qt.AlignmentFlag.AlignHCenter|Qt.AlignmentFlag.AlignVCenter)
    alacarte_shift=header_shift+menu_gap_shift
    if decorated:divider(p,primary,accent,451+alacarte_shift,assets,target,30)
    dishes=[dict(d) for d in source.selection(target)]
    if not dishes:
        if glass_enabled:glass(p,QRectF(40,478+alacarte_shift,W-80,72),205,8,primary,source)
        text(p,source,"dish_name",style_size(source,"dish_name",11),dark,60,494+alacarte_shift,W-120,45,"Még nincs à la carte étel kiválasztva.",align=Qt.AlignmentFlag.AlignHCenter)
        return 550+alacarte_shift
    p.save();p.translate(0,alacarte_shift)
    top=478
    # Reserve a small gap above the footer and let the à la carte columns use
    # the remaining A4 height instead of stopping at the former fixed cutoff.
    max_y=max(top+120,H-150-alacarte_shift)
    def plan(size,columns):
        gap=16;column_width=(1360-gap*(columns-1))/columns;col_x=[40+column*(column_width+gap) for column in range(columns)]
        name_width=column_width-188
        result=[];col=0;y=top
        for category in CATEGORIES:
            rows=[d for d in dishes if d["category"]==category]
            if not rows:continue
            category_h=max(size*1.3,style_size(source,"category_title",14)*1.2)
            line_h=QFontMetricsF(font(source,"dish_name",size)).height()*1.05
            row_items=[]
            for d in rows:
                lines=wrapped_lines(d["name"],source,"dish_name",size,name_width-(62 if d.get("promo_enabled") and d.get("promo_price") is not None else 0))
                row_h=max(line_h*len(lines)+size*.18,size*1.25)
                row_items.append((d,row_h))
            section_gap=14 if y>top else 0
            section_height=section_gap+category_h+sum(row_h for _,row_h in row_items)
            if y+section_height>max_y:
                col+=1;y=top;section_height-=section_gap;section_gap=0
                if col>=columns:return None
            if section_height>max_y-top:return None
            y+=section_gap
            result.append(("heading",col,y,category,size));y+=category_h
            for d,row_h in row_items:
                result.append(("dish",col,y,d,size,row_h));y+=row_h
        return result
    chosen_columns=2;lo,hi=6.0,float(style_size(source,"dish_name",12.5))
    if plan(8.0,2) is None:
        chosen_columns=3;lo,hi=5.0,float(style_size(source,"dish_name",12.5))
    for _ in range(24):
        mid=(lo+hi)/2
        if plan(mid,chosen_columns) is None:hi=mid
        else:lo=mid
    placements=plan(lo,chosen_columns) or plan(5.0,chosen_columns)
    if placements is None:raise ValueError("Túl sok étel az egyképes napi étlaphoz.")
    mode=setting(source,"leader","none")
    gap=16;column_width=(1360-gap*(chosen_columns-1))/chosen_columns
    col_x=[40+column*(column_width+gap) for column in range(chosen_columns)]
    name_width=column_width-188
    sections_by_column={}
    for item in placements:
        col=item[1]
        if item[0]=="heading":
            sections_by_column.setdefault(col,[]).append([item])
        else:
            sections_by_column[col][-1].append(item)
    if glass_enabled:
        for col,sections in sections_by_column.items():
            x=col_x[col]
            for section in sections:
                heading_height=max(section[0][4]*1.3,style_size(source,"category_title",14)*1.2)
                start=section[0][2]+heading_height
                end=max(item[2]+(max(item[4]*1.3,style_size(source,"category_title",14)*1.2)
                                 if item[0]=="heading" else item[5]) for item in section)
                if end>start:glass(p,QRectF(x-3,start,column_width+6,end-start),208,5,primary,source)
    for item in placements:
        item_kind,col,y,value,size,*rest=item;x=col_x[col]
        if item_kind=="heading":
            category_size=style_size(source,"category_title",14)
            heading_font=font(source,"category_title",category_size,True)
            heading_w=min(column_width-24,QFontMetricsF(heading_font).horizontalAdvance(value)+24)
            heading_h=max(size*1.3,category_size*1.2)
            heading_y=y
            p.save();p.setPen(Qt.PenStyle.NoPen);p.setBrush(QColor(primary));p.drawRoundedRect(QRectF(x-5,heading_y,heading_w+10,heading_h),7,7);p.restore()
            heading_text="#FFFFFF" if QColor(primary).lightness()<155 else dark
            text(p,source,"category_title",category_size,heading_text,x+10,heading_y+1,heading_w-20,heading_h-2,value,True,Qt.AlignmentFlag.AlignVCenter);continue
        dish=value;row_h=rest[0];promo=bool(dish.get("promo_enabled") and dish.get("promo_price") is not None)
        price_width=column_width-name_width-16;price_x=x+name_width+8
        label_width=name_width-(62 if promo else 0)
        lines=wrapped_lines(dish["name"],source,"dish_name",size,label_width)
        metrics=QFontMetricsF(font(source,"dish_name",size));line_h=metrics.height()*1.05
        for li,line in enumerate(lines):
            yy=y+li*line_h
            text_singleline(p,source,"dish_name",size,dark,x,yy,label_width,line_h,line)
        if promo:
            badge_x=x+name_width-57;badge_y=y+(len(lines)-1)*line_h
            badge=QRectF(badge_x,badge_y+line_h*.12,56,line_h*.72)
            p.save();p.setPen(Qt.PenStyle.NoPen);p.setBrush(QColor("#a9433b"));p.drawRoundedRect(badge,6,6);p.restore()
            text_singleline(p,source,"promo_badge",style_size(source,"promo_badge",6),"#ffffff",badge_x+2,badge_y+line_h*.12,52,line_h*.72,"AKCIÓ",True,Qt.AlignmentFlag.AlignHCenter)
        price_y=y+(len(lines)-1)*line_h
        if mode!="none":
            pen=QPen(QColor(accent));pen.setWidthF(.8)
            if mode=="dots":pen.setStyle(Qt.PenStyle.DotLine)
            elif mode=="dashes":pen.setStyle(Qt.PenStyle.DashLine)
            p.setPen(pen);p.drawLine(round(price_x-8),round(price_y+line_h*.55),round(price_x),round(price_y+line_h*.55))
        if promo:
            old=price(dish["price"]);new=price(dish["promo_price"])
            old_size=min(size,style_size(source,"promo_old_price",7));new_size=min(size,style_size(source,"promo_new_price",12.5))
            old_metrics=QFontMetricsF(font(source,"promo_old_price",old_size));new_metrics=QFontMetricsF(font(source,"promo_new_price",new_size,True))
            old_w=old_metrics.horizontalAdvance(old);new_w=new_metrics.horizontalAdvance(new);gap_px=7
            total=old_w+gap_px+new_w
            if total>price_width:
                scale=price_width/total;old_size*=scale;new_size*=scale
                old_metrics=QFontMetricsF(font(source,"promo_old_price",old_size));new_metrics=QFontMetricsF(font(source,"promo_new_price",new_size,True))
                old_w=old_metrics.horizontalAdvance(old);new_w=new_metrics.horizontalAdvance(new);gap_px=4
            old_x=price_x+price_width-old_w-new_w-gap_px
            text_singleline(p,source,"promo_old_price",old_size,"#777777",old_x,price_y,old_w,line_h,old,False)
            p.save();p.setPen(QPen(QColor("#777777"),max(.7,size*.035)));p.drawLine(round(old_x),round(price_y+line_h*.53),round(old_x+old_w),round(price_y+line_h*.53));p.restore()
            text_singleline(p,source,"promo_new_price",new_size,"#9E3F3A",old_x+old_w+gap_px,price_y,new_w,line_h,new,True,Qt.AlignmentFlag.AlignRight)
        else:
            price_size=min(size,style_size(source,"dish_price",12.5))
            price_text=price(dish["price"])
            price_width_px=QFontMetricsF(font(source,"dish_price",price_size)).horizontalAdvance(price_text)
            if price_width_px>price_width:price_size=max(6,int(price_size*price_width/price_width_px))
            text_singleline(p,source,"dish_price",price_size,dark,price_x,price_y,price_width,line_h,price_text,False,Qt.AlignmentFlag.AlignRight)
    content_end=max((item[2]+(item[4]*1.3 if item[0]=="heading" else item[5])
                     for item in placements),default=top)
    p.restore()
    return content_end+alacarte_shift


def draw_weekly(p,source,target,primary,accent,dark,decorated,glass_enabled,assets,days_shift=0):
    mon=monday(target)
    p.save();p.translate(0,days_shift)
    entries=[source.week_entry(mon+timedelta(days=i)) for i in range(5)]
    for i,(label,entry) in enumerate(zip(WEEKDAYS,entries)):
        y=330+i*310
        if glass_enabled:glass(p,QRectF(40,y-8,W-80,278),205,6,primary,source)
        if decorated and i<4:divider(p,primary,accent,y+286,assets,mon+timedelta(days=i),20)
        closed,closure_note=source.week_entry_state(mon+timedelta(days=i)) if hasattr(source,"week_entry_state") else (False,"")
        if closed:
            text(p,source,"weekly_value",style_size(source,"weekly_value",15),dark,92,y+18,W-184,230,closure_note.strip() or "Zárva",False,Qt.AlignmentFlag.AlignHCenter|Qt.AlignmentFlag.AlignVCenter)
            continue
        weekday_size=style_size(source,"weekday_title",16)
        heading_width=QFontMetricsF(font(source,"weekday_title",weekday_size,True)).horizontalAdvance(label)+28
        p.save();p.setPen(Qt.PenStyle.NoPen);p.setBrush(QColor(primary));p.drawRoundedRect(QRectF(72,y+10,heading_width,52),5,5);p.restore()
        heading_text="#FFFFFF" if QColor(primary).lightness()<155 else dark
        text(p,source,"weekday_title",weekday_size,heading_text,86,y+11,heading_width-28,48,label,True,Qt.AlignmentFlag.AlignVCenter)
        values=[("Leves",entry[0]),("A menü",entry[1]),("B menü",entry[2])]
        label_size=style_size(source,"weekly_label",15)
        value_size=style_size(source,"weekly_value",15)
        yy=y+78
        for field,value in values:
            height=max(56,measure(value or "—",source,"weekly_value",value_size,1040)+8,
                       measure(field,source,"weekly_label",label_size,190,True)+4)
            text(p,source,"weekly_label",label_size,primary,92,yy,190,height,field,True)
            text(p,source,"weekly_value",value_size,dark,292,yy,1040,height,value or "—")
            yy+=height+3
    p.restore()


def render_image(source,kind,target,width=EXPORT_WIDTH,height=EXPORT_HEIGHT):
    image=QImage(width,height,QImage.Format.Format_RGB32);image.fill(Qt.GlobalColor.white)
    image.setDotsPerMeterX(round(EXPORT_DPI/0.0254));image.setDotsPerMeterY(round(EXPORT_DPI/0.0254))
    p=QPainter(image);p.scale(width/W,height/H);draw_menu(p,source,kind,target);p.end();return image


def export_png(path,source,kind,target):
    if not render_image(source,kind,target).save(str(path),"PNG"):raise OSError("A PNG nem menthető.")


def export_pdf(path,source,kind,target):
    from PyQt6.QtGui import QPageLayout
    writer=QPdfWriter(str(path))
    writer.setPageLayout(QPageLayout(QPageSize(QPageSize.PageSizeId.A4),QPageLayout.Orientation.Portrait,
                                    QMarginsF(0,0,0,0),QPageLayout.Unit.Millimeter))
    writer.setResolution(EXPORT_DPI);writer.setTitle(("Napi étlap" if kind=="daily" else "Heti menü" if kind=="weekly" else "Különleges alkalom")+" – "+display_date(target))
    p=QPainter(writer);area=writer.pageLayout().paintRectPixels(writer.resolution())
    p.translate(area.x(),area.y());p.scale(area.width()/W,area.height()/H);draw_menu(p,source,kind,target);p.end()

