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
    key=setting(source,"theme")
    season=theme_season(key,target)
    if key=="auto" or setting(source,"auto_theme","1")=="1":
        return {"header":BASE/"design_assets"/"brushstroke.png",
                "divider":BASE/"design_assets"/f"{season}_divider.jpg",
                "background":theme_background_path("auto",target)}
    packs=load_themes(BASE/"themes_builtin",data_dir()/"themes")
    if key not in packs:
        return {"header":BASE/"design_assets"/"brushstroke.png",
                "divider":BASE/"design_assets"/f"{season}_divider.jpg",
                "background":theme_background_path(key,target)}
    manifest,folder=packs[key]
    assets={name:folder/filename for name,filename in manifest.get("assets",{}).items()
            if filename.lower().endswith((".png",".jpg",".jpeg")) and (folder/filename).is_file()}
    assets.setdefault("header",BASE/"design_assets"/"brushstroke.png")
    assets.setdefault("divider",BASE/"design_assets"/f"{season}_divider.jpg")
    assets.setdefault("background",theme_background_path(key,target))
    return assets


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


def theme_season(key,target):
    key=(key or "").casefold()
    for tokens,season in ((('christmas','winter'),'winter'),(('autumn','fall'),'autumn'),
                          (('summer',),'summer'),(('spring','easter'),'spring')):
        if any(token in key for token in tokens):return season
    return season_key(target)


def theme_background_path(key,target):
    """Holiday art stays distinct from its generic seasonal counterpart."""
    name=(key or "auto").casefold()
    if name=="auto":
        easter=_easter_sunday(target.year)
        if easter-timedelta(days=4)<=target<=easter+timedelta(days=1):name="easter"
        elif target.month==12 or (target.month==1 and target.day<=2):name="christmas"
        else:name=season_key(target)
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
    p.save();c=QColor(accent);c.setAlpha(75);p.setPen(QPen(c,1.2));p.drawLine(48,y, W-48,y);p.restore()


def draw_header(p,source,kind,target,primary,accent,dark,paper,decorated,glass_enabled,assets):
    if glass_enabled:glass(p,QRectF(40,28,W-80,176),222,8)
    logo=BASE/"design_assets"/"megyehaza_wordmark.png"
    if logo.is_file():
        image=QImage(str(logo))
        if not image.isNull():
            box=QRectF(700,34,350,164)
            scale=min(box.width()/image.width(),box.height()/image.height())
            width=image.width()*scale;height=image.height()*scale
            p.drawImage(QRectF(box.x()+(box.width()-width)/2,box.y()+(box.height()-height)/2,width,height),image)
    address=setting(source,"address");phone=setting(source,"phone")
    text(p,source,"special",17,dark,1065,76,270,28,address,align=Qt.AlignmentFlag.AlignRight)
    text(p,source,"special",17,dark,1065,108,270,28,phone,align=Qt.AlignmentFlag.AlignRight)
    title="Napi étlap" if kind=="daily" else "Heti étlap"
    text(p,source,"title",47,dark,72,52,570,58,title,True)
    stamp=display_date(target) if kind=="daily" else display_date(monday(target))+" – "+display_date(monday(target)+timedelta(days=4))
    text(p,source,"special",25,dark,74,117,570,34,stamp)
    if kind=="weekly":
        try:menu_price=int(setting(source,"daily_menu_price","2800") or "0")
        except (TypeError,ValueError):menu_price=2800
        text(p,source,"special",19,primary,74,153,570,27,"Napi menü ára: "+price(menu_price),True)


def draw_menu(p,source,kind,target):
    p.save();p.setRenderHint(QPainter.RenderHint.Antialiasing);p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    primary,accent,paper=colors(source,target);dark="#2D342E"
    assets=theme_assets(source,target)
    p.fillRect(QRectF(0,0,W,H),QColor(paper))
    background_path=assets.get("background") if assets else None
    background=QImage(str(background_path)) if background_path else seasonal_art(target,"background")
    if background is not None and background.isNull():background=seasonal_art(target,"background")
    if background is not None:
        p.save();p.setOpacity(.48);p.drawImage(QRectF(0,0,W,H),background);p.restore()
        p.fillRect(QRectF(0,0,W,H),QColor(QColor(paper).red(),QColor(paper).green(),QColor(paper).blue(),143))
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
    else:
        days_y=guide(source,kind,"days",220)
        draw_weekly(p,source,target,primary,accent,dark,decorated,glass_enabled,assets,
                    days_y-220+header_y-header_default)
    note=setting(source,"note").strip()
    if note:
        if glass_enabled:glass(p,QRectF(40,1710,W-80,58),205,8)
        text(p,source,"special",17,dark,60,1720,W-120,38,note[:130],align=Qt.AlignmentFlag.AlignHCenter)
    p.restore()


