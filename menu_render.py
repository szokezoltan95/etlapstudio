"""One Qt painting path for the live preview, Facebook PNG and print PDF."""
from __future__ import annotations

import io
from datetime import timedelta
from pathlib import Path
from PyQt6.QtCore import QMarginsF, QRectF, Qt
from PyQt6.QtGui import (QColor, QFont, QFontMetricsF, QImage, QPainter, QPageSize,
                         QPdfWriter, QPen)
from themes import load_themes, HEX
from menu_core import CATEGORIES, WEEKDAYS, data_dir, display_date, monday, price

W,H=1440,1800
BASE=Path(__file__).resolve().parent


def setting(source,key,default=""):
    return source.setting(key,default)


def font(source,role,size,bold=False):
    defaults={"restaurant":"Georgia","title":"Georgia","heading":"Georgia",
              "special":"Segoe UI","dish":"Segoe UI"}
    family=setting(source,"font_"+role,defaults.get(role,"Segoe UI"))
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


def leader(p,mode,x1,x2,y,color,size):
    if mode=="none" or x2<=x1+4:return
    pen=QPen(QColor(color));pen.setWidthF(.8)
    if mode=="dots":pen.setStyle(Qt.PenStyle.DotLine)
    elif mode=="dashes":pen.setStyle(Qt.PenStyle.DashLine)
    else:pen.setStyle(Qt.PenStyle.SolidLine)
    p.setPen(pen);p.drawLine(round(x1),round(y),round(x2),round(y))


def artwork(p,folder,manifest,palette,primary,accent,key,rect):
    name=manifest["assets"][key];path=folder/name
    if name.endswith(".png"):
        image=QImage(str(path))
        if not image.isNull():p.drawImage(rect,image)


def seasonal_asset(source,role):
    season=setting(source,"seasonal_background","autumn")
    if season not in ("spring","summer","autumn","winter"):return None
    path=BASE/"design_assets"/f"{season}_{role}.jpg"
    return path if path.is_file() else None


def draw_raster(p,path,rect,opacity=1.0):
    if not path:return
    image=QImage(str(path))
    if image.isNull():return
    p.save();p.setOpacity(max(0.0,min(1.0,opacity)));p.drawImage(rect,image);p.restore()


def draw_menu(p,source,kind,target):
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    p.fillRect(QRectF(0,0,W,H),QColor("white"))
    packs=load_themes(BASE/"themes_builtin",data_dir()/"themes")
    manifest,folder=packs.get(setting(source,"theme","classic"),packs["classic"])
    palette=manifest["palette"]
    primary=setting(source,"theme_primary")
    accent=setting(source,"theme_accent")
    primary=primary if HEX.fullmatch(primary) else palette["primary"]
    accent=accent if HEX.fullmatch(accent) else palette["accent"]
    dark="#263A30";decorated=setting(source,"decorations","1")=="1"
    bgname=setting(source,"background_file")
    bgpath=data_dir()/"backgrounds"/bgname if bgname and Path(bgname).name==bgname else None
    season=setting(source,"seasonal_background","autumn")
    if not bgpath or not bgpath.is_file():
        bgpath=seasonal_asset(source,"background")
    if not bgpath or not bgpath.is_file():
        bgpath=BASE/"backgrounds"/"botanical.png" if setting(source,"background_builtin") == "1" else None
    if bgpath and bgpath.is_file() and setting(source,"background_enabled") == "1":
        image=QImage(str(bgpath))
        if not image.isNull():
            p.save();p.setOpacity(max(0,min(100,int(setting(source,"background_opacity","78"))))/100)
            p.drawImage(QRectF(0,0,W,H),image);p.restore()
    p.setPen(QPen(QColor(primary),2));p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawRect(QRectF(46,46,W-92,H-92))
    if decorated:
        # The generated background already carries a full botanical frame;
        # keep this banner translucent so it does not repeat the illustration.
        p.setPen(QPen(QColor(primary),1.5));p.setBrush(QColor(palette["background"]))
        p.drawRoundedRect(QRectF(155,78,W-310,174),22,22)
        artwork(p,folder,manifest,palette,primary,accent,"header",QRectF(120,62,W-240,200))
    else:
        p.drawLine(120,260,W-120,260)
    text(p,source,"restaurant",37,dark,120,106,W-240,68,
         setting(source,"restaurant","Étterem") or "Étterem",True,Qt.AlignmentFlag.AlignHCenter)
    address=setting(source,"address");phone=setting(source,"phone")
    text(p,source,"special",21,dark,120,177,W-240,35,
         address+("  •  " if address and phone else "")+phone,align=Qt.AlignmentFlag.AlignHCenter)
    title="Napi étlap" if kind=="daily" else "Heti menü"
    if decorated:
        p.setPen(QPen(QColor(accent),1.4));p.setBrush(QColor(palette["background"]))
        p.drawRoundedRect(QRectF(235,292,W-470,124),22,22)
    text(p,source,"title",60,dark,120,307,W-240,92,title,True,Qt.AlignmentFlag.AlignHCenter)
    stamp=display_date(target) if kind=="daily" else display_date(monday(target))+" – "+display_date(monday(target)+timedelta(days=4))
    text(p,source,"special",27,dark,120,399,W-240,47,stamp,align=Qt.AlignmentFlag.AlignHCenter)
    if kind=="daily":draw_daily(p,source,target,folder,manifest,palette,primary,accent,dark,decorated)
    else:draw_weekly(p,source,target,folder,manifest,palette,primary,accent,dark,decorated)
    p.setPen(QPen(QColor(accent),1));p.drawLine(120,1723,W-120,1723)
    text(p,source,"special",17,dark,120,1733,W-240,38,setting(source,"note")[:130])
    p.restore()


