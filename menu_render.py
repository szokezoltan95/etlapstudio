"""Clean seasonal menu artwork and full-bleed PDF/PNG rendering."""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from PyQt6.QtCore import QMarginsF, QRectF, Qt
from PyQt6.QtGui import (QColor, QFont, QFontMetricsF, QImage, QPainter,
                         QPageSize, QPdfWriter, QPainterPath, QPen)
from themes import HEX, load_themes
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


def _easter_sunday(year):
    a=year%19;b=year//100;c=year%100;d=b//4;e=b%4;f=(b+8)//25;g=(b-f+1)//3
    h=(19*a+b-d-g+15)%30;i=c//4;k=c%4;l=(32+2*e+2*i-h-k)%7;m=(a+11*h+22*l)//451
    month=(h+l-7*m+114)//31;day=(h+l-7*m+114)%31+1
    return date(year,month,day)


def seasonal_colors(target):
    """Muted holiday palette selected from the menu date."""
    easter=_easter_sunday(target.year)
    if easter-timedelta(days=4)<=target<=easter+timedelta(days=1):
        return ("#4F5D3E","#A93632","#F7EEDC")
    if target.month==2 and 13<=target.day<=15:
        return ("#682A36","#B7444D","#F8EADF")
    if target.month==8 and 18<=target.day<=21:
        return ("#3F5942","#B33930","#F5EBD5")
    if target.month==10 and target.day>=20:
        return ("#63352A","#AD382D","#F5EAD4")
    if (target.month==12 and target.day>=1) or (target.month==1 and target.day<=2):
        return ("#3A5748","#A8342D","#F5EBDD")
    if target.month in (6,7,8):return ("#526044","#B33930","#F8EED9")
    if target.month in (9,10,11):return ("#63352A","#A9362E","#F5EAD4")
    return ("#4D5C45","#A93632","#F7EEDC")


def colors(source,target):
    key=setting(source,"theme","auto")
    if key=="auto" or setting(source,"auto_theme","1")=="1":return seasonal_colors(target)
    packs=load_themes(BASE/"themes_builtin",data_dir()/"themes")
    if key in packs:
        palette=packs[key][0]["palette"]
        return palette["primary"],palette["accent"],palette["background"]
    p=setting(source,"theme_primary");a=setting(source,"theme_accent")
    default=seasonal_colors(target)
    return (p if HEX.fullmatch(p) else default[0],a if HEX.fullmatch(a) else default[1],default[2])


def theme_assets(source,target):
    if setting(source,"auto_theme","1")=="1":
        return {"header":BASE/"design_assets"/"brushstroke.png",
                "divider":BASE/"design_assets"/"brushstroke.png"}
    key=setting(source,"theme")
    packs=load_themes(BASE/"themes_builtin",data_dir()/"themes")
    if key not in packs:return {}
    manifest,folder=packs[key]
    return {name:folder/filename for name,filename in manifest.get("assets",{}).items()
            if filename.endswith(".png") and (folder/filename).is_file()}


def draw_theme_asset(p,assets,key,rect,opacity=0.75):
    path=assets.get(key)
    if not path:return False
    image=QImage(str(path))
    if image.isNull():return False
    p.save();p.setOpacity(opacity);p.drawImage(rect,image);p.restore();return True


_brush_tints={}
def tinted_brush(color):
    if color not in _brush_tints:
        original=QImage(str(BASE/"design_assets"/"brushstroke.png")).convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
        if original.isNull():return None
        p=QPainter(original);p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        p.fillRect(original.rect(),QColor(color));p.end();_brush_tints[color]=original
    return _brush_tints[color]


def guide(source,kind,name,default):
    try:return max(80,min(H-70,int(setting(source,f"guide_{kind}_{name}",str(default)))))
    except (ValueError,TypeError):return default


def season_key(target):
    easter=_easter_sunday(target.year)
    if easter-timedelta(days=4)<=target<=easter+timedelta(days=1):return "spring"
    if target.month==12 or (target.month==1 and target.day<=2):return "winter"
    if target.month in (6,7,8):return "summer"
    if target.month in (9,10,11):return "autumn"
    return "spring"


