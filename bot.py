import os
import logging
import asyncio
import threading
import sys
import tempfile
import random
from http.server import BaseHTTPRequestHandler, HTTPServer
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    ConversationHandler,
    filters,
)
import openai

# --- CONFIGURATION ---
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "").strip()
PORT = int(os.environ.get("PORT", 8080))

if not TOKEN:
    print("ERROR: TELEGRAM_BOT_TOKEN is not set!")
    sys.exit(1)

# Initialize OpenAI client
client = openai.OpenAI(api_key=OPENAI_API_KEY)

# States
MENU_STATE, VOICE_STATE = range(2)

# --- FRUIT DATA ---
FRUITS = [
    "APPLE", "BANANA", "PINEAPPLE", "STRAWBERRY", "POMEGRANATE", 
    "BLUEBERRY", "AVOCADO", "WATERMELON", "DRAGONFRUIT", "KIWI",
    "MANGO", "ORAGE", "PAPAYA", "RASPBERRY", "BLACKBERRY"
]

# Logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# --- UI HELPERS ---
def get_main_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("🍎 Start Fruit Challenge", callback_data="start_voice")],
        [InlineKeyboardButton("❌ Exit", callback_data="exit_game")]
    ]
    return InlineKeyboardMarkup(keyboard)

# --- BOT LOGIC ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🍎 *Fruit Pronunciation Pro* 🎙️\n\n"
        "Can you say the names of these fruits perfectly?\n"
        "Choose an option below to begin!"
    )
    reply_markup = get_main_menu_keyboard()
    
    if update.message:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    return MENU_STATE

async def start_voice_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    target_fruit = random.choice(FRUITS)
    context.user_data['target_word'] = target_fruit
    
    text = (
        "🎙️ *Pronunciation Challenge*\n\n"
        f"Your fruit is: *{target_fruit}*\n\n"
        "Please send a *Voice Message* clearly saying this fruit's name!"
    )
    await query.edit_message_text(text, parse_mode='Markdown')
    return VOICE_STATE

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target = context.user_data.get('target_word')
    if not target:
        return await start(update, context)

    loading_msg = await update.message.reply_text("👂 Listening closely to your accent...")
    
    try:
        # 1. Download voice file
        voice_file = await update.message.voice.get_file()
        
        with tempfile.NamedTemporaryFile(suffix='.ogg', delete=False) as tf:
            temp_path = tf.name
        
        await voice_file.download_to_drive(temp_path)

        # 2. Transcribe with OpenAI Whisper
        with open(temp_path, "rb") as audio_file:
            transcript = client.audio.transcriptions.create(
                model="whisper-1", 
                file=audio_file
            )
        
        os.remove(temp_path)
        # Clean up the spoken text for better matching
        spoken_text = transcript.text.upper().strip().replace(".", "").replace("!", "").replace("?", "")

        # 3. Compare and Score
        if target in spoken_text:
            result_text = (
                f"✅ *PERFECT PRONUNCIATION!* 🏆\n\n"
                f"I heard: `{spoken_text}`\n"
                f"Score: 100/100"
            )
        else:
            result_text = (
                f"❌ *NOT QUITE!* 🫤\n\n"
                f"I heard: `{spoken_text}`\n"
                f"Expected: `{target}`\n\n"
                "Give it another shot!"
            )

        await loading_msg.edit_text(result_text, parse_mode='Markdown')
        await update.message.reply_text("Ready for the next fruit?", reply_markup=get_main_menu_keyboard())
        
    except Exception as e:
        logger.error(f"Voice Error: {e}")
        await loading_msg.edit_text("⚠️ Sorry, I couldn't process that audio. Please ensure your OpenAI API key is valid.")
    
    return MENU_STATE

async def exit_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Thanks for playing Fruit Pronunciation! Send /start anytime to play again. 🍉")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Game cancelled. Send /start to begin again.")
    return ConversationHandler.END

# --- RENDER HEALTH CHECK ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running")
    def log_message(self, format, *args): return

def run_health_check():
    httpd = HTTPServer(('0.0.0.0', PORT), HealthCheckHandler)
    httpd.serve_forever()

# --- MAIN ---
async def main():
    # Start health check thread for Render
    threading.Thread(target=run_health_check, daemon=True).start()
    
    application = ApplicationBuilder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            MENU_STATE: [
                CallbackQueryHandler(start_voice_game, pattern="^start_voice$"),
                CallbackQueryHandler(exit_game, pattern="^exit_game$"),
            ],
            VOICE_STATE: [MessageHandler(filters.VOICE, handle_voice)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        per_message=False 
    )

    application.add_handler(conv_handler)
    
    async with application:
        await application.initialize()
        await application.start()
        logger.info("Fruit Bot is polling...")
        await application.updater.start_polling()
        while True: await asyncio.sleep(1)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped.")
