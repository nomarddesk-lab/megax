import os
import logging
import asyncio
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
)

# --- CONFIGURATION ---
# Get your token from @BotFather
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
PORT = int(os.environ.get("PORT", 8080))

# States for ConversationHandler
QUIZ = 1

# --- QUIZ DATA ---
# Content is tailored to be professional and educational (Telegram Ad Policy compliant)
QUIZ_QUESTIONS = [
    {
        "question": "What does 'SEO' stand for in digital marketing?",
        "options": ["Social Engine Order", "Search Engine Optimization", "System Entry Operation", "Sales Efficiency Office"],
        "correct": 1,
        "explanation": "SEO is the practice of orienting your website to rank higher on a search engine results page."
    },
    {
        "question": "Which metric measures the percentage of users who leave a site after viewing only one page?",
        "options": ["Conversion Rate", "Click Rate", "Bounce Rate", "Retention Rate"],
        "correct": 2,
        "explanation": "Bounce Rate helps marketers understand if their landing page is relevant to the audience."
    },
    {
        "question": "What is 'CTR' a metric for?",
        "options": ["Click-Through Rate", "Customer Total Reach", "Content Text Ratio", "Cost To Return"],
        "correct": 0,
        "explanation": "CTR is the ratio of users who click on a specific link to the number of total users who view a page or ad."
    },
    {
        "question": "In advertising, what does 'CTA' stand for?",
        "options": ["Customer Trial Area", "Cost To Acquire", "Call To Action", "Client Target Analysis"],
        "correct": 2,
        "explanation": "A Call To Action is an instruction to the audience designed to provoke an immediate response."
    },
    {
        "question": "What is a 'KPI' used for?",
        "options": ["Key Performance Indicator", "Knowledge Process Integration", "Keyword Personal Index", "Key Point Installation"],
        "correct": 0,
        "explanation": "KPIs are quantifiable measures used to evaluate the success of an organization or activity."
    }
]

# Logging setup
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- BOT LOGIC ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Initial greeting and start button."""
    user = update.effective_user
    welcome_text = (
        f"Hello {user.first_name}! 🎓\n\n"
        "Welcome to the Digital Marketing English Quiz.\n"
        "Test your knowledge of professional terminology with 5 quick questions."
    )
    
    keyboard = [[InlineKeyboardButton("Start Quiz", callback_data="start_quiz")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup)
    return QUIZ

async def handle_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the quiz flow: asking questions and checking answers."""
    query = update.callback_query
    await query.answer()
    
    # Initialize or update state
    if 'current_q' not in context.user_data or query.data == "start_quiz":
        context.user_data['current_q'] = 0
        context.user_data['score'] = 0

    current_idx = context.user_data['current_q']

    # Process previous answer if applicable
    if query.data.startswith("ans_"):
        selected_idx = int(query.data.split("_")[1])
        prev_q = QUIZ_QUESTIONS[current_idx]
        
        if selected_idx == prev_q['correct']:
            context.user_data['score'] += 1
            feedback = "Correct! ✅"
        else:
            feedback = f"Incorrect. ❌ The right answer was: {prev_q['options'][prev_q['correct']]}"
        
        await query.edit_message_text(f"{feedback}\n\n{prev_q['explanation']}")
        await asyncio.sleep(2) # Brief pause for reading
        
        current_idx += 1
        context.user_data['current_q'] = current_idx

    # End of Quiz
    if current_idx >= len(QUIZ_QUESTIONS):
        score = context.user_data['score']
        finish_text = (
            f"You finished the quiz! 🏆\n"
            f"Your Score: {score}/{len(QUIZ_QUESTIONS)}\n\n"
            "Great effort. You have completed this week's Digital Marketing curriculum.\n\n"
            "📅 Please come back next week to learn more about advanced strategies and test your skills again!"
        )
        await query.message.reply_text(finish_text)
        return ConversationHandler.END

    # Ask Next Question
    q = QUIZ_QUESTIONS[current_idx]
    keyboard = []
    for i, opt in enumerate(q['options']):
        keyboard.append([InlineKeyboardButton(opt, callback_data=f"ans_{i}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.reply_text(
        f"Question {current_idx + 1}/{len(QUIZ_QUESTIONS)}:\n\n{q['question']}",
        reply_markup=reply_markup
    )
    return QUIZ

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Quiz cancelled. Send /start to try again whenever you're ready.")
    return ConversationHandler.END

# --- RENDER HEALTH CHECK ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running")

def run_health_check():
    server = HTTPServer(('0.0.0.0', PORT), HealthCheckHandler)
    server.serve_forever()

# --- MAIN ENTRY POINT ---
if __name__ == '__main__':
    # Start health check in a separate thread so Render doesn't shut down the service
    threading.Thread(target=run_health_check, daemon=True).start()

    # Build the Application
    application = ApplicationBuilder().token(TOKEN).build()

    # Add Conversation Handler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            QUIZ: [CallbackQueryHandler(handle_quiz)]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    application.add_handler(conv_handler)

    print(f"Bot started on port {PORT}...")
    application.run_polling()
