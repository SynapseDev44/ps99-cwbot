"""
image_gen.py  –  Generiert Clan-Board Bilder wie CW-Ranking Bot
Benutzt Pillow (PIL) + io.BytesIO (kein Speichern auf Disk!)
"""

import io
import math
import asyncio
import aiohttp
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# ── Font Paths ─────────────────────────────────────────────────────
FONT_REGULAR = "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"
FONT_BOLD    = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"

# ── Farben (exakt wie Screenshots) ────────────────────────────────
BG_DARK      = (15, 17, 20)          # fast schwarz
BG_CARD      = (25, 28, 35)          # dunkle Karte
BG_HEADER    = (20, 22, 30)          # Header-Bereich
ACCENT_BLUE  = (88, 101, 242)        # Discord Blau
ACCENT_GREEN = (87, 242, 135)        # Grün für Active
ACCENT_RED   = (237, 66, 69)         # Rot für Zero
ACCENT_GOLD  = (255, 215, 0)         # Gold für Rank
TEXT_WHITE   = (255, 255, 255)
TEXT_GRAY    = (160, 165, 180)
TEXT_DIM     = (100, 105, 120)
BAR_GREEN    = (87, 242, 135)
BAR_ORANGE   = (255, 165, 0)
BAR_RED      = (237, 66, 69)

def _font(size, bold=False):
    path = FONT_BOLD if bold else FONT_REGULAR
    return ImageFont.truetype(path, size)

def _fmt(n) -> str:
    try: n = float(n)
    except: return "0"
    if n >= 1_000_000_000: return f"{n/1_000_000_000:.2f}b"
    if n >= 1_000_000:     return f"{n/1_000_000:.2f}m"
    if n >= 1_000:         return f"{n/1_000:.2f}k"
    return str(int(n))

def _bar_color(pts, max_pts):
    if max_pts == 0: return BAR_RED
    ratio = pts / max_pts
    if ratio > 0.6:  return BAR_GREEN
    if ratio > 0.2:  return BAR_ORANGE
    return BAR_RED

def _rounded_rect(draw, xy, radius, fill, outline=None, outline_width=1):
    x1, y1, x2, y2 = xy
    draw.rounded_rectangle([x1, y1, x2, y2], radius=radius, fill=fill,
                            outline=outline, width=outline_width)

async def fetch_clan_icon(icon_asset: str) -> Image.Image | None:
    """Lädt das Clan-Icon von der PS99 API."""
    if not icon_asset:
        return None
    asset_id = icon_asset.replace("rbxassetid://", "")
    url = f"https://ps99.biggamesapi.io/image/{asset_id}"
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(url, timeout=aiohttp.ClientTimeout(total=8)) as r:
                if r.status == 200:
                    data = await r.read()
                    img = Image.open(io.BytesIO(data)).convert("RGBA")
                    return img
    except Exception:
        pass
    return None

def make_circular(img: Image.Image, size: int) -> Image.Image:
    """Macht ein Bild kreisförmig mit Rand."""
    img = img.resize((size, size), Image.LANCZOS)
    mask = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(mask)
    d.ellipse([0, 0, size, size], fill=255)
    result = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    result.paste(img, (0, 0), mask)
    return result

