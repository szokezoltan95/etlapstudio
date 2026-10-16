"""Create the scalable ornament pack used by ÉtlapStúdió."""
from pathlib import Path
import json

THEMES = {
    'classic': ('Klasszikus', '#1D6B50', '#C39A5E', '#F0F5EF'),
    'spring': ('Tavasz', '#477A5B', '#D99BAA', '#FDF1F3'),
    'summer': ('Nyár', '#157A8A', '#E3A543', '#FFF8E7'),
    'autumn': ('Ősz', '#935437', '#C39349', '#FBF3E9'),
    'winter': ('Tél', '#3E7390', '#9BBACF', '#F0F7FA'),
    'christmas': ('Karácsony', '#1B6546', '#B34542', '#F7F1EC'),
    'easter': ('Húsvét', '#68835A', '#C998AD', '#F7F3EA'),
}

# All ornaments are drawn as real SVG geometry: they remain sharp on A4 prints.
def art(key, a, b, pale):
    if key == 'classic':
        return f'''<path d="M5 65 C24 60 23 27 50 30 S75 55 94 19" fill="none" stroke="{a}" stroke-width="2"/>
        <path d="M26 53 Q5 33 19 24 Q42 28 26 53 M45 35 Q33 9 48 7 Q61 18 45 35 M68 34 Q67 6 85 8 Q90 23 68 34" fill="{pale}" stroke="{a}" stroke-width="1.4"/>
        <circle cx="49" cy="30" r="4" fill="{b}"/><circle cx="82" cy="32" r="3" fill="{b}"/>'''
    if key == 'spring':
        petals=''.join(f'<ellipse cx="0" cy="-11" rx="6" ry="11" transform="rotate({n*72})" fill="{pale}" stroke="{b}" stroke-width="1.5"/>' for n in range(5))
        return f'''<path d="M2 79 Q28 62 47 35 Q66 19 96 27" fill="none" stroke="{a}" stroke-width="2.2"/>
        <path d="M22 67 Q5 51 14 42 Q33 44 22 67 M65 24 Q65 2 82 7 Q83 19 65 24" fill="{a}" opacity=".8"/>
        <g transform="translate(47 35)">{petals}<circle r="6" fill="{b}"/></g>
        <circle cx="83" cy="30" r="5" fill="{b}" opacity=".7"/>'''
    if key == 'summer':
        rays=''.join(f'<path d="M51 45 L51 19" transform="rotate({n*45} 51 45)" stroke="{b}" stroke-width="1.5"/>' for n in range(8))
        return f'''<path d="M1 75 Q25 61 44 75 T94 75" fill="none" stroke="{a}" stroke-width="2.2"/>
        <circle cx="51" cy="45" r="34" fill="{pale}" stroke="{b}" stroke-width="3"/>
        <circle cx="51" cy="45" r="27" fill="none" stroke="{b}" stroke-width="1.2"/>{rays}
        <path d="M72 22 Q78 3 94 6 Q94 20 72 22" fill="{a}"/>'''
    if key == 'autumn':
        return f'''<path d="M10 82 Q44 53 87 13" fill="none" stroke="{a}" stroke-width="2"/>
        <path d="M38 61 C13 55 6 37 14 17 Q24 27 40 22 Q53 42 38 61 Z" fill="{b}" stroke="{a}" stroke-width="1.6"/>
        <path d="M71 31 C57 29 50 17 57 4 Q67 12 82 8 Q87 26 71 31 Z" fill="{a}" opacity=".85"/>
        <path d="M13 18 Q29 42 38 61 M57 5 Q68 20 71 31" fill="none" stroke="{pale}" stroke-width="1.4"/>
        <circle cx="78" cy="61" r="5" fill="{b}"/><circle cx="88" cy="55" r="4" fill="{b}"/>'''
    if key == 'winter':
        lines=''.join(f'<g transform="rotate({n*60} 50 50)"><path d="M50 16 V84 M43 25 L50 33 L57 25 M43 75 L50 67 L57 75" fill="none" stroke="{a}" stroke-width="2" stroke-linecap="round"/></g>' for n in range(3))
        return f'''<circle cx="50" cy="50" r="36" fill="{pale}" opacity=".8"/>{lines}<circle cx="50" cy="50" r="5" fill="{b}"/>
        <circle cx="12" cy="28" r="2" fill="{b}"/><circle cx="89" cy="79" r="2" fill="{b}"/>'''
    if key == 'christmas':
        return f'''<path d="M4 83 Q44 53 89 14" stroke="{a}" stroke-width="2.5" fill="none"/>
        <path d="M39 58 C11 65 5 42 24 35 Q34 42 39 58 M62 36 Q58 12 76 7 Q82 25 62 36 M61 58 Q89 49 94 64 Q75 76 61 58" fill="{a}" stroke="{a}" stroke-width="1.6"/>
        <circle cx="47" cy="47" r="7" fill="{b}"/><circle cx="58" cy="47" r="7" fill="{b}"/><circle cx="53" cy="58" r="7" fill="{b}"/>
        <path d="M84 6 l2 6 6 2 -6 2 -2 6 -2 -6 -6 -2 6 -2z" fill="{b}"/>'''
    if key == 'easter':
        return f'''<path d="M4 81 Q45 75 96 80" fill="none" stroke="{a}" stroke-width="2"/>
        <path d="M18 81 Q9 33 30 22 Q51 36 41 81 Z" fill="{pale}" stroke="{b}" stroke-width="2"/>
        <path d="M54 81 Q51 22 73 11 Q96 38 87 81 Z" fill="{pale}" stroke="{a}" stroke-width="2"/>
        <path d="M15 56 Q30 42 44 56 M17 68 Q30 56 43 68 M53 51 Q72 34 89 51 M54 66 Q72 51 89 66" fill="none" stroke="{b}" stroke-width="2"/>
        <circle cx="73" cy="29" r="3" fill="{b}"/>'''
    raise KeyError(key)