def draw_daily(p,source,target,folder,manifest,palette,primary,accent,dark,decorated):
    soup,a,b=source.week_entry(target)
    p.setPen(QPen(QColor(primary),2));p.setBrush(QColor(palette["background"]))
    p.drawRoundedRect(QRectF(120,475,W-240,235),21,21)
    text(p,source,"heading",27,primary,152,497,W-300,45,"MAI MENÜ",True)
    fields=[("Leves",soup or "—"),("A menü",a or "—"),("B menü",b or "—")]
    special_size=24
    for candidate in range(24,7,-1):
        total=sum(max(35,measure(value,source,"special",candidate,835)+5) for _,value in fields)
        if total<=156:special_size=candidate;break
    y=548
    for label,value in fields:
        height=max(35,measure(value,source,"special",special_size,835)+5)
        text(p,source,"heading",special_size,primary,152,y,180,height,label,True)
        text(p,source,"special",special_size,dark,360,y,870,height,value)
        y+=height
    if decorated:
        draw_raster(p,seasonal_asset(source,"divider"),QRectF(120,725,W-240,76),.95)
        artwork(p,folder,manifest,palette,primary,accent,"divider",QRectF(120,725,W-240,76))
    else:
        p.setPen(QPen(QColor(accent),2));p.drawLine(120,775,W-120,775)
    dishes=[dict(d) for d in source.selection(target)]
    if not dishes:
        text(p,source,"dish",25,dark,170,843,W-340,100,"Még nincs à la carte étel kiválasztva.",align=Qt.AlignmentFlag.AlignHCenter)
        return
    column_width=560;col_x=(125,755);max_y=1690;top=813
    def plan(size):
        result=[];col=0;y=top
        for category in CATEGORIES:
            rows=[d for d in dishes if d["category"]==category]
            for index,d in enumerate(rows):
                name_h=measure(d["name"],source,"dish",size,390)
                promo=bool(d.get("promo_enabled") and d.get("promo_price") is not None)
                row_h=max(name_h+size*.24,size*(2.25 if promo else 1.35))
                heading_h=size*1.9 if index==0 else 0
                if y+heading_h+row_h>max_y:
                    col+=1;y=top
                    if col>1:return None
                    heading_h=size*1.9
                if y+heading_h+row_h>max_y:return None
                if heading_h:
                    result.append(("heading",col,y,category,size));y+=heading_h
                result.append(("dish",col,y,d,size,row_h));y+=row_h
        return result
    lo,hi=2.0,24.0
    for _ in range(20):
        mid=(lo+hi)/2
        if plan(mid) is None:hi=mid
        else:lo=mid
    placements=plan(lo) or plan(2.0)
    if placements is None:raise ValueError("Túl sok étel az egyképes napi étlaphoz.")
    mode=setting(source,"leader","none")
    for item in placements:
        kind,col,y,value,size,*rest=item;x=col_x[col]
        if kind=="heading":
            if decorated:
                p.setPen(Qt.PenStyle.NoPen);p.setBrush(QColor(palette["background"]))
                p.drawRoundedRect(QRectF(x-8,y-3,column_width-20,size*1.8),8,8)
                draw_raster(p,seasonal_asset(source,"category"),QRectF(x-8,y-3,column_width-20,size*1.8),.20)
            text(p,source,"heading",size*1.23,primary,x,y,column_width,size*1.8,value,True)
            continue
        d=value;row_h=rest[0];promo=bool(d.get("promo_enabled") and d.get("promo_price") is not None)
        text(p,source,"dish",size,dark,x,y,390,row_h,d["name"])
        leader(p,mode,x+393,x+410,y+size*.83,accent,size)
        if promo:
            old=price(d["price"]);new=price(d["promo_price"])
            text(p,source,"dish",size*.79,"#687269",x+410,y,150,size*1.08,old,
                 align=Qt.AlignmentFlag.AlignRight)
            fm=QFontMetricsF(font(source,"dish",size*.79))
            old_w=fm.horizontalAdvance(old)
            p.setPen(QPen(QColor("#687269"),1.2));p.drawLine(round(x+560-old_w),round(y+size*.59),x+560,round(y+size*.59))
            text(p,source,"dish",size*.92,"#AC2929",x+410,y+size*.95,150,size*1.3,
                 "AKCIÓ  "+new,True,Qt.AlignmentFlag.AlignRight)
        else:
            text(p,source,"dish",size,dark,x+410,y,150,row_h,price(d["price"]),
                 align=Qt.AlignmentFlag.AlignRight)


