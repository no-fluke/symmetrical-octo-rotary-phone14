import os
import logging
import requests
import asyncio
import threading
import time
import re
from datetime import datetime
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# Initialize Flask app for keeping Render awake
app = Flask(__name__)

@app.route('/')
def home():
    return "🤖 Telegram Course Bot is running!"

@app.route('/health')
def health():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

def run_flask():
    app.run(host='0.0.0.0', port=5000)

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class CompleteCourseBot:
    def __init__(self, token):
        self.token = token
        self.application = Application.builder().token(token).build()
        self.api_base_url = "https://backend.multistreaming.site/api"
        self.user_sessions = {}
        self.setup_handlers()
        
    def setup_handlers(self):
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("batches", self.batches_command))
        self.application.add_handler(CommandHandler("get_course", self.get_course_command))
        self.application.add_handler(CommandHandler("quality", self.quality_command))
        self.application.add_handler(CallbackQueryHandler(self.handle_callback))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text))
        
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        
        # Initialize user session
        if user_id not in self.user_sessions:
            self.user_sessions[user_id] = {
                'preferred_quality': '720p',
                'selected_course': None
            }
        
        welcome_text = """
🤖 **Complete Course Data Bot**

I can fetch complete course data from APIs including:

• **Video Lectures** with quality preference
• **Class PDFs** (study materials)
• **Practice Sheets** (test papers)
• Organized by topics and classes

**Commands:**
/start - Show this message
/help - Get detailed instructions
/batches - Show available courses
/get_course - Generate complete course file
/quality - Set video quality preference

**Current Quality:** 720p (use /quality to change)
        """
        await update.message.reply_text(welcome_text, parse_mode='Markdown')
        
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        help_text = """
📖 **Complete Help Guide**

**How to use:**
1. `/batches` - See all available courses
2. Select a course from the list
3. `/get_course` - Generate complete data file
4. Receive a .txt file with everything organized

**What's included in the file:**
✅ **VIDEO LECTURES** - Class videos in your preferred quality
✅ **CLASS PDFs** - Study materials for each class
✅ **PRACTICE SHEETS** - Test papers organized by topic
✅ **TEACHER INFORMATION** - Who taught each class

**Video Quality Options:**
- 240p (Lowest quality, smallest file)
- 360p (Good for mobile data)
- 480p (Standard quality)
- 720p (HD - Recommended)
- 1080p (Full HD - if available)

**Note:** The bot fetches real-time data from the APIs.
        """
        await update.message.reply_text(help_text, parse_mode='Markdown')
        
    async def batches_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show available courses"""
        await update.message.reply_text("📚 Fetching available courses...")
        
        try:
            # These are example courses - you should replace with actual API call
            courses = [
                {
                    "id": "maths_special",
                    "title": "Mathematics Special Batch",
                    "description": "Complete Mathematics course with videos and PDFs"
                },
                {
                    "id": "science_batch", 
                    "title": "Science Foundation",
                    "description": "Physics, Chemistry, Biology complete course"
                },
                {
                    "id": "english_batch",
                    "title": "English Master Course",
                    "description": "Complete English grammar and comprehension"
                }
            ]
            
            if not courses:
                await update.message.reply_text("❌ No courses found.")
                return
            
            # Store in context
            context.user_data['courses'] = courses
            
            # Create detailed keyboard
            keyboard = []
            for i, course in enumerate(courses, 1):
                button_text = f"{i}. {course['title'][:40]}..."
                if len(course['title']) > 40:
                    button_text = f"{i}. {course['title'][:37]}..."
                keyboard.append([InlineKeyboardButton(button_text, callback_data=f"select_course_{i-1}")])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                "📚 **Available Courses:**\n\n"
                "Select a course to generate its complete data file:\n\n"
                "1. **Mathematics Special Batch** - Complete math course\n"
                "2. **Science Foundation** - Physics, Chemistry, Biology\n"
                "3. **English Master Course** - English complete syllabus\n\n"
                "Each file will include:\n"
                "• Video lecture links\n"
                "• Class PDF materials\n"
                "• Practice sheets\n"
                "• Organized by topics",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Error in batches command: {e}")
            await update.message.reply_text("❌ Error fetching courses. Please try again.")
            
    async def get_course_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Generate complete course data file"""
        user_id = update.effective_user.id
        
        if user_id not in self.user_sessions:
            await update.message.reply_text("❌ Please use /start first.")
            return
            
        session = self.user_sessions[user_id]
        
        if not session.get('selected_course'):
            await update.message.reply_text(
                "❌ Please select a course first using /batches\n\n"
                "Then click on a course from the list."
            )
            return
            
        course_id = session['selected_course']['id']
        course_title = session['selected_course']['title']
        preferred_quality = session['preferred_quality']
        
        await update.message.reply_text(
            f"📡 **Generating Data for:** {course_title}\n"
            f"🎥 **Video Quality:** {preferred_quality.upper()}\n"
            f"⏳ **Please wait...**"
        )
        
        try:
            # For demonstration, we'll use the example data format
            # In production, you would fetch from your API
            text_content = await self.generate_example_format_file(course_title, preferred_quality)
            
            # Count entries
            total_classes = text_content.count("Class-")
            total_pdfs = text_content.count(".pdf")
            total_videos = text_content.count(".mp4")
            
            # Create filename
            safe_title = ''.join(c for c in course_title if c.isalnum() or c in (' ', '-', '_')).rstrip()
            filename = f"{safe_title.replace(' ', '_')}_Complete_{datetime.now().strftime('%Y%m%d')}.txt"
            
            # Send file with caption including counts
            caption = (
                f"✅ **{course_title}**\n\n"
                f"📊 **Summary:**\n"
                f"• Total Classes: {total_classes}\n"
                f"• Video Lectures: {total_videos}\n"
                f"• PDF Materials: {total_pdfs}\n"
                f"• Quality: {preferred_quality.upper()}\n\n"
                f"📅 Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            )
            
            await update.message.reply_document(
                document=text_content.encode('utf-8'),
                filename=filename,
                caption=caption,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Error generating file: {e}")
            await update.message.reply_text("❌ Error generating course file. Please try again.")
    
    async def generate_example_format_file(self, course_title, quality):
        """Generate file in the same format as the example"""
        lines = []
        
        # Example data in the same format as your provided file
        # This is just an example - you should replace with actual data from your API
        
        # Class 1 examples
        lines.append("Class-01 || Class-01 || Number System | Gagan sir | Gagan Sir | Advance | (GAGAN SIR): https://selectionwayrecordedmp4.hranker.com/561/68e3669f10c7d671132e56ab/mp4/output_720p_720p.mp4")
        lines.append("NUMBER SYSTEM CLASS -1 BOARD (GAGAN SIR): https://selectionwayserver.hranker.com/pdfs/files/1760480325844-1759813735845-Number_System_Class-1___Board_pdf__.pdf")
        lines.append("")
        lines.append("Class-01 || Class -01  || Calculation and Simplification | Gagan sir | Gagan Sir | Advance | (GAGAN SIR): https://selectionwayrecordedmp4.hranker.com/561/6912d529932c0deb70be72fc/mp4/1112_720p.mp4")
        lines.append("calculation 1 (GAGAN SIR): https://selectionwayserver.hranker.com/pdfs/files/calculation 1.pdf")
        lines.append("")
        
        # Class 2 examples
        lines.append("Class-02 || Class-02 || Number System | Gagan sir | Gagan Sir | Advance | (GAGAN SIR): https://selectionwayrecordedmp4.hranker.com/561/68e3f88210c7d6711353db5c/mp4/output_720p_720p.mp4")
        lines.append("NUMBER SYSTEM CLASS -2 BOARD (GAGAN SIR): https://selectionwayserver.hranker.com/pdfs/files/1760480038092-1759826889367-NUMBER_SYSTEM_CLASS_-2_BOARD__PDF_.pdf")
        lines.append("")
        
        # Class 3 examples
        lines.append("Class-03 || Class-03 || Number System | Gagan sir | Gagan Sir | Advance | (GAGAN SIR): https://selectionwayrecordedmp4.hranker.com/561/68e4f80e290f277f35542716/mp4/output_720p_720p.mp4")
        lines.append("NUMBER SYSTEM CLASS -3 BOARD (GAGAN SIR): https://selectionwayserver.hranker.com/pdfs/files/1760479373162-1760010540863-Number_System_Class_3_bord_pdf_(1).pdf")
        lines.append("")
        
        # Add more classes here based on your actual data
        # You would fetch this from your API
        
        return '\n'.join(lines)
    
    async def fetch_course_data_from_api(self, course_id, quality):
        """Fetch actual data from your API"""
        try:
            # This is where you would make the actual API call
            # For now, return example data
            return await self.generate_example_format_file("Example Course", quality)
        except Exception as e:
            logger.error(f"Error fetching from API: {e}")
            return None
            
    async def quality_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Set video quality preference"""
        user_id = update.effective_user.id
        
        if user_id not in self.user_sessions:
            self.user_sessions[user_id] = {
                'preferred_quality': '720p',
                'selected_course': None
            }
        
        keyboard = [
            [
                InlineKeyboardButton("240p", callback_data="quality_240p"),
                InlineKeyboardButton("360p", callback_data="quality_360p"),
            ],
            [
                InlineKeyboardButton("480p", callback_data="quality_480p"),
                InlineKeyboardButton("720p (Recommended)", callback_data="quality_720p"),
            ],
            [
                InlineKeyboardButton("1080p", callback_data="quality_1080p"),
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        current_quality = self.user_sessions[user_id]['preferred_quality']
        
        await update.message.reply_text(
            f"🎥 **Select video quality:**\n\n"
            f"**Current:** {current_quality.upper()}\n\n"
            f"This quality will be used for video links.",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle callback queries"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        
        if query.data.startswith('select_course_'):
            # Handle course selection
            try:
                index = int(query.data.replace('select_course_', ''))
                courses = context.user_data.get('courses', [])
                
                if index < len(courses):
                    course = courses[index]
                    
                    if user_id not in self.user_sessions:
                        self.user_sessions[user_id] = {
                            'preferred_quality': '720p',
                            'selected_course': None
                        }
                    
                    self.user_sessions[user_id]['selected_course'] = course
                    
                    await query.edit_message_text(
                        f"✅ **Course Selected:** {course['title']}\n\n"
                        f"📖 Description: {course.get('description', 'Complete course with videos and PDFs')}\n\n"
                        f"Now use `/get_course` to generate the complete data file.",
                        parse_mode='Markdown'
                    )
                else:
                    await query.edit_message_text("❌ Invalid course selection.")
                    
            except Exception as e:
                logger.error(f"Error selecting course: {e}")
                await query.edit_message_text("❌ Error selecting course.")
                
        elif query.data.startswith('quality_'):
            # Handle quality selection
            quality = query.data.replace('quality_', '')
            
            if user_id not in self.user_sessions:
                self.user_sessions[user_id] = {
                    'preferred_quality': quality,
                    'selected_course': None
                }
            else:
                self.user_sessions[user_id]['preferred_quality'] = quality
            
            quality_descriptions = {
                '240p': 'Mobile Data - Lowest quality',
                '360p': 'Standard - Good for basic viewing',
                '480p': 'Good Quality - Balanced option',
                '720p': 'HD - Recommended for most users',
                '1080p': 'Full HD - Best quality if available'
            }
            
            description = quality_descriptions.get(quality, '')
            
            await query.edit_message_text(
                f"✅ **Video quality set to:** {quality.upper()}\n\n"
                f"{description}\n\n"
                f"This setting will be used for all video links.",
                parse_mode='Markdown'
            )
            
    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text messages"""
        text = update.message.text.lower()
        
        if text in ['/cancel', 'cancel', 'stop']:
            user_id = update.effective_user.id
            if user_id in self.user_sessions:
                self.user_sessions[user_id]['selected_course'] = None
                await update.message.reply_text(
                    "✅ **Operation cancelled.**\n\n"
                    "Course selection has been cleared.\n"
                    "Use `/batches` to select a new course.",
                    parse_mode='Markdown'
                )
            else:
                await update.message.reply_text("No active operation to cancel.")
        elif text in ['status', 'info']:
            user_id = update.effective_user.id
            if user_id in self.user_sessions:
                session = self.user_sessions[user_id]
                status_text = f"📊 **Your Status:**\n\n"
                status_text += f"🎥 **Video Quality:** {session['preferred_quality'].upper()}\n"
                if session['selected_course']:
                    status_text += f"📚 **Selected Course:** {session['selected_course']['title']}\n"
                else:
                    status_text += "📚 **Selected Course:** None (use /batches)\n"
                await update.message.reply_text(status_text, parse_mode='Markdown')
            else:
                await update.message.reply_text("Please use /start first.")
        else:
            await update.message.reply_text(
                "🤖 **Available Commands:**\n\n"
                "`/start` - Welcome message and setup\n"
                "`/help` - Detailed instructions\n"
                "`/batches` - Show available courses\n"
                "`/get_course` - Generate complete course file\n"
                "`/quality` - Set video quality preference\n"
                "`status` - Check your current settings\n"
                "`cancel` - Clear current selection\n\n"
                "**Quick Start:**\n"
                "1. Use `/batches` to see courses\n"
                "2. Click on a course\n"
                "3. Use `/get_course` to generate file",
                parse_mode='Markdown'
            )

def keep_alive():
    """Keep-alive mechanism"""
    def ping_server():
        while True:
            try:
                logger.info("Bot is alive and running...")
                time.sleep(300)
            except Exception as e:
                logger.error(f"Keep-alive error: {e}")
                
    thread = threading.Thread(target=ping_server, daemon=True)
    thread.start()

def main():
    # Load environment variables
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN environment variable is required")
    
    # Start Flask server in a separate thread
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    # Start keep-alive mechanism
    keep_alive()
    
    # Initialize and start bot
    bot = CompleteCourseBot(token)
    
    logger.info("Bot is starting...")
    bot.application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