# ─────────────────────────────────────────────────────────────────
# HAUPT-FUNKTION: Clan Board (wie Screenshot 1)
# ─────────────────────────────────────────────────────────────────
async def generate_clan_board(clan_data: dict, clan_name: str,
                               rank: int | None, hourly_pts: int,
                               diff: int | None) -> io.BytesIO:
    """
    Generiert das große Clan-Board Bild.
    Gibt io.BytesIO zurück – kein Speichern auf Disk!
    """
    # ── Daten aus clan_data lesen ──────────────────────────────
    # HIER deine JSON-Felder anpassen falls nötig:
    members_list = clan_data.get("Members", [])
    capacity     = clan_data.get("MemberCapacity", 75)
    clan_icon    = clan_data.get("Icon", "")          # z.B. "rbxassetid://123456"

    battle       = sorted(
        clan_data.get("Contribution", {}).get("Battle", []),
        key=lambda x: x.get("Points", 0), reverse=True
    )
    total_m  = len(members_list)
    active   = sum(1 for m in battle if m.get("Points", 0) > 0)
    zero_c   = total_m - active
    diamonds = clan_data.get("DepositedDiamonds", 0) or 0
    total_pts = sum(m.get("Points", 0) for m in battle)
    max_pts   = battle[0].get("Points", 1) if battle else 1

    # ── Canvas Größe berechnen ─────────────────────────────────
    ROW_H    = 28
    COLS     = 3
    rows_per_col = math.ceil(len(battle) / COLS) if battle else 1
    HEADER_H = 160
    LIST_H   = rows_per_col * ROW_H + 20
    W        = 1100
    H        = HEADER_H + LIST_H + 30
    H        = max(H, 500)

    img  = Image.new("RGB", (W, H), BG_DARK)
    draw = ImageDraw.Draw(img)

    # ── Hintergrund Gradient-ähnlich ──────────────────────────
    for y in range(H):
        alpha = int(8 * (1 - y/H))
        draw.line([(0, y), (W, y)], fill=(20+alpha, 22+alpha, 35+alpha))

    # ── Clan Icon ─────────────────────────────────────────────
    ICON_SIZE = 80
    ICON_X, ICON_Y = 20, 30
    icon_img = await fetch_clan_icon(clan_icon)
    if icon_img:
        icon_circle = make_circular(icon_img, ICON_SIZE)
        # Glow-Effekt
        glow = Image.new("RGBA", (ICON_SIZE+20, ICON_SIZE+20), (0,0,0,0))
        gd = ImageDraw.Draw(glow)
        gd.ellipse([5,5,ICON_SIZE+15,ICON_SIZE+15], fill=(88,101,242,60))
        img.paste(glow, (ICON_X-10, ICON_Y-10), glow)
        img.paste(icon_circle, (ICON_X, ICON_Y), icon_circle)
    else:
        # Fallback: Buchstabe im Kreis
        _rounded_rect(draw, [ICON_X, ICON_Y, ICON_X+ICON_SIZE, ICON_Y+ICON_SIZE],
                      radius=40, fill=ACCENT_BLUE)
        f = _font(32, bold=True)
        letter = clan_name[0].upper()
        bbox = draw.textbbox((0,0), letter, font=f)
        lw, lh = bbox[2]-bbox[0], bbox[3]-bbox[1]
        draw.text((ICON_X + ICON_SIZE//2 - lw//2,
                   ICON_Y + ICON_SIZE//2 - lh//2), letter, font=f, fill=TEXT_WHITE)

    # ── Clan Name ─────────────────────────────────────────────
    NAME_X = ICON_X + ICON_SIZE + 18
    draw.text((NAME_X, 35), f"[{clan_name}]", font=_font(32, bold=True),
              fill=ACCENT_GOLD)

    # ── Header Boxen: Rank | Hourly Points ────────────────────
    boxes = [
        ("Clan Rank",     f"#{rank}" if rank else "?",        ACCENT_BLUE),
        ("Hourly Points", _fmt(hourly_pts),                   (100, 200, 100)),
    ]
    bx = NAME_X
    for label, value, color in boxes:
        bw, bh = 160, 48
        _rounded_rect(draw, [bx, 75, bx+bw, 75+bh], radius=8,
                      fill=(30, 33, 45), outline=color, outline_width=2)
        draw.text((bx+10, 79), label, font=_font(11), fill=TEXT_GRAY)
        draw.text((bx+10, 93), value, font=_font(18, bold=True), fill=TEXT_WHITE)
        bx += bw + 12

    # ── Stats: Players | Active | Zero ────────────────────────
    stats = [
        ("Players", str(total_m), TEXT_WHITE,   ACCENT_BLUE),
        ("Active",  str(active),  ACCENT_GREEN, ACCENT_GREEN),
        ("Zero",    str(zero_c),  ACCENT_RED,   ACCENT_RED),
    ]
    sx = W - 420
    for label, value, vcol, box_col in stats:
        sw = 110
        _rounded_rect(draw, [sx, 30, sx+sw, 100], radius=8,
                      fill=(25, 28, 38), outline=box_col, outline_width=2)
        draw.text((sx + sw//2, 42), value,
                  font=_font(28, bold=True), fill=vcol,
                  anchor="mt")
        draw.text((sx + sw//2, 76), label,
                  font=_font(13), fill=TEXT_GRAY,
                  anchor="mt")
        sx += sw + 15

    # ── Diamonds + Diff ───────────────────────────────────────
    dy = 110
    draw.text((NAME_X, dy), f"💎 {_fmt(diamonds)}", font=_font(14), fill=(150, 180, 255))
    if diff is not None:
        sign = "+" if diff >= 0 else ""
        col  = ACCENT_GREEN if diff >= 0 else ACCENT_RED
        draw.text((NAME_X + 180, dy), f"Δ {sign}{_fmt(diff)}/h",
                  font=_font(14, bold=True), fill=col)

    # ── Trennlinie ────────────────────────────────────────────
    draw.line([(0, HEADER_H - 10), (W, HEADER_H - 10)],
              fill=(40, 44, 60), width=1)

    # ── Mitgliederliste in 3 Spalten ──────────────────────────
    COL_W  = W // COLS
    BAR_MAX_W = COL_W - 120

    for idx, m in enumerate(battle):
        col   = idx % COLS
        row   = idx // COLS
        x     = col * COL_W + 12
        y     = HEADER_H + row * ROW_H + 8
        pts   = m.get("Points", 0)
        uid   = str(m.get("UserID", "?"))
        num   = idx + 1

        # Zeilenhintergrund abwechselnd
        if row % 2 == 0:
            draw.rectangle([col*COL_W, y-3, (col+1)*COL_W-4, y+ROW_H-5],
                           fill=(20, 23, 32))

        # Nummer
        num_col = ACCENT_GOLD if num <= 3 else TEXT_GRAY
        draw.text((x, y), f"{num:02d}", font=_font(12, bold=num<=3), fill=num_col)

        # Dot
        dot_col = ACCENT_GREEN if pts > 0 else ACCENT_RED
        draw.ellipse([x+30, y+5, x+40, y+15], fill=dot_col)

        # Username (gekürzt)
        uid_display = uid[:12] + "…" if len(uid) > 12 else uid
        draw.text((x+46, y), uid_display, font=_font(12), fill=TEXT_WHITE)

        # Progress Bar
        bar_w = max(0, int((pts / max_pts) * BAR_MAX_W)) if max_pts > 0 else 0
        bar_x = x + 46
        bar_y = y + ROW_H - 10
        draw.rounded_rectangle([bar_x, bar_y, bar_x + BAR_MAX_W, bar_y+4],
                                radius=2, fill=(40, 44, 55))
        if bar_w > 0:
            draw.rounded_rectangle([bar_x, bar_y, bar_x + bar_w, bar_y+4],
                                    radius=2, fill=_bar_color(pts, max_pts))

        # Punkte rechts
        pts_str = _fmt(pts)
        pts_x   = (col+1)*COL_W - 8
        draw.text((pts_x, y), pts_str, font=_font(12, bold=True),
                  fill=TEXT_WHITE if pts > 0 else TEXT_DIM, anchor="ra")

    # ── Footer ────────────────────────────────────────────────
    draw.text((W//2, H-12), "PS99 ClanWar Bot",
              font=_font(11), fill=TEXT_DIM, anchor="mt")

    # ── Als BytesIO zurückgeben (kein Speichern!) ─────────────
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf


# ─────────────────────────────────────────────────────────────────
# Diamond Update Bild (wie Screenshot 2)
# ─────────────────────────────────────────────────────────────────
async def generate_diamond_update(clan_name: str, roblox_user: str,
                                   amount: float, user_total: float,
                                   clan_diamonds: float,
                                   clan_icon: str = "") -> io.BytesIO:
    W, H = 500, 220
    img  = Image.new("RGB", (W, H), BG_CARD)
    draw = ImageDraw.Draw(img)

    # Hintergrund
    for y in range(H):
        v = int(5 * y/H)
        draw.line([(0,y),(W,y)], fill=(25+v, 28+v, 38+v))

    # Blauer linker Balken
    draw.rectangle([0, 0, 4, H], fill=ACCENT_BLUE)

    # Icon rechts
    ICON_SIZE = 80
    icon_img = await fetch_clan_icon(clan_icon)
    if icon_img:
        ic = make_circular(icon_img, ICON_SIZE)
        img.paste(ic, (W - ICON_SIZE - 20, 20), ic)
    else:
        _rounded_rect(draw, [W-100, 20, W-20, 100], radius=40, fill=ACCENT_BLUE)
        draw.text((W-60, 60), "💎", font=_font(30), fill=TEXT_WHITE, anchor="mm")

    # Titel
    draw.text((18, 15), "💎 Diamond Update", font=_font(18, bold=True), fill=TEXT_WHITE)
    draw.text((18, 38), f"• {clan_name.lower()}", font=_font(14), fill=TEXT_GRAY)

    # Content
    y = 70
    draw.text((18, y), f"{roblox_user} ({roblox_user})",
              font=_font(15, bold=True), fill=TEXT_WHITE)
    y += 25
    draw.text((18, y), "donated ", font=_font(14), fill=TEXT_GRAY)
    draw.text((18 + 70, y), f"{_fmt(amount)} 💎", font=_font(14, bold=True), fill=ACCENT_GOLD)
    y += 22
    draw.text((18, y), f"(Total: {_fmt(user_total)})", font=_font(13), fill=TEXT_GRAY)
    y += 22
    draw.text((18, y), "Clan Diamonds: ", font=_font(13), fill=TEXT_GRAY)
    draw.text((18 + 118, y), f"{_fmt(clan_diamonds)}", font=_font(13, bold=True), fill=(150, 200, 255))

    # Kleines Diamond Icon unten
    draw.text((18, H-30), "💎", font=_font(16), fill=ACCENT_BLUE)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf


# ─────────────────────────────────────────────────────────────────
# Ranking Change Bild (wie Screenshot 3)
# ─────────────────────────────────────────────────────────────────
async def generate_ranking_change(clan_name: str, old_rank: int,
                                   new_rank: int, contributions: int,
                                   clan_icon: str = "") -> io.BytesIO:
    W, H = 500, 180
    went_up   = new_rank < old_rank
    delta     = abs(new_rank - old_rank)
    bar_color = ACCENT_GREEN if went_up else ACCENT_RED
    direction = f"Position {'Increased' if went_up else 'Decreased'} by {delta}"

    img  = Image.new("RGB", (W, H), BG_CARD)
    draw = ImageDraw.Draw(img)
    for y in range(H):
        v = int(5*y/H)
        draw.line([(0,y),(W,y)], fill=(25+v,28+v,38+v))

    draw.rectangle([0, 0, 4, H], fill=bar_color)

    # Titel
    draw.text((18, 15), f"{clan_name.upper()} RANKING",
              font=_font(18, bold=True), fill=TEXT_WHITE)

    # Icon
    icon_img = await fetch_clan_icon(clan_icon)
    if icon_img:
        ic = make_circular(icon_img, 60)
        img.paste(ic, (W-80, 15), ic)

    # Card Hintergrund
    _rounded_rect(draw, [18, 50, W-18, H-15], radius=10,
                  fill=(30, 33, 45), outline=(50, 55, 75), outline_width=1)

    # Clan Name in Card
    draw.text((30, 62), f"[{clan_name.upper()}]",
              font=_font(16, bold=True), fill=TEXT_WHITE)
    draw.text((W//2, 62), direction,
              font=_font(12), fill=bar_color, anchor="mt")

    # Rank Änderung: #98 → #99
    draw.text((50, 88), f"#{old_rank}",
              font=_font(36, bold=True), fill=TEXT_WHITE)
    draw.text((50 + 90, 100), "›", font=_font(30), fill=TEXT_GRAY)
    new_col = ACCENT_GREEN if went_up else ACCENT_RED
    draw.text((50 + 130, 88), f"#{new_rank}",
              font=_font(36, bold=True), fill=new_col)

    # Contributions
    draw.text((30, H-30), "Contributions ",
              font=_font(13), fill=TEXT_GRAY)
    draw.text((30 + 110, H-30), _fmt(contributions),
              font=_font(13, bold=True), fill=TEXT_WHITE)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf


# ─────────────────────────────────────────────────────────────────
# Player Joined / Left Bild (wie Screenshot 4)
# ─────────────────────────────────────────────────────────────────
async def generate_player_event(roblox_user: str, member_count: int,
                                 capacity: int, clan_name: str,
                                 joined: bool = True) -> io.BytesIO:
    W, H  = 500, 160
    color = ACCENT_GREEN if joined else ACCENT_RED
    title = "Player Joined" if joined else "Player Left"
    label = "NEW MEMBER" if joined else "MEMBER LEFT"

    img  = Image.new("RGB", (W, H), BG_CARD)
    draw = ImageDraw.Draw(img)
    for y in range(H):
        v = int(5*y/H)
        draw.line([(0,y),(W,y)], fill=(25+v,28+v,38+v))
    draw.rectangle([0, 0, 4, H], fill=color)

    # Avatar Kreis rechts
    _rounded_rect(draw, [W-90, 15, W-15, 90], radius=38, fill=(40,44,55))
    draw.text((W-52, 52), "👤", font=_font(28), fill=color, anchor="mm")

    # Labels
    draw.text((18, 15), f"{'📥' if joined else '📤'} {title}",
              font=_font(18, bold=True), fill=color)
    draw.text((18, 45), label, font=_font(11, bold=True), fill=TEXT_GRAY)

    # Content
    draw.text((18, 62), f"👤 {member_count}/{capacity} Members",
              font=_font(13), fill=TEXT_GRAY)
    arrow = "➜"
    action = "joined" if joined else "left"
    draw.text((18, 83), f"{arrow} {roblox_user} ({roblox_user}) {action} [{clan_name}]",
              font=_font(13), fill=TEXT_WHITE)
    draw.text((18, H-30), f"User: {roblox_user} ({roblox_user})",
              font=_font(13, bold=True), fill=TEXT_WHITE)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf


# ─────────────────────────────────────────────────────────────────
# Top Contributors Bild (wie Screenshot 5)
# ─────────────────────────────────────────────────────────────────
async def generate_top_contributors(clan_data: dict, clan_name: str,
                                     rank: int | None, battle_name: str,
                                     uid_map: dict,
                                     clan_icon: str = "") -> io.BytesIO:
    battle    = sorted(clan_data.get("Contribution",{}).get("Battle",[]),
                       key=lambda x: x.get("Points",0), reverse=True)
    top10     = battle[:10]
    total_pts = sum(m.get("Points",0) for m in battle)
    kick_cd   = clan_data.get("LastKickTimestamp")
    mc        = len(clan_data.get("Members",[]))
    capacity  = clan_data.get("MemberCapacity",75)

    W = 420
    H = 80 + len(top10)*38 + 40
    img  = Image.new("RGB", (W, H), BG_CARD)
    draw = ImageDraw.Draw(img)
    for y in range(H):
        v = int(8*y/H)
        draw.line([(0,y),(W,y)], fill=(22+v,25+v,35+v))
    draw.rectangle([0,0,4,H], fill=ACCENT_GOLD)

    # Icon rechts oben
    icon_img = await fetch_clan_icon(clan_icon)
    if icon_img:
        ic = make_circular(icon_img, 64)
        img.paste(ic, (W-80, 10), ic)

    # Titel
    draw.text((14, 12), f"Top Clanwar Contributors", font=_font(15, bold=True), fill=TEXT_WHITE)
    draw.text((14, 32), f"for {clan_name}", font=_font(13, bold=True), fill=ACCENT_GOLD)

    # Stats
    y = 55
    stats_text = f"Current Event: {battle_name}   Rank: #{rank if rank else '?'}   Stars: {_fmt(total_pts)} ⭐"
    draw.text((14, y), stats_text, font=_font(11), fill=TEXT_GRAY)

    # Trennlinie
    draw.line([(0, 75), (W, 75)], fill=(40,44,60))

    # Top 10 Liste
    medals = ["🥇","🥈","🥉"]
    for i, m in enumerate(top10):
        uid  = m.get("UserID","?")
        name = uid_map.get(uid, f"UserID {uid}")
        pts  = m.get("Points",0)
        ry   = 80 + i*38

        if i % 2 == 0:
            draw.rectangle([0, ry, W, ry+36], fill=(28,31,42))

        medal = medals[i] if i < 3 else f"{i+1}."
        draw.text((14, ry+8), f"{medal}", font=_font(14), fill=ACCENT_GOLD)
        draw.text((50, ry+8), name, font=_font(13, bold=True), fill=TEXT_WHITE)
        draw.text((50, ry+24), f"⭐ {_fmt(pts)}", font=_font(11), fill=TEXT_GRAY)
        draw.text((W-14, ry+12), _fmt(pts), font=_font(13, bold=True),
                  fill=ACCENT_GOLD, anchor="ra")

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf
