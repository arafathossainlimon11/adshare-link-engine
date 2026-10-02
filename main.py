import asyncio
import base64
import os
import re
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

# ইউজার সেশন ও লিংক সংখ্যা ট্র্যাকার (User ID ভিত্তিক)
user_states = {}
user_link_counts = {}


# --- Base64 এনকোড ও ডিকোড হেল্পার ---
def encode_data(mode, chosen_ad, dest_url):
  raw_str = f"{mode}|||{chosen_ad}|||{dest_url}"
  return base64.urlsafe_b64encode(raw_str.encode()).decode()


def decode_data(encoded_str):
  try:
    decoded_bytes = base64.urlsafe_b64decode(encoded_str.encode())
    parts = decoded_bytes.decode().split("|||")
    if len(parts) == 3:
      return parts[0], parts[1], parts[2]
  except Exception:
    pass
  return None, None, None


# --- TinyURL অটোমেটিক শর্টনার ---
def make_tiny_url(long_url):
  try:
    api_url = f"https://tinyurl.com/api-create.php?url={long_url}"
    res = requests.get(api_url, timeout=5)
    if res.status_code == 200 and res.text.startswith("http"):
      return res.text.strip()
  except Exception as e:
    print(f"TinyURL error: {e}")
  return long_url


# --- স্টার্ট ও মেইন মেনু ---
@bot.message_handler(commands=["start", "help"])
def send_welcome(message):
  chat_id = message.chat.id
  user_states[chat_id] = {}  # Reset state

  markup = InlineKeyboardMarkup()
  btn_clean = InlineKeyboardButton(
      "🔗 Clean Link Shortener", callback_data="mode_clean"
  )
  btn_custom = InlineKeyboardButton(
      "⚡ Custom Ad Link", callback_data="mode_custom"
  )

  markup.row(btn_clean)
  markup.row(btn_custom)

  welcome_text = (
      "🌐 **AdShare Global Link Tools**\n\n"
      "Choose an option below to format and optimize your links:\n\n"
      "• **Clean Link Shortener:** Convert any media/file link into a clean,"
      " fast-sharing link.\n"
      "• **Custom Ad Link:** Attach your own ad/monetization URL with your media"
      " link."
  )
  bot.send_message(
      chat_id, welcome_text, parse_mode="Markdown", reply_markup=markup
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
    encoded = encode_data("clean", "none", input_url)
    raw_link = f"{SERVER_URL}/go?data={encoded}"
    short_link = make_tiny_url(raw_link)

    reply_msg = (
        "✅ **Your Clean Link is Ready!**\n\n"
        f"🔗 **Short Link:**\n`{short_link}`\n\n"
        f"🎯 **Destination:** `{input_url}`"
    )
    bot.reply_to(message, reply_msg, parse_mode="Markdown")
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

      # ইউজার অনুযায়ী লিংক গণনার লজিক
      current_count = user_link_counts.get(chat_id, 0) + 1
      user_link_counts[chat_id] = current_count

      # ১ম লিংকে ইউজারের অ্যাড, ২য়/৩য়/৪র্থ লিংকে ওনারের (আপনার) অ্যাড
      if current_count == 1:
        selected_ad = user_ad
      else:
        selected_ad = OWNER_AD_LINK

      encoded = encode_data("custom", selected_ad, dest_url)
      raw_link = f"{SERVER_URL}/go?data={encoded}"
      short_link = make_tiny_url(raw_link)

      reply_msg = (
          "🎉 **Your Custom Ad Link is Live!**\n\n"
          f"🔗 **Short Link:**\n`{short_link}`\n\n"
          "Share this link anywhere to direct users to your content and ad!"
      )
      bot.reply_to(message, reply_msg, parse_mode="Markdown")
      user_states[chat_id] = {}

  else:
    bot.reply_to(
        message, "💡 Please select an option first by clicking /start"
    )


# --- Web Redirect Engine (সরাসরি ৩০২ ডাইরেক্ট রিডাইরেক্ট, কোনো ওয়েব পেজ নেই) ---
routes = web.RouteTableDef()


@routes.get("/")
async def home(request):
  return web.Response(
      text="AdShare Global Engine Active!", content_type="text/plain"
  )


@routes.get("/go")
async def redirect_engine(request):
  data = request.query.get("data", "")
  mode, chosen_ad, dest_url = decode_data(data)

  if not dest_url:
    return web.Response(text="Invalid or Expired Link!", status=400)

  # ১. ক্লিন লিংকের ক্ষেত্রে সরাসরি মূল ফাইলে রিডাইরেক্ট
  if mode == "clean":
    raise web.HTTPFound(location=dest_url)

  # ২. কাস্টম অ্যাড লিংকের ক্ষেত্রে সরাসরি ৩০২ ডাইরেক্ট রিডাইরেক্ট (কোনো মধ্যবর্তী পেজ ছাড়াই)
  raise web.HTTPFound(location=chosen_ad)


def run_bot():
  print(">>> Starting Bot... <<<")
  bot.remove_webhook()
  bot.infinity_polling()


async def start_background_tasks(app):
  asyncio.create_task(asyncio.to_thread(run_bot))


app = web.Application()
app.add_routes(routes)
app.on_startup.append(start_background_tasks)

if __name__ == "__main__":
  port = int(os.environ.get("PORT", 8080))
  web.run_app(app, host="0.0.0.0", port=port)
