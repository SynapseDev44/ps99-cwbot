"""
image_gen.py  –  Pixel-perfekte Bilder wie CW-Ranking Bot Screenshots
"""
import io, math, asyncio, aiohttp
from PIL import Image, ImageDraw, ImageFont

FONT_REG  = "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"

# ── Exakte Farben aus den Screenshots ─────────────────────────────
BG          = (30, 31, 34)       # Discord-ähnliches Dunkelgrau
BG2         = (37, 39, 45)       # etwas heller für Karten
BLUE        = (88, 101, 242)     # Discord Blau
GREEN       = (87, 242, 135)     # Active / Joined grün
RED         = (237, 66, 69)      # Zero / Left rot
GOLD        = (255, 215, 0)      # Rang / Punkte
WHITE       = (255, 255, 255)
GRAY        = (148, 155, 164)    # Sekundärtext
DARKGRAY    = (79, 84, 92)       # Trennlinien
BAR_COL     = (88, 101, 242)     # Balkenfarbe (blau-lila wie Screenshot)
BAR_BG      = (64, 68, 75)       # Balken Hintergrund

def F(size, bold=False):
    return ImageFont.truetype(FONT_BOLD if bold else FONT_REG, size)

def fmt(n):
    try: n = float(n)
    except: return "0"
    if n >= 1e9:  return f"{n/1e9:.2f}b"
    if n >= 1e6:  return f"{n/1e6:.2f}m"
    if n >= 1e3:  return f"{n/1e3:.2f}k"
    return str(int(n))

def rrect(draw, xy, r, fill, outline=None, ow=1):
    draw.rounded_rectangle(xy, radius=r, fill=fill, outline=outline, width=ow)

async def get_icon(asset: str, size: int) -> Image.Image | None:
    if not asset: return None
    aid = asset.replace("rbxassetid://", "")
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(f"https://ps99.biggamesapi.io/image/{aid}",
                             timeout=aiohttp.ClientTimeout(total=8)) as r:
                if r.status == 200:
                    data = await r.read()
                    img  = Image.open(io.BytesIO(data)).convert("RGBA")
                    img  = img.resize((size, size), Image.LANCZOS)
                    mask = Image.new("L", (size, size), 0)
                    ImageDraw.Draw(mask).ellipse([0,0,size,size], fill=255)
                    out  = Image.new("RGBA", (size, size), (0,0,0,0))
                    out.paste(img, mask=mask)
                    return out
    except: pass
    return None