def seasonal_art(target,kind):
    path=BASE/"design_assets"/f"{season_key(target)}_{kind}.jpg"
    if path.is_file():
        image=QImage(str(path))
        if not image.isNull():return image


def glass(p,rect,opacity=216,radius=20):
    p.save();p.setPen(Qt.PenStyle.NoPen);p.setBrush(QColor(255,255,255,opacity));p.drawRoundedRect(rect,radius,radius);p.restore()


def brushstroke(p,x,y,w,color,width=20):
    image=tinted_brush(color)
    if image is not None:
        p.save();p.setOpacity(.76);p.drawImage(QRectF(x,y-width*.55,w,width),image);p.restore();return
    p.save();c=QColor(color);c.setAlpha(60)
    path=QPainterPath();path.moveTo(x,y)
    path.cubicTo(x+w*.2,y-width*.35,x+w*.44,y+width*.3,x+w*.63,y-width*.08)
    path.cubicTo(x+w*.78,y-width*.28,x+w*.9,y+width*.25,x+w,y)
    pen=QPen(c,width);pen.setCapStyle(Qt.PenCapStyle.RoundCap);pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen);p.setBrush(Qt.BrushStyle.NoBrush);p.drawPath(path);p.restore()


def divider(p,primary,accent,y,assets=None):
    path=assets.get("divider") if assets else None
    if path and Path(path).name!="brushstroke.png" and draw_theme_asset(p,assets,"divider",QRectF(120,y-18,W-240,38),.32):return
    brushstroke(p,132,y,1170,accent,30)


def draw_header(p,source,kind,target,primary,accent,dark,paper,decorated,glass_enabled,assets):
    if glass_enabled:glass(p,QRectF(130,68,1180,365),225,22)
    if decorated:
        path=assets.get("header") if assets else None
        if path and Path(path).name!="brushstroke.png":
            draw_theme_asset(p,assets,"header",QRectF(120,218,1200,200),.74)
        else:
            brushstroke(p,230,339,980,accent,250)
    else:
        p.setPen(QPen(QColor(accent),1.2));p.drawLine(180,270,1260,270)
    logo=BASE/"design_assets"/"megyehaza_logo.png"
    if logo.is_file():
        image=QImage(str(logo))
        if not image.isNull():p.drawImage(QRectF(140,78,130,130),image)
    text(p,source,"restaurant",37,dark,275,105,W-550,68,
         setting(source,"restaurant","Megyeháza Étterem") or "Megyeháza Étterem",True,Qt.AlignmentFlag.AlignHCenter)
    address=setting(source,"address");phone=setting(source,"phone")
    text(p,source,"special",21,dark,120,176,W-240,34,
         address+("  •  " if address and phone else "")+phone,align=Qt.AlignmentFlag.AlignHCenter)
    title="Napi étlap" if kind=="daily" else "Heti menü"
    text(p,source,"title",60,paper if decorated else dark,120,296,W-240,86,title,True,Qt.AlignmentFlag.AlignHCenter)
    stamp=display_date(target) if kind=="daily" else display_date(monday(target))+" – "+display_date(monday(target)+timedelta(days=4))
    text(p,source,"special",27,dark,120,390,W-240,43,stamp,align=Qt.AlignmentFlag.AlignHCenter)


def draw_menu(p,source,kind,target):
    p.save();p.setRenderHint(QPainter.RenderHint.Antialiasing);p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    primary,accent,paper=colors(source,target);dark="#2D342E"
    p.fillRect(QRectF(0,0,W,H),QColor(paper))
    background=seasonal_art(target,"background")
    if setting(source,"background_enabled","1")=="1" and background is not None:
        p.save();p.setOpacity(.48);p.drawImage(QRectF(0,0,W,H),background);p.restore()
        p.fillRect(QRectF(0,0,W,H),QColor(QColor(paper).red(),QColor(paper).green(),QColor(paper).blue(),143))
    glass_enabled=setting(source,"glass_panels","1")=="1"
    decorated=setting(source,"decorations","1")=="1"
    assets=theme_assets(source,target)
    header_y=guide(source,kind,"header",430)
    p.save();p.translate(0,header_y-430)
    draw_header(p,source,kind,target,primary,accent,dark,paper,decorated,glass_enabled,assets)
    p.restore()
    if kind=="daily":
        menu_end=guide(source,kind,"menu_end",710)
        draw_daily(p,source,target,primary,accent,dark,decorated,glass_enabled,assets,
                   header_y-430,menu_end-710)
    else:
        days_y=guide(source,kind,"days",520)
        draw_weekly(p,source,target,primary,accent,dark,decorated,glass_enabled,assets,days_y-520)
    note=setting(source,"note").strip()
    if note:text(p,source,"special",17,dark,120,1733,W-240,40,note[:130],align=Qt.AlignmentFlag.AlignHCenter)
    p.restore()