def draw_weekly(p,source,target,folder,manifest,palette,primary,accent,dark,decorated):
    mon=monday(target)
    if decorated:
        draw_raster(p,seasonal_asset(source,"divider"),QRectF(120,462,W-240,76),.95)
        artwork(p,folder,manifest,palette,primary,accent,"divider",QRectF(120,462,W-240,76))
    entries=[source.week_entry(mon+timedelta(days=i)) for i in range(5)]
    for i,(label,entry) in enumerate(zip(WEEKDAYS,entries)):
        y=548+i*222
        p.setPen(QPen(QColor(accent),1));p.drawLine(140,y+201,W-140,y+201)
        if decorated:
            p.setPen(Qt.PenStyle.NoPen);p.setBrush(QColor(palette["background"]))
            p.drawRoundedRect(QRectF(138,y-4,248,61),8,8)
            draw_raster(p,seasonal_asset(source,"category"),QRectF(138,y-4,248,61),.20)
        text(p,source,"heading",31,primary,145,y,235,52,label,True)
        values=[("Leves",entry[0]),("A menü",entry[1]),("B menü",entry[2])]
        size=25
        for candidate in range(25,7,-1):
            total=sum(max(39,measure(value or "—",source,"special",candidate,880)+4) for _,value in values)
            if total<=176:size=candidate;break
        yy=y+2
        for field,value in values:
            height=max(39,measure(value or "—",source,"special",size,880)+4)
            text(p,source,"heading",size*.83,primary,190,yy,155,height,field,True)
            text(p,source,"special",size,dark,390,yy,890,height,value or "—")
            yy+=height
    if decorated:artwork(p,folder,manifest,palette,primary,accent,"corner",QRectF(60,1590,120,120))


def render_image(source,kind,target,width=W,height=H):
    image=QImage(width,height,QImage.Format.Format_RGB32);image.fill(Qt.GlobalColor.white)
    p=QPainter(image);p.scale(width/W,height/H);draw_menu(p,source,kind,target);p.end()
    return image


def export_png(path,source,kind,target):
    if not render_image(source,kind,target).save(str(path),"PNG"):
        raise OSError("A PNG nem menthető.")


def export_pdf(path,source,kind,target):
    from PyQt6.QtGui import QPageLayout
    writer=QPdfWriter(str(path))
    writer.setPageLayout(QPageLayout(QPageSize(QPageSize.PageSizeId.A4),
                                    QPageLayout.Orientation.Portrait,QMarginsF(0,0,0,0),
                                    QPageLayout.Unit.Millimeter))
    writer.setResolution(300);writer.setTitle(("Napi étlap" if kind=="daily" else "Heti menü")+" – "+display_date(target))
    p=QPainter(writer)
    area=writer.pageLayout().paintRectPixels(writer.resolution())
    p.translate(area.x(),area.y())
    p.scale(area.width()/W,area.height()/H)
    draw_menu(p,source,kind,target);p.end()
