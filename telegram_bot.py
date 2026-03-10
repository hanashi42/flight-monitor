import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, ROUTES, THRESHOLDS
from db import get_cheapest_per_route, get_price_history


def get_app():
    return Application.builder().token(TELEGRAM_BOT_TOKEN).build()


async def send_message(app, text, parse_mode="HTML"):
    await app.bot.send_message(
        chat_id=TELEGRAM_CHAT_ID, text=text, parse_mode=parse_mode,
        disable_web_page_preview=True,
    )


def format_alert(flight, route_label, level_info, prev_price=None):
    diff = ""
    if prev_price is not None:
        change = flight["price"] - prev_price
        arrow = "↓" if change < 0 else "↑"
        diff = f" ({arrow} MYR {abs(change):.0f})"

    stops_text = "直飞" if flight["stops"] == 0 else f"{flight['stops']}次转机"
    return (
        f"{level_info['emoji']} <b>{level_info['label']}！{route_label}</b>\n"
        f"📅 {flight['fly_date']}\n"
        f"✈️ {flight['airline']} ({stops_text})\n"
        f"💰 MYR {flight['price']:.0f}{diff}\n"
        f"🔗 <a href=\"{flight['deep_link']}\">订票链接</a>"
    )


def format_summary(cheapest_list):
    if not cheapest_list:
        return "📊 <b>每日价格汇总</b>\n\n暂无数据"
    lines = ["📊 <b>每日价格汇总</b>\n"]
    for item in cheapest_list:
        stops_text = "直飞" if item["stops"] == 0 else f"{item['stops']}转"
        lines.append(
            f"<b>{item['route']}</b>: MYR {item['price']:.0f} "
            f"({item['fly_date']}, {item['airline']}, {stops_text})"
        )
    return "\n".join(lines)


async def cmd_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ 正在查询最新价格...")
    from monitor import run_scan
    await run_scan(context)
    cheapest = get_cheapest_per_route()
    await update.message.reply_text(format_summary(cheapest), parse_mode="HTML")


async def cmd_routes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lines = ["📋 <b>监控路线</b>\n"]
    for r in ROUTES:
        lines.append(f"• {r['label']}")
    lines.append("\n<b>价格阈值</b>")
    for t in THRESHOLDS:
        lines.append(f"{t['emoji']} MYR {t['max_price']} — {t['label']}")
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


async def cmd_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args or len(args) < 2:
        await update.message.reply_text("用法: /history JHB KIX")
        return
    route = f"{args[0].upper()}-{args[1].upper()}"
    history = get_price_history(route)
    if not history:
        await update.message.reply_text(f"暂无 {route} 的历史数据")
        return
    lines = [f"📈 <b>{route} 近30天最低价</b>\n"]
    for h in history[-15:]:
        lines.append(f"{h['fly_date']}: MYR {h['min_price']:.0f}")
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


def setup_handlers(app):
    app.add_handler(CommandHandler("check", cmd_check))
    app.add_handler(CommandHandler("routes", cmd_routes))
    app.add_handler(CommandHandler("history", cmd_history))
    app.add_handler(CommandHandler("start", cmd_routes))