def draw_daily(p,source,target,primary,accent,dark,decorated,glass_enabled,assets,header_shift=0,menu_gap_shift=0):
    soup,a,b=source.week_entry(target)
    menu_shift=header_shift
    menu_y=475+menu_shift
    if glass_enabled:glass(p,QRectF(120,menu_y,W-240,235),224,22)
    elif decorated:brushstroke(p,150,530+menu_shift,1090,primary,24)
    text(p,source,"heading",27,primary,152,497+menu_shift,W-300,45,"Mai menü",True)
    fields=[("Leves",soup or "—"),("A menü",a or "—"),("B menü",b or "—")]
    special_size=24
    for candidate in range(24,7,-1):
        total=sum(max(35,measure(value,source,"special",candidate,835)+5) for _,value in fields)
        if total<=156:special_size=candidate;break
    y=548+menu_shift
    for label,value in fields:
        height=max(35,measure(value,source,"special",special_size,835)+5)
        text(p,source,"heading",special_size,primary,152,y,180,height,label,True)
        text(p,source,"special",special_size,dark,360,y,870,height,value);y+=height
    alacarte_shift=header_shift+menu_gap_shift
    if decorated:divider(p,primary,accent,775+alacarte_shift,assets)
    dishes=[dict(d) for d in source.selection(target)]
    if not dishes:
        text(p,source,"dish",27,dark,170,844+alacarte_shift,W-340,100,"Még nincs à la carte étel kiválasztva.",align=Qt.AlignmentFlag.AlignHCenter)
        return
    p.save();p.translate(0,alacarte_shift)
    max_y=1690+alacarte_shift;top=813+alacarte_shift
    def plan(size,columns):
        column_width=1140/columns;col_x=[120+column*(column_width+20) for column in range(columns)]
        name_width=column_width-155
        result=[];col=0;y=top
        for category in CATEGORIES:
            rows=[d for d in dishes if d["category"]==category]
            for index,d in enumerate(rows):
                name_h=measure(d["name"],source,"dish",size,name_width)
                promo=bool(d.get("promo_enabled") and d.get("promo_price") is not None)
                row_h=max(name_h+size*.24,size*(2.25 if promo else 1.35))
                heading_h=size*1.9 if index==0 else 0
                if y+heading_h+row_h>max_y:
                    col+=1;y=top
                    if col>=columns:return None
                    heading_h=size*1.9
                if y+heading_h+row_h>max_y:return None
                if heading_h:result.append(("heading",col,y,category,size));y+=heading_h
                result.append(("dish",col,y,d,size,row_h));y+=row_h
        return result
    chosen_columns=2;lo,hi=8.0,30.0
    if plan(8.0,2) is None:
        chosen_columns=3;lo,hi=5.0,30.0
    for _ in range(24):
        mid=(lo+hi)/2
        if plan(mid,chosen_columns) is None:hi=mid
        else:lo=mid
    placements=plan(lo,chosen_columns) or plan(5.0,chosen_columns)
    if placements is None:raise ValueError("Túl sok étel az egyképes napi étlaphoz.")
    mode=setting(source,"leader","none")
    column_width=1140/chosen_columns
    col_x=[120+column*(column_width+20) for column in range(chosen_columns)]
    name_width=column_width-155
    for item in placements:
        item_kind,col,y,value,size,*rest=item;x=col_x[col]
        if item_kind=="heading":
            if decorated:brushstroke(p,x,y+size*.86,column_width-20,accent,size*1.35)
            text(p,source,"heading",size*1.14,primary,x,y,column_width,size*1.8,value,True);continue
        dish=value;row_h=rest[0];promo=bool(dish.get("promo_enabled") and dish.get("promo_price") is not None)
        text(p,source,"dish",size,dark,x,y,name_width,row_h,dish["name"])
        price_x=x+name_width+5;price_width=column_width-name_width-5
        if mode!="none":
            pen=QPen(QColor(accent));pen.setWidthF(.8)
            if mode=="dots":pen.setStyle(Qt.PenStyle.DotLine)
            elif mode=="dashes":pen.setStyle(Qt.PenStyle.DashLine)
            p.setPen(pen);p.drawLine(round(price_x-8),round(y+size*.83),round(price_x),round(y+size*.83))
        if promo:
            old=price(dish["price"]);new=price(dish["promo_price"])
            text(p,source,"dish",size*.67,"#687269",price_x,y,price_width,size*1.08,old,align=Qt.AlignmentFlag.AlignRight)
            fm=QFontMetricsF(font(source,"dish",size*.79));old_w=fm.horizontalAdvance(old)
            p.setPen(QPen(QColor("#687269"),1.2));p.drawLine(round(x+column_width-old_w),round(y+size*.59),round(x+column_width),round(y+size*.59))
            text(p,source,"dish",size*.62,"#9E3F3A",price_x,y+size*.95,price_width,size*1.3,"AKCIÓ · "+new,True,Qt.AlignmentFlag.AlignRight)
        else:text(p,source,"dish",size*.82,dark,price_x,y,price_width,row_h,price(dish["price"]),align=Qt.AlignmentFlag.AlignRight)
    p.restore()