def draw_daily(p,source,target,primary,accent,dark,decorated,glass_enabled,assets,header_shift=0,menu_gap_shift=0):
    soup,a,b=source.week_entry(target)
    menu_shift=header_shift
    menu_y=220+menu_shift
    if glass_enabled:glass(p,QRectF(40,menu_y,W-80,205),224,8)
    text(p,source,"heading",25,primary,72,menu_y+9,W-144,34,"Napi menü",True)
    fields=[("Leves",soup or "—"),("A menü",a or "—"),("B menü",b or "—")]
    special_size=31
    for candidate in range(31,17,-1):
        total=sum(max(34,measure(value,source,"special",candidate,790)+2) for _,value in fields)
        if total<=132:special_size=candidate;break
    y=menu_y+52
    for label,value in fields:
        height=max(34,measure(value,source,"special",special_size,790)+2)
        text(p,source,"heading",special_size*.82,primary,170,y,150,height,label,True)
        text(p,source,"special",special_size,dark,330,y,790,height,value)
        y+=height
    try:menu_price=int(setting(source,"daily_menu_price","2800") or "0")
    except (TypeError,ValueError):menu_price=2800
    text(p,source,"special",17,primary,1110,menu_y+59,230,28,"Napi menü ára",True,Qt.AlignmentFlag.AlignHCenter)
    text(p,source,"title",36,dark,1110,menu_y+90,230,54,price(menu_price),True,Qt.AlignmentFlag.AlignHCenter)
    alacarte_shift=header_shift+menu_gap_shift
    if decorated:divider(p,primary,accent,460+alacarte_shift,assets)
    dishes=[dict(d) for d in source.selection(target)]
    if not dishes:
        if glass_enabled:glass(p,QRectF(40,478+alacarte_shift,W-80,72),210,8)
        text(p,source,"dish",27,dark,60,494+alacarte_shift,W-120,45,"Még nincs à la carte étel kiválasztva.",align=Qt.AlignmentFlag.AlignHCenter)
        return
    p.save();p.translate(0,alacarte_shift)
    max_y=1690;top=478
    def plan(size,columns):
        gap=16;column_width=(1360-gap*(columns-1))/columns;col_x=[40+column*(column_width+gap) for column in range(columns)]
        name_width=column_width-188
        result=[];col=0;y=top
        for category in CATEGORIES:
            rows=[d for d in dishes if d["category"]==category]
            for index,d in enumerate(rows):
                lines=wrapped_lines(d["name"],source,"dish",size,name_width-(62 if d.get("promo_enabled") and d.get("promo_price") is not None else 0))
                line_h=QFontMetricsF(font(source,"dish",size)).height()*1.05
                promo=bool(d.get("promo_enabled") and d.get("promo_price") is not None)
                row_h=max(line_h*len(lines)+size*.18,size*1.25)
                heading_h=size*2.4 if index==0 else 0
                if y+heading_h+row_h>max_y:
                    col+=1;y=top
                    if col>=columns:return None
                    heading_h=size*2.4
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
    gap=16;column_width=(1360-gap*(chosen_columns-1))/chosen_columns
    col_x=[40+column*(column_width+gap) for column in range(chosen_columns)]
    name_width=column_width-188
    for item in placements:
        item_kind,col,y,value,size,*rest=item;x=col_x[col]
        if item_kind=="heading":
            heading_font=font(source,"heading",size*1.14,True)
            heading_w=min(column_width-24,QFontMetricsF(heading_font).horizontalAdvance(value)+24)
            heading_h=size*1.62
            heading_y=y+size*.34
            p.save();p.setPen(Qt.PenStyle.NoPen);p.setBrush(QColor(primary));p.drawRoundedRect(QRectF(x,heading_y,heading_w,heading_h),5,5);p.restore()
            heading_text="#FFFFFF" if QColor(primary).lightness()<155 else dark
            text(p,source,"heading",size*1.02,heading_text,x+10,heading_y+1,heading_w-20,heading_h-2,value,True,Qt.AlignmentFlag.AlignVCenter);continue
        dish=value;row_h=rest[0];promo=bool(dish.get("promo_enabled") and dish.get("promo_price") is not None)
        price_width=column_width-name_width-16;price_x=x+name_width+8
        label_width=name_width-(62 if promo else 0)
        lines=wrapped_lines(dish["name"],source,"dish",size,label_width)
        metrics=QFontMetricsF(font(source,"dish",size));line_h=metrics.height()*1.05
        if glass_enabled:glass(p,QRectF(x-3,y-2,column_width+6,max(row_h,size*1.4)),170,4)
        for li,line in enumerate(lines):
            yy=y+li*line_h
            text_singleline(p,source,"dish",size,dark,x,yy,label_width,line_h,line)
        if promo:
            badge_x=x+name_width-57;badge_y=y+(len(lines)-1)*line_h
            badge=QRectF(badge_x,badge_y+line_h*.12,56,line_h*.72)
            p.save();p.setPen(Qt.PenStyle.NoPen);p.setBrush(QColor("#a9433b"));p.drawRoundedRect(badge,6,6);p.restore()
            text_singleline(p,source,"dish",max(7,size*.43),"#ffffff",badge_x+2,badge_y+line_h*.12,52,line_h*.72,"AKCIÓ",True,Qt.AlignmentFlag.AlignHCenter)
        price_y=y+(len(lines)-1)*line_h
        if mode!="none":
            pen=QPen(QColor(accent));pen.setWidthF(.8)
            if mode=="dots":pen.setStyle(Qt.PenStyle.DotLine)
            elif mode=="dashes":pen.setStyle(Qt.PenStyle.DashLine)
            p.setPen(pen);p.drawLine(round(price_x-8),round(price_y+line_h*.55),round(price_x),round(price_y+line_h*.55))
        if promo:
            old=price(dish["price"]);new=price(dish["promo_price"])
            old_size=max(7,size*.57);new_size=max(7,size*.66)
            old_metrics=QFontMetricsF(font(source,"dish",old_size));new_metrics=QFontMetricsF(font(source,"dish",new_size,True))
            old_w=old_metrics.horizontalAdvance(old);new_w=new_metrics.horizontalAdvance(new);gap_px=7
            total=old_w+gap_px+new_w
            if total>price_width:
                scale=price_width/total;old_size*=scale;new_size*=scale
                old_metrics=QFontMetricsF(font(source,"dish",old_size));new_metrics=QFontMetricsF(font(source,"dish",new_size,True))
                old_w=old_metrics.horizontalAdvance(old);new_w=new_metrics.horizontalAdvance(new);gap_px=4
            old_x=price_x+price_width-old_w-new_w-gap_px
            text_singleline(p,source,"dish",old_size,"#777777",old_x,price_y,old_w,line_h,old,False)
            p.save();p.setPen(QPen(QColor("#777777"),max(.7,size*.035)));p.drawLine(round(old_x),round(price_y+line_h*.53),round(old_x+old_w),round(price_y+line_h*.53));p.restore()
            text_singleline(p,source,"dish",new_size,"#9E3F3A",old_x+old_w+gap_px,price_y,new_w,line_h,new,True,Qt.AlignmentFlag.AlignRight)
        else:
            text_singleline(p,source,"dish",min(size*.82,price_width*.105),dark,price_x,price_y,price_width,line_h,price(dish["price"]),False,Qt.AlignmentFlag.AlignRight)
    p.restore()