# ══════════════════════════════════════════════════════════════════
# 1.  CLAN BOARD  (Screenshot 1)
#     Header: [ZYXE] | Clan Rank #96 | Hourly Points 1.23k
#             Players 74 🔵 | Active 25 🟢 | Zero 49 🔴
#     Body: 3 Spalten mit Nr, Name, Balken, Punkte
# ══════════════════════════════════════════════════════════════════
async def generate_clan_board(clan_data: dict, clan_name: str,
                               rank, hourly_pts: int,
                               diff, uid_map: dict = None) -> io.BytesIO:

    members  = clan_data.get("Members", [])
    capacity = clan_data.get("MemberCapacity", 75)
    icon_str = clan_data.get("Icon", "")
    battle   = sorted(clan_data.get("Contribution",{}).get("Battle",[]),
                      key=lambda x: x.get("Points",0), reverse=True)
    total_m  = len(members)
    active   = sum(1 for m in battle if m.get("Points",0) > 0)
    zero_c   = total_m - active
    max_pts  = battle[0].get("Points",1) if battle else 1

    # Canvas
    COLS     = 3
    ROW_H    = 26
    HDR_H    = 145
    rows     = math.ceil(len(battle) / COLS) if battle else 1
    W        = 1080
    H        = HDR_H + rows * ROW_H + 24
    H        = max(H, 400)

    img  = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    # ── Header Hintergrund ──────────────────────────────────
    draw.rectangle([0, 0, W, HDR_H], fill=(28, 29, 33))

    # ── Clan Icon ───────────────────────────────────────────
    ISIZ = 72
    IX, IY = 16, 16
    icon = await get_icon(icon_str, ISIZ)
    if icon:
        # Glühender Ring
        ring = Image.new("RGBA", (ISIZ+8, ISIZ+8), (0,0,0,0))
        ImageDraw.Draw(ring).ellipse([0,0,ISIZ+8,ISIZ+8], outline=(88,101,242,200), width=3)
        img.paste(ring, (IX-4, IY-4), ring)
        img.paste(icon, (IX, IY), icon)
    else:
        draw.ellipse([IX, IY, IX+ISIZ, IY+ISIZ], fill=BLUE)
        draw.text((IX+ISIZ//2, IY+ISIZ//2), clan_name[0],
                  font=F(28, True), fill=WHITE, anchor="mm")

    # ── Clan Name ────────────────────────────────────────────
    NX = IX + ISIZ + 14
    draw.text((NX, 18), f"[{clan_name}]", font=F(26, True), fill=WHITE)

    # ── Rank Box ─────────────────────────────────────────────
    BX, BY = NX, 52
    rrect(draw, [BX, BY, BX+120, BY+38], r=6, fill=(40,42,50))
    draw.text((BX+8, BY+4),  "Clan Rank", font=F(10), fill=GRAY)
    draw.text((BX+8, BY+16), f"#{rank}" if rank else "?",
              font=F(16, True), fill=WHITE)

    # ── Hourly Points Box ────────────────────────────────────
    BX2 = BX + 130
    rrect(draw, [BX2, BY, BX2+140, BY+38], r=6, fill=(40,42,50))
    draw.text((BX2+8, BY+4),  "Hourly Points", font=F(10), fill=GRAY)
    draw.text((BX2+8, BY+16), fmt(hourly_pts),  font=F(16, True), fill=WHITE)

    # ── Players / Active / Zero Boxen rechts ─────────────────
    STAT_W = 90
    stats = [
        ("Players", str(total_m), WHITE,  (59, 130, 246)),
        ("Active",  str(active),  GREEN,  (34, 197, 94)),
        ("Zero",    str(zero_c),  RED,    (239, 68, 68)),
    ]
    sx = W - (STAT_W + 12) * 3 - 10
    for label, val, vcol, bcol in stats:
        rrect(draw, [sx, 14, sx+STAT_W, 14+80], r=8,
              fill=(38, 40, 48), outline=bcol, ow=2)
        draw.text((sx+STAT_W//2, 28), val,
                  font=F(26, True), fill=vcol, anchor="mt")
        draw.text((sx+STAT_W//2, 62), label,
                  font=F(11), fill=GRAY, anchor="mt")
        sx += STAT_W + 12

    # ── Diff ─────────────────────────────────────────────────
    if diff is not None:
        sign = "+" if diff >= 0 else ""
        col  = GREEN if diff >= 0 else RED
        draw.text((NX, 100), f"Δ {sign}{fmt(diff)}/h",
                  font=F(13, True), fill=col)

    # ── Trennlinie ───────────────────────────────────────────
    draw.line([(0, HDR_H-1), (W, HDR_H-1)], fill=(50, 52, 60), width=1)

    # ── Mitgliederliste 3 Spalten ────────────────────────────
    COL_W  = W // COLS
    BAR_W  = COL_W - 160   # Platz für Name + Punkte

    for idx, m in enumerate(battle):
        col  = idx % COLS
        row  = idx // COLS
        cx   = col * COL_W
        y    = HDR_H + row * ROW_H + 2
        pts  = m.get("Points", 0)
        uid  = m.get("UserID", 0)
        num  = idx + 1

        # Roblox username aus uid_map, sonst UID als Fallback
        _uid_map = uid_map or {}
        display  = _uid_map.get(int(uid), _uid_map.get(str(uid), str(uid)))

        # Zeilenhintergrund abwechselnd
        if row % 2 == 0:
            draw.rectangle([cx+2, y, cx+COL_W-2, y+ROW_H-2],
                           fill=(33, 34, 40))

        # Nummer  01–74
        ncol = GOLD if num <= 3 else GRAY
        draw.text((cx+8, y+4), f"{num:02d}",
                  font=F(12, num<=3), fill=ncol)

        # Roblox Username (gekürzt auf 14 Zeichen)
        name_disp = display[:14] + ("…" if len(display) > 14 else "")
        draw.text((cx+36, y+4), name_disp, font=F(12), fill=WHITE)

        # Fortschrittsbalken (wie im Screenshot – volle Breite)
        bar_x = cx + 36
        bar_y = y + ROW_H - 8
        bw    = int((pts / max_pts) * BAR_W) if max_pts > 0 else 0
        bw    = max(0, min(bw, BAR_W))
        draw.rounded_rectangle([bar_x, bar_y, bar_x+BAR_W, bar_y+4],
                                radius=2, fill=BAR_BG)
        if bw > 0:
            draw.rounded_rectangle([bar_x, bar_y, bar_x+bw, bar_y+4],
                                    radius=2, fill=BAR_COL)

        # Punkte rechts
        draw.text((cx+COL_W-8, y+4), fmt(pts),
                  font=F(12, True), fill=WHITE if pts>0 else GRAY,
                  anchor="ra")

    buf = io.BytesIO()
    img.save(buf, "PNG")
    buf.seek(0)
    return buf


# ══════════════════════════════════════════════════════════════════
# 2.  DIAMOND UPDATE  (Screenshot 2)
#     Titel: "Diamond Update • zyxe"
#     kxezy44 (kxezy44)
#     donated 50.00m 💎
#     (Total: 50.00m)
#     Clan Diamonds: 11.64b
#     30.04.2026 18:50
# ══════════════════════════════════════════════════════════════════
async def generate_diamond_update(clan_name: str, roblox_user: str,
                                   amount: float, user_total: float,
                                   clan_diamonds: float,
                                   icon_str: str = "") -> io.BytesIO:
    W, H = 480, 210
    img  = Image.new("RGB", (W, H), BG2)
    draw = ImageDraw.Draw(img)

    # Dezenter Hintergrund-Gradient
    for y in range(H):
        v = int(6*y/H)
        draw.line([(0,y),(W,y)], fill=(37+v, 39+v, 46+v))

    # Icon oben rechts (wie im Screenshot – großes Clan-Icon)
    icon = await get_icon(icon_str, 90)
    if icon:
        img.paste(icon, (W-105, 10), icon)
    else:
        # Fallback: blaues Diamond-Icon
        draw.ellipse([W-105, 10, W-15, 100], fill=(50, 60, 120))
        draw.text((W-60, 55), "💎", font=F(30), fill=BLUE, anchor="mm")

    # Titel  "Diamond Update • zyxe"
    draw.text((14, 12), "Diamond Update •", font=F(16, True), fill=WHITE)
    draw.text((14, 32), clan_name.lower(), font=F(16, True), fill=WHITE)

    # Content (genau wie Screenshot)
    y = 65
    # "kxezy44 (kxezy44)"
    draw.text((14, y), f"{roblox_user} ({roblox_user})",
              font=F(14, True), fill=WHITE)
    y += 22
    # "donated 50.00m 💎"
    draw.text((14, y), f"donated {fmt(amount)} 💎",
              font=F(13), fill=WHITE)
    y += 20
    # "(Total: 50.00m)"
    draw.text((14, y), f"(Total: {fmt(user_total)})",
              font=F(13), fill=WHITE)
    y += 20
    # "Clan Diamonds: 11.64b"
    draw.text((14, y), f"Clan Diamonds: {fmt(clan_diamonds)}",
              font=F(13), fill=WHITE)
    y += 28
    # Kleines Diamond
    draw.text((14, y), "💎", font=F(14), fill=BLUE)

    # Datum unten
    from datetime import datetime
    dt = datetime.now().strftime("%d.%m.%Y %H:%M")
    draw.text((14, H-18), dt, font=F(11), fill=GRAY)

    buf = io.BytesIO()
    img.save(buf, "PNG")
    buf.seek(0)
    return buf


# ══════════════════════════════════════════════════════════════════
# 3.  RANKING CHANGE  (Screenshot 3)
#     "[ZYXE]  Position Decreased by 1"
#     #98 ›› #99   (rot)  oder  #99 ›› #98  (grün)
#     Contributions 117.64k
# ══════════════════════════════════════════════════════════════════
async def generate_ranking_change(clan_name: str, old_rank: int,
                                   new_rank: int, contributions: int,
                                   icon_str: str = "") -> io.BytesIO:
    W, H    = 480, 155
    went_up = new_rank < old_rank
    delta   = abs(new_rank - old_rank)
    new_col = GREEN if went_up else RED
    direction = f"Position {'Increased' if went_up else 'Decreased'} by {delta}"

    img  = Image.new("RGB", (W, H), BG2)
    draw = ImageDraw.Draw(img)
    for y in range(H):
        v = int(6*y/H)
        draw.line([(0,y),(W,y)], fill=(37+v,39+v,46+v))

    # Karten-Box (dunkler Hintergrund mit Rand)
    rrect(draw, [8, 8, W-8, H-8], r=10,
          fill=(40, 42, 50), outline=(55, 58, 70), ow=1)

    # Clan Icon links in Box
    icon = await get_icon(icon_str, 38)
    IX, IY = 18, 18
    if icon:
        img.paste(icon, (IX, IY), icon)
    else:
        draw.ellipse([IX, IY, IX+38, IY+38], fill=BLUE)
        draw.text((IX+19, IY+19), clan_name[0], font=F(16,True),
                  fill=WHITE, anchor="mm")

    # "[ZYXE]"
    draw.text((IX+46, IY+2), f"[{clan_name.upper()}]",
              font=F(15, True), fill=WHITE)

    # "Position Decreased by 1" – rechts
    draw.text((W-18, IY+4), direction,
              font=F(11), fill=new_col, anchor="ra")

    # Rank Zahlen: #98 ›› #99
    y_rank = 68
    draw.text((22, y_rank), f"#{old_rank}",
              font=F(38, True), fill=WHITE)

    # Pfeil ›› (wie im Screenshot – breit)
    arr_x = 22 + len(f"#{old_rank}") * 22 + 10
    draw.text((arr_x, y_rank+10), "»", font=F(28, True), fill=GRAY)

    new_x = arr_x + 36
    draw.text((new_x, y_rank), f"#{new_rank}",
              font=F(38, True), fill=new_col)

    # "Contributions 117.64k"
    draw.text((22, H-26), "Contributions ",
              font=F(12), fill=GRAY)
    draw.text((22 + 100, H-26), fmt(contributions),
              font=F(12, True), fill=WHITE)

    buf = io.BytesIO()
    img.save(buf, "PNG")
    buf.seek(0)
    return buf


# ══════════════════════════════════════════════════════════════════
# 4.  PLAYER JOINED / LEFT  (Screenshot 4)
#     "Player Joined"  NEW MEMBER
#     👤 74/75 Members
#     → Sora (Assoum1) joined [ZYXE]
#     User: Sora (Assoum1)
# ══════════════════════════════════════════════════════════════════
async def generate_player_event(roblox_user: str, member_count: int,
                                 capacity: int, clan_name: str,
                                 joined: bool = True) -> io.BytesIO:
    W, H   = 480, 148
    color  = GREEN if joined else RED
    title  = "Player Joined" if joined else "Player Left"
    label  = "NEW MEMBER" if joined else "MEMBER LEFT"
    action = "joined" if joined else "left"

    img  = Image.new("RGB", (W, H), BG2)
    draw = ImageDraw.Draw(img)
    for y in range(H):
        v = int(6*y/H)
        draw.line([(0,y),(W,y)], fill=(37+v,39+v,46+v))

    # Karten-Box
    rrect(draw, [8, 8, W-8, H-8], r=10,
          fill=(40, 42, 50), outline=color, ow=1)

    # Kleiner Label oben
    draw.text((18, 15), label, font=F(9, True), fill=GRAY)

    # Avatar Kreis rechts (wie im Screenshot)
    AV = 64
    AX, AY = W-AV-20, 20
    draw.ellipse([AX, AY, AX+AV, AY+AV],
                 fill=(50, 54, 65), outline=color, width=2)
    draw.text((AX+AV//2, AY+AV//2), "👤",
              font=F(24), fill=WHITE, anchor="mm")

    # Titel "Player Joined" / "Player Left"
    draw.text((18, 28), title, font=F(20, True), fill=color)

    # Mitglieder-Zahl
    draw.text((18, 58), f"👤 {member_count}/{capacity} Members",
              font=F(12), fill=GRAY)

    # Pfeil + Name
    draw.text((18, 78), f"→ {roblox_user} ({roblox_user}) {action} [{clan_name}]",
              font=F(12), fill=WHITE)

    # "User: Sora (Assoum1)"
    draw.text((18, H-26), f"User: {roblox_user} ({roblox_user})",
              font=F(13, True), fill=WHITE)

    buf = io.BytesIO()
    img.save(buf, "PNG")
    buf.seek(0)
    return buf


# ══════════════════════════════════════════════════════════════════
# 5.  TOP CONTRIBUTORS  (Screenshot 5)
#     "Top Clanwar Contributors for ZYXE"
#     Current Event: StarryBattle
#     Current Rank: 96  |  Total Stars: 161.01k
#     Kick Cooldown / End
#     1. Shudin617 (Chubbylals) ⭐ 6.66k
#     ...10 Einträge
# ══════════════════════════════════════════════════════════════════
def _rel_time(ts) -> str:
    """Convert a unix timestamp to a human-readable relative string."""
    if not ts:
        return "?"
    import time as _time
    diff = int(ts) - int(_time.time())
    if diff <= 0:
        return "Beendet"
    d = diff // 86400
    h = (diff % 86400) // 3600
    m = (diff % 3600) // 60
    if d > 0:
        return f"in {d}T {h}h" if h else f"in {d} Tag{'en' if d>1 else ''}"
    if h > 0:
        return f"in {h}h {m}m" if m else f"in {h} Stunde{'n' if h>1 else ''}"
    return f"in {m} Min." if m > 0 else "gleich"


async def generate_top_contributors(clan_data: dict, clan_name: str,
                                     rank, battle_name: str,
                                     uid_map: dict,
                                     icon_str: str = "",
                                     battle_info: dict = None) -> io.BytesIO:
    battle   = sorted(clan_data.get("Contribution",{}).get("Battle",[]),
                      key=lambda x: x.get("Points",0), reverse=True)
    top10    = battle[:10]
    total_pts = sum(m.get("Points",0) for m in battle)
    kick_cd  = clan_data.get("LastKickTimestamp")
    cap      = clan_data.get("MemberCapacity",75)

    bi       = battle_info or {}
    end_ts   = bi.get("EndTime") or bi.get("endTime") or bi.get("EndTimestamp")

    W  = 400
    H  = 50 + 130 + len(top10)*42 + 50
    img  = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    for y in range(H):
        v = int(10*y/H)
        draw.line([(0,y),(W,y)], fill=(28+v,30+v,38+v))

    # Clan Icon oben rechts (wie im Screenshot)
    icon = await get_icon(icon_str, 80)
    if icon:
        img.paste(icon, (W-90, 8), icon)

    # Titel
    y = 10
    draw.text((12, y), "Top Clanwar Contributors for", font=F(14,True), fill=WHITE)
    y += 22
    draw.text((12, y), clan_name, font=F(16,True), fill=WHITE)

    # Stats-Block (wie Screenshot – untereinander)
    y += 28
    stats = [
        ("Current Event:", battle_name),
        ("Current Rank:",  str(rank) if rank else "?"),
        ("Total Stars:",   f"{fmt(total_pts)} ⭐"),
        ("Kick Cooldown:", _rel_time(kick_cd) if kick_cd else "in einem Tag"),
        ("End:",           _rel_time(end_ts)),
    ]
    for label, val in stats:
        draw.text((12, y), label, font=F(12), fill=GRAY)
        draw.text((12+130, y), val, font=F(12,True), fill=WHITE)
        y += 18

    # Trennlinie
    y += 6
    draw.line([(0, y), (W, y)], fill=(50,52,60))
    y += 10

    # Top 10 Liste (genau wie Screenshot)
    for i, m in enumerate(top10):
        uid   = m.get("UserID","?")
        name  = uid_map.get(uid, f"UserID {uid}")
        pts   = m.get("Points",0)

        if i % 2 == 0:
            draw.rectangle([0, y-2, W, y+38], fill=(33,35,42))

        # Nummer
        draw.text((12, y+2), f"{i+1}.", font=F(13,True), fill=GOLD)

        # Name + (DisplayName) genau wie Screenshot
        draw.text((38, y+2), name, font=F(13,True), fill=WHITE)

        # ⭐ Punkte
        draw.text((38, y+20), f"⭐ {fmt(pts)}", font=F(12), fill=GRAY)

        y += 42

    # Footer Buttons (wie Screenshot – nur Dekoration)
    rrect(draw, [10, H-40, 90, H-12], r=6, fill=(88,101,242))
    draw.text((50, H-26), "Back", font=F(12,True), fill=WHITE, anchor="mm")
    rrect(draw, [100, H-40, 180, H-12], r=6, fill=(88,101,242))
    draw.text((140, H-26), "Next", font=F(12,True), fill=WHITE, anchor="mm")
    rrect(draw, [190, H-40, 270, H-12], r=6, fill=(79,84,92))
    draw.text((230, H-26), "Close", font=F(12,True), fill=WHITE, anchor="mm")

    buf = io.BytesIO()
    img.save(buf, "PNG")
    buf.seek(0)
    return buf