def draw_weekly(p,source,target,primary,accent,dark,decorated,glass_enabled,assets,days_shift=0):
    mon=monday(target)
    p.save();p.translate(0,days_shift)
    entries=[source.week_entry(mon+timedelta(days=i)) for i in range(5)]
    for i,(label,entry) in enumerate(zip(WEEKDAYS,entries)):
        y=548+i*222
        if glass_enabled:glass(p,QRectF(132,y-10,W-264,196),195,16)
        if decorated:brushstroke(p,150,y+29,225,accent,19)
        if i<4:divider(p,primary,accent,y+201,assets)
        text(p,source,"heading",31,primary,155,y,235,52,label,True)
        values=[("Leves",entry[0]),("A menü",entry[1]),("B menü",entry[2])]
        size=25
        for candidate in range(25,7,-1):
            total=sum(max(39,measure(value or "—",source,"special",candidate,880)+4) for _,value in values)
            if total<=176:size=candidate;break
        yy=y+2
        for field,value in values:
            text(p,source,"heading",size*.83,primary,190,yy,155,39,field,True)
            text(p,source,"special",size,dark,390,yy,890,39,value or "—");yy+=39
    p.restore()


def render_image(source,kind,target,width=W,height=H):
    image=QImage(width,height,QImage.Format.Format_RGB32);image.fill(Qt.GlobalColor.white)
    p=QPainter(image);p.scale(width/W,height/H);draw_menu(p,source,kind,target);p.end();return image


def export_png(path,source,kind,target):
    if not render_image(source,kind,target).save(str(path),"PNG"):raise OSError("A PNG nem menthető.")


def export_pdf(path,source,kind,target):
    from PyQt6.QtGui import QPageLayout
    writer=QPdfWriter(str(path))
    writer.setPageLayout(QPageLayout(QPageSize(QPageSize.PageSizeId.A4),QPageLayout.Orientation.Portrait,
                                    QMarginsF(0,0,0,0),QPageLayout.Unit.Millimeter))
    writer.setResolution(300);writer.setTitle(("Napi étlap" if kind=="daily" else "Heti menü")+" – "+display_date(target))
    p=QPainter(writer);area=writer.pageLayout().paintRectPixels(writer.resolution())
    p.translate(area.x(),area.y());p.scale(area.width()/W,area.height()/H);draw_menu(p,source,kind,target);p.end()
