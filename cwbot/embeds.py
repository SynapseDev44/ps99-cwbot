"""
embeds.py  –  Alle Discord-Embeds exakt nach den CW-Ranking Screenshots
"""

import discord
from datetime import datetime, timezone
from fmt import fmt, rank_medal, bar
import api as ps99api

# ── Farben ────────────────────────────────────────────────────────────────────
C_GOLD  = 0xFFD700
C_GREEN = 0x57F287
C_RED   = 0xED4245
C_BLUE  = 0x5865F2
C_PINK  = 0xE91E8C
C_DARK  = 0x1E1F22   # fast-schwarz wie CW-Ranking Hintergrund

def _now():
    return discord.utils.utcnow()

# ─────────────────────────────────────────────────────────────────────────────
# 1.  !cb  /  /clan  →  Großes Dashboard  (Screenshot 1)
#     [ZYXE]  |  Clan Rank #96  |  Hourly Points 1.23k
#     Players 74 | Active 25 | Zero 49
#     Mitgliederliste in 3 Spalten
# ─────────────────────────────────────────────────────────────────────────────
def clan_board(clan_data: dict, clan_name: str, rank: int | None,
               hrly: int, diff: int | None) -> discord.Embed:

    members    = clan_data.get("Members", [])
    capacity   = clan_data.get("MemberCapacity", 75)
    battle     = ps99api.battle_sorted(clan_data)
    total_m    = len(members)
    active     = sum(1 for m in battle if m.get("Points", 0) > 0)
    zero_count = total_m - active
    diamonds   = ps99api.deposited_diamonds(clan_data)

    rank_str = f"#{rank}" if rank else "?"

    e = discord.Embed(color=C_DARK)

    # ── Kopfzeile (wie Screenshot) ──
    header = (
        f"**[{clan_name}]**\n"
        f"Clan Rank  **{rank_str}**   │   "
        f"Hourly Points  **{fmt(hrly)}**\n"
        f"Players **{total_m}** 🔵   Active **{active}** 🟢   Zero **{zero_count}** 🔴\n"
        f"💎 Deposited  **{fmt(diamonds)}**"
    )
    if diff is not None:
        sign = "+" if diff >= 0 else ""
        header += f"   │   Δ/h **{sign}{fmt(diff)}**"

    e.description = header

    # ── Mitgliederliste in 3 Spalten ──
    max_pts = battle[0]["Points"] if battle else 1

    def member_line(idx: int, m: dict) -> str:
        pts  = m.get("Points", 0)
        uid  = m.get("UserID", "?")
        dot  = "🟢" if pts > 0 else "🔴"
        b    = bar(pts, max_pts, 5)
        return f"`{idx+1:02d}` {dot} `{str(uid)[:11]:<11}` **{fmt(pts)}**"

    col_size = max(1, -(-len(battle) // 3))   # ceiling division
    cols = [battle[i * col_size:(i + 1) * col_size] for i in range(3)]
    for col in cols:
        if col:
            e.add_field(
                name="\u200b",
                value="\n".join(member_line(battle.index(m), m) for m in col),
                inline=True
            )

    e.set_footer(text=f"PS99 ClanWar Bot  •  {clan_name}")
    e.timestamp = _now()
    return e


# ─────────────────────────────────────────────────────────────────────────────
# 2.  Diamond Update  (Screenshot 2)
#     "Diamond Update • zyxe"
#     kxezy44 (kxezy44) donated 50.00m  (Total: 50.00m)
#     Clan Diamonds: 11.64b
# ─────────────────────────────────────────────────────────────────────────────
def diamond_update(clan_name: str, roblox_user: str,
                   amount: float, user_total: float,
                   clan_diamonds: float) -> discord.Embed:
    e = discord.Embed(
        title=f"💎 Diamond Update • {clan_name.lower()}",
        color=C_BLUE,
    )
    e.description = (
        f"**{roblox_user} ({roblox_user})**\n"
        f"donated **{fmt(amount)}** 💎\n"
        f"(Total: {fmt(user_total)})\n"
        f"Clan Diamonds: **{fmt(clan_diamonds)}**\n\n"
        f"💎"
    )
    e.timestamp = _now()
    return e


# ─────────────────────────────────────────────────────────────────────────────
# 3.  Ranking Change  (Screenshot 3)
#     "ZYXE RANKING ✅ APP"
#     [ZYXE]  Position Decreased by 1
#     #98 → #99   Contributions 117.64k
# ─────────────────────────────────────────────────────────────────────────────
def ranking_change(clan_name: str, old_rank: int, new_rank: int,
                   contributions: int) -> discord.Embed:
    went_up = new_rank < old_rank
    delta   = abs(new_rank - old_rank)
    if went_up:
        color     = C_GREEN
        direction = f"Position Increased by {delta}"
        arrow     = "📈"
    else:
        color     = C_RED
        direction = f"Position Decreased by {delta}"
        arrow     = "📉"

    e = discord.Embed(
        title=f"{arrow} {clan_name.upper()} RANKING",
        color=color,
    )
    e.add_field(
        name=direction,
        value=(
            f"**[{clan_name.upper()}]**\n"
            f"**#{old_rank}**  ›  **#{new_rank}**\n"
            f"Contributions  **{fmt(contributions)}**"
        ),
        inline=False,
    )
    e.timestamp = _now()
    return e


# ─────────────────────────────────────────────────────────────────────────────
# 4.  Player Joined / Left  (Screenshot 4)
#     "Player Joined"   NEW MEMBER
#     74/75 Members  •  Sora (Assoum1) joined [ZYXE]
#     User: Sora (Assoum1)
# ─────────────────────────────────────────────────────────────────────────────
def player_joined(roblox_user: str, member_count: int,
                  capacity: int, clan_name: str) -> discord.Embed:
    e = discord.Embed(title="📥 Player Joined", color=C_GREEN)
    e.add_field(
        name="NEW MEMBER",
        value=(
            f"👤 {member_count}/{capacity} Members\n"
            f"➜ **{roblox_user} ({roblox_user})** joined [{clan_name}]\n\n"
            f"User: **{roblox_user} ({roblox_user})**"
        ),
        inline=False,
    )
    e.timestamp = _now()
    return e

def player_left(roblox_user: str, member_count: int,
                capacity: int, clan_name: str) -> discord.Embed:
    e = discord.Embed(title="📤 Player Left", color=C_RED)
    e.add_field(
        name="MEMBER LEFT",
        value=(
            f"👤 {member_count}/{capacity} Members\n"
            f"➜ **{roblox_user} ({roblox_user})** left [{clan_name}]\n\n"
            f"User: **{roblox_user} ({roblox_user})**"
        ),
        inline=False,
    )
    e.timestamp = _now()
    return e


# ─────────────────────────────────────────────────────────────────────────────
# 5.  Top Clanwar Contributors  (Screenshot 5)
#     "Top Clanwar Contributors for ZYXE"
#     Current Event: StarryBattle  |  Rank #96
#     Total Stars: 161.01k  |  Kick Cooldown …
#     1. Shudin617 (Chubbylals) ⭐ 6.66k
#     …
# ─────────────────────────────────────────────────────────────────────────────
def top_contributors(clan_data: dict, clan_name: str,
                     rank: int | None, battle_name: str = "ClanBattle") -> discord.Embed:
    battle       = ps99api.battle_sorted(clan_data)
    total_pts    = ps99api.total_points(clan_data)
    kick_cd      = clan_data.get("LastKickTimestamp")
    capacity     = clan_data.get("MemberCapacity", 75)
    member_count = len(clan_data.get("Members", []))

    e = discord.Embed(
        title=f"⭐ Top Clanwar Contributors for {clan_name}",
        color=C_GOLD,
    )

    kick_str = f"<t:{kick_cd}:R>" if kick_cd else "–"

    e.add_field(name="Current Event",   value=f"**{battle_name}**",    inline=True)
    e.add_field(name="Current Rank",    value=f"**#{rank}**" if rank else "**?**", inline=True)
    e.add_field(name="Total Stars",     value=f"**{fmt(total_pts)}** ⭐", inline=True)
    e.add_field(name="Kick Cooldown",   value=kick_str,                inline=True)
    e.add_field(name="Members",         value=f"**{member_count}/{capacity}**", inline=True)

    # Top 10 contributors
    lines = []
    for i, m in enumerate(battle[:10]):
        uid  = m.get("UserID", "?")
        pts  = m.get("Points", 0)
        name = f"UserID {uid}"
        lines.append(f"**{i+1}.** {name} ⭐ **{fmt(pts)}**")

    e.add_field(name="\u200b", value="\n".join(lines) or "*Keine Daten*", inline=False)
    e.set_footer(text=f"PS99 ClanWar Bot  •  {clan_name}")
    e.timestamp = _now()
    return e


# ─────────────────────────────────────────────────────────────────────────────
# 6.  Stündliches Snapshot-Update  (interner Timer)
# ─────────────────────────────────────────────────────────────────────────────
def hourly_update(clan_data: dict, clan_name: str,
                  rank: int | None, hrly: int, diff: int | None) -> discord.Embed:
    member_count = len(clan_data.get("Members", []))
    capacity     = clan_data.get("MemberCapacity", 75)
    battle       = ps99api.battle_sorted(clan_data)
    active       = sum(1 for m in battle if m.get("Points", 0) > 0)

    diff_str = ""
    if diff is not None:
        sign     = "+" if diff >= 0 else ""
        diff_str = f"{sign}{fmt(diff)}"

    e = discord.Embed(
        title=f"⏰ Stündliches Update  •  {clan_name}",
        color=C_BLUE,
    )
    e.add_field(name="Clan Rank",     value=f"**#{rank}**" if rank else "**?**", inline=True)
    e.add_field(name="Hourly Points", value=f"**{fmt(hrly)}**",                  inline=True)
    e.add_field(name="Δ Punkte/h",    value=f"**{diff_str}**" if diff_str else "**–**", inline=True)
    e.add_field(name="Players",       value=f"**{member_count}/{capacity}**",    inline=True)
    e.add_field(name="Active",        value=f"**{active}**",                     inline=True)
    e.add_field(name="Zero",          value=f"**{member_count - active}**",      inline=True)
    e.set_footer(text="PS99 ClanWar Bot  •  Stündlicher Snapshot")
    e.timestamp = _now()
    return e


# ─────────────────────────────────────────────────────────────────────────────
# 7.  Notification-Settings Übersicht
# ─────────────────────────────────────────────────────────────────────────────
def notif_overview(clan_name: str, notifs: dict) -> discord.Embed:
    def tog(k): return "✅ AN" if notifs.get(k, True) else "❌ AUS"
    e = discord.Embed(title=f"⚙️ Notifications  •  {clan_name}", color=C_BLUE)
    e.add_field(name="💎 Diamond Updates",   value=tog("diamond"),    inline=True)
    e.add_field(name="👤 Join / Leave",       value=tog("join_leave"), inline=True)
    e.add_field(name="📊 Ranking Changes",    value=tog("ranking"),    inline=True)
    e.add_field(name="⏰ Stündliche Updates", value=tog("hourly"),     inline=True)
    e.timestamp = _now()
    return e


# ─────────────────────────────────────────────────────────────────────────────
# 8.  Diamond / Gem Leaderboard
# ─────────────────────────────────────────────────────────────────────────────
def diamond_lb(clan_name: str, donations: list) -> discord.Embed:
    total  = sum(d["amount"] for d in donations)
    top    = sorted(donations, key=lambda x: x["amount"], reverse=True)[:10]
    lines  = [
        f"{rank_medal(i)} **{d['roblox_user']}** — 💎 {fmt(d['amount'])}"
        for i, d in enumerate(top)
    ] or ["*Noch keine Donations*"]

    e = discord.Embed(
        title=f"💎 Diamond Leaderboard  •  {clan_name}",
        description="\n".join(lines),
        color=C_PINK,
    )
    e.add_field(name="💰 Clan Diamonds gesamt", value=f"**{fmt(total)}**")
    e.timestamp = _now()
    return e