def svg(viewbox, body, width=600, height=100):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="{viewbox}" width="{width}" height="{height}">{body}</svg>'''


def generate(folder: Path):
    folder.mkdir(parents=True, exist_ok=True)
    for key, (label, a, b, pale) in THEMES.items():
        target = folder / key
        target.mkdir(exist_ok=True)
        motif=art(key,a,b,pale)
        header=f'''<path d="M8 83 H590" stroke="{a}" stroke-width="1.8" opacity=".65"/>
            <g transform="translate(2 2) scale(.85)">{motif}</g>
            <g transform="translate(598 2) scale(-.85 .85)">{motif}</g>
            <path d="M132 84 H468" stroke="{b}" stroke-width="1" opacity=".8"/>'''
        divider=f'''<path d="M12 50 H235 M365 50 H588" stroke="{a}" stroke-width="1.6" opacity=".65"/>
            <g transform="translate(250 7) scale(.88)">{motif}</g>'''
        corner=f'''<g transform="translate(12 12) scale(1.1)">{motif}</g>
            <path d="M8 130 V10 H130" fill="none" stroke="{a}" stroke-width="2"/>'''
        (target/'header.svg').write_text(svg('0 0 600 100',header),encoding='utf-8')
        (target/'divider.svg').write_text(svg('0 0 600 100',divider),encoding='utf-8')
        (target/'corner.svg').write_text(svg('0 0 145 145',corner,145,145),encoding='utf-8')
        (target/'manifest.json').write_text(json.dumps({
            'schema_version': 1, 'id': key, 'name': label,
            'palette': {'primary': a, 'accent': b, 'background': pale},
            'assets': {'header': 'header.svg', 'divider': 'divider.svg', 'corner': 'corner.svg'},
        },ensure_ascii=False,indent=2)+'\n', encoding='utf-8')


if __name__=='__main__':
    generate(Path(__file__).resolve().parent/'themes_builtin')
