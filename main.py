import asyncio
import base64
import os
import random
import re
import string
from aiohttp import web
import requests
import telebot
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup

# --- মূল কনফিগারেশন ---
BOT_TOKEN = "8932965102:AAHQAlbYoAd6A2jP9Rw6tycTC0QxYXd-MP0"
OWNER_AD_LINK = "https://omg10.com/4/11200499"

SERVER_URL = os.environ.get(
    "RENDER_EXTERNAL_URL", "https://adshare-link-engine.onrender.com"
)

bot = telebot.TeleBot(BOT_TOKEN)

# ইউজার সেশন, ডাটাবেজ ও লিংক সংখ্যা ট্র্যাকার
user_states = {}
user_link_counts = {}
link_database = {}


# --- ৬ অক্ষরের কাস্টম ইউনিক শর্ট কোড জেনারেটর ---
def generate_short_code():
  chars = string.ascii_letters + string.digits
  while True:
    code = "".join(random.choices(chars, k=6))
    if code not in link_database:
      return code


# --- মেনু বাটন তৈরি করার ফাংশন ---
def get_main_menu_markup():
  markup = InlineKeyboardMarkup()
  btn_clean = InlineKeyboardButton(
      "🔗 Clean Link Shortener", callback_data="mode_clean"
  )
  btn_custom = InlineKeyboardButton(
      "⚡ Custom Ad Link", callback_data="mode_custom"
  )
  markup.row(btn_clean)
  markup.row(btn_custom)
  return markup


def get_after_action_markup():
  markup = InlineKeyboardMarkup()
  btn_again = InlineKeyboardButton(
      "➕ Create Another Link", callback_data="mode_restart"
  )
  btn_menu = InlineKeyboardButton("🏠 Main Menu", callback_data="mode_home")
  markup.row(btn_again)
  markup.row(btn_menu)
  return markup


# --- স্টার্ট ও মেইন মেনু ---
@bot.message_handler(commands=["start", "help"])
def send_welcome(message):
  chat_id = message.chat.id
  user_states[chat_id] = {}  # Reset state

  welcome_text = (
      "🌐 **AdShare Global Link Tools**\n\n"
      "Choose an option below to format and optimize your links:\n\n"
      "• **Clean Link Shortener:** Convert any media/file link into a clean,"
      " fast-sharing link.\n"
      "• **Custom Ad Link:** Attach your own ad/monetization URL with your media"
      " link."
  )
  bot.send_message(
      chat_id,
      welcome_text,
      parse_mode="Markdown",
      reply_markup=get_main_menu_markup(),
  )


# --- বাটন ক্লিক হ্যান্ডলার ---
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
  chat_id = call.message.chat.id

  if call.data == "mode_clean":
    user_states[chat_id] = {"mode": "clean"}
    bot.edit_message_text(
        "🔗 **Clean Link Shortener Selected**\n\n"
        "Please send your **File / Image / Video URL** now:\n"
        "_(Example: `https://example.com/video.mp4`)_",
        chat_id=chat_id,
        message_id=call.message.message_id,
        parse_mode="Markdown",
    )

  elif call.data == "mode_custom":
    user_states[chat_id] = {"mode": "custom", "step": 1}
    bot.edit_message_text(
        "⚡ **Custom Ad Link Selected**\n\n"
        "📥 **Step 1 of 2:** Please send your **Main File / Media URL** first:",
        chat_id=chat_id,
        message_id=call.message.message_id,
        parse_mode="Markdown",
    )

  elif call.data in ["mode_restart", "mode_home"]:
    user_states[chat_id] = {}
    welcome_text = (
        "🌐 **AdShare Global Link Tools**\n\nChoose an option to continue:"
    )
    bot.send_message(
        chat_id,
        welcome_text,
        parse_mode="Markdown",
        reply_markup=get_main_menu_markup(),
    )