def draw_weekly(p,source,target,primary,accent,dark,decorated,glass_enabled,assets,days_shift=0):
    mon=monday(target)
    p.save();p.translate(0,days_shift)
    entries=[source.week_entry(mon+timedelta(days=i)) for i in range(5)]
    for i,(label,entry) in enumerate(zip(WEEKDAYS,entries)):
        y=220+i*282
        if glass_enabled:glass(p,QRectF(40,y-8,W-80,250),195,6)
        if i<4:divider(p,primary,accent,y+264,assets)
        heading_width=QFontMetricsF(font(source,"heading",38,True)).horizontalAdvance(label)+28
        p.save();p.setPen(Qt.PenStyle.NoPen);p.setBrush(QColor(primary));p.drawRoundedRect(QRectF(72,y+9,heading_width,48),5,5);p.restore()
        heading_text="#FFFFFF" if QColor(primary).lightness()<155 else dark
        text(p,source,"heading",32,heading_text,86,y+11,heading_width-28,43,label,True,Qt.AlignmentFlag.AlignVCenter)
        values=[("Leves",entry[0]),("A menü",entry[1]),("B menü",entry[2])]
        size=31
        for candidate in range(31,22,-1):
            total=sum(max(47,measure(value or "—",source,"special",candidate,1030)+4) for _,value in values)
            if total<=177:size=candidate;break
        yy=y+67
        for field,value in values:
            height=max(48,measure(value or "—",source,"special",size,1040)+4)
            text(p,source,"heading",size*.82,primary,92,yy,190,height,field,True)
            text(p,source,"special",size,dark,292,yy,1040,height,value or "—")
            yy+=height
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