# --- টেক্সট মেসেজ প্রসেসিং ---
@bot.message_handler(func=lambda message: True)
def process_message(message):
  chat_id = message.chat.id
  text = message.text.strip()
  urls = re.findall(r"https?://[^\s]+", text)

  if not urls:
    bot.reply_to(
        message,
        "❌ **Invalid Link!** Please send a valid URL starting with `http://` or"
        " `https://`.",
        parse_mode="Markdown",
    )
    return

  input_url = urls[0]
  state = user_states.get(chat_id, {})

  # --- Clean Link Handler ---
  if state.get("mode") == "clean":
    code = generate_short_code()
    link_database[code] = {
        "mode": "clean",
        "dest_url": input_url,
        "chosen_ad": "none",
    }
    short_link = f"{SERVER_URL}/s/{code}"

    reply_msg = (
        "✅ **Your Clean Link is Ready!**\n\n"
        f"🔗 **Short Link:**\n`{short_link}`\n\n"
        f"🎯 **Destination:** `{input_url}`"
    )
    bot.reply_to(
        message,
        reply_msg,
        parse_mode="Markdown",
        reply_markup=get_after_action_markup(),
    )
    user_states[chat_id] = {}

  # --- Custom Ad Link Handler ---
  elif state.get("mode") == "custom":
    if state.get("step") == 1:
      user_states[chat_id]["dest_url"] = input_url
      user_states[chat_id]["step"] = 2
      bot.reply_to(
          message,
          "✅ **Destination URL Saved!**\n\n"
          "🎯 **Step 2 of 2:** Now send your **Monetization / Ad Direct"
          " Link**:",
          parse_mode="Markdown",
      )

    elif state.get("step") == 2:
      dest_url = state.get("dest_url")
      user_ad = input_url

      # ইউজার অনুযায়ী ১ম লিংক ইউজারের অ্যাড, পরবর্তী সব ওনারের (আপনার) অ্যাড
      current_count = user_link_counts.get(chat_id, 0) + 1
      user_link_counts[chat_id] = current_count

      if current_count == 1:
        selected_ad = user_ad
      else:
        selected_ad = OWNER_AD_LINK

      code = generate_short_code()
      link_database[code] = {
          "mode": "custom",
          "dest_url": dest_url,
          "chosen_ad": selected_ad,
      }
      short_link = f"{SERVER_URL}/s/{code}"

      reply_msg = (
          "🎉 **Your Custom Ad Link is Live!**\n\n"
          f"🔗 **Short Link:**\n`{short_link}`\n\n"
          "Share this link anywhere to direct users to your content and ad!"
      )
      bot.reply_to(
          message,
          reply_msg,
          parse_mode="Markdown",
          reply_markup=get_after_action_markup(),
      )
      user_states[chat_id] = {}

  else:
    bot.reply_to(
        message,
        "💡 Please choose an option from the menu below:",
        reply_markup=get_main_menu_markup(),
    )


# --- Web Redirect Engine (অটোমেটিক রিডাইরেক্ট) ---
routes = web.RouteTableDef()


@routes.get("/")
async def home(request):
  return web.Response(
      text="AdShare Global Engine Active!", content_type="text/plain"
  )


@routes.get("/s/{code}")
async def redirect_engine(request):
  code = request.match_info.get("code", "")

  if code not in link_database:
    return web.Response(
        text="Invalid or Expired Link!", status=404, content_type="text/plain"
    )

  data = link_database[code]
  mode = data["mode"]
  dest_url = data["dest_url"]
  chosen_ad = data["chosen_ad"]

  # ১. ক্লিন লিংকের ক্ষেত্রে সরাসরি ফাইলে রিডাইরেক্ট
  if mode == "clean":
    raise web.HTTPFound(location=dest_url)

  # ২. কাস্টম অ্যাড লিংক: কোনো বোতামে চাপ দেওয়া ছাড়াই অটোমেটিক ০.৫ সেকেন্ডে রিডাইরেক্ট
  html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Redirecting...</title>
        <style>
            body {{ font-family: sans-serif; background: #0f172a; color: #fff; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; text-align: center; }}
            .loader {{ border: 4px solid #1e293b; border-top: 4px solid #38bdf8; border-radius: 50%; width: 40px; height: 40px; animation: spin 1s linear infinite; margin: 0 auto 15px; }}
            @keyframes spin {{ 0% {{ transform: rotate(0deg); }} 100% {{ transform: rotate(360deg); }} }}
        </style>
    </head>
    <body>
        <div>
            <div class="loader"></div>
            <h3>Connecting to Destination...</h3>
        </div>
        <script>
            setTimeout(function() {{
                window.open('{chosen_ad}', '_blank');
                window.location.href = '{dest_url}';
            }}, 500);
        </script>
    </body>
    </html>
    """
  return web.Response(text=html_content, content_type="text/html")


# --- সার্ভার ২৪ ঘণ্টা চালু রাখার অটো-পিং ফাংশন (Keep-Alive) ---
async def keep_alive():
  while True:
    await asyncio.sleep(500)  # প্রতি ৮ মিনিটে অটো পিং পাঠাবে
    try:
      requests.get(SERVER_URL, timeout=5)
      print(">>> Keep-alive self-ping successful <<<")
    except Exception as e:
      print(f"Keep-alive ping error: {e}")


def run_bot():
  print(">>> Starting Bot... <<<")
  bot.remove_webhook()
  bot.infinity_polling()


async def start_background_tasks(app):
  asyncio.create_task(asyncio.to_thread(run_bot))
  asyncio.create_task(keep_alive())  # কিপ-এলাইভ শুরু


app = web.Application()
app.add_routes(routes)
app.on_startup.append(start_background_tasks)

if __name__ == "__main__":
  port = int(os.environ.get("PORT", 8080))
  web.run_app(app, host="0.0.0.0", port=port)
