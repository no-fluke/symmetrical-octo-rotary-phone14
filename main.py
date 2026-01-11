import os
import logging
import json
import requests
import asyncio
import threading
import time
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

class CourseDataBot:
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
🤖 **Course Data Bot**

I can fetch course data from APIs and generate formatted text files with:

• Video lecture links with quality preference
• PDF materials and practice sheets
• Organized by topics and classes
• Teacher information

**Commands:**
/start - Show this message
/help - Get help information
/batches - Show available courses
/get_course - Generate course data file
/quality - Set video quality preference

**Current Quality:** 720p (use /quality to change)
        """
        await update.message.reply_text(welcome_text, parse_mode='Markdown')
        
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        help_text = """
📖 **Help Guide**

**How to use:**
1. Use `/batches` to see available courses
2. Select a course from the list
3. Use `/get_course` to generate the text file
4. Receive a .txt file with all organized links

**File Format:**
- Videos organized by topic and class
- PDF materials listed below each video
- Practice sheets included
- Teacher names and class titles

**Quality Settings:**
Use `/quality` to set preferred video quality:
- 240p, 360p, 480p, 720p, 1080p

**Note:** The bot uses API endpoints to fetch real-time course data.
        """
        await update.message.reply_text(help_text, parse_mode='Markdown')
        
    async def batches_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show available courses"""
        await update.message.reply_text("📚 Fetching available courses...")
        
        try:
            # Example course IDs - in production, you'd fetch these from an API
            courses = [
                {"id": "68e7b6e6aaf4383d1192dfb6", "title": "RRB Group-D Target batch"},
                {"id": "68dbdf3a63a1698bf4194576", "title": "Science Complete Course"},
                # Add more courses as needed
            ]
            
            if not courses:
                await update.message.reply_text("❌ No courses found.")
                return
            
            # Store in context
            context.user_data['courses'] = courses
            
            # Create keyboard
            keyboard = []
            for i, course in enumerate(courses, 1):
                keyboard.append([
                    InlineKeyboardButton(
                        f"{i}. {course['title'][:50]}...",
                        callback_data=f"select_course_{i-1}"
                    )
                ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                "📚 **Available Courses:**\n\nSelect a course to generate its data file:",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Error fetching batches: {e}")
            await update.message.reply_text("❌ Error fetching courses. Please try again.")
            
    async def get_course_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Generate course data file"""
        user_id = update.effective_user.id
        
        if user_id not in self.user_sessions:
            await update.message.reply_text("❌ Please use /start first.")
            return
            
        session = self.user_sessions[user_id]
        
        if not session.get('selected_course'):
            await update.message.reply_text("❌ Please select a course first using /batches")
            return
            
        course_id = session['selected_course']['id']
        course_title = session['selected_course']['title']
        preferred_quality = session['preferred_quality']
        
        await update.message.reply_text(
            f"📡 Fetching data for: {course_title}\n"
            f"🎥 Quality: {preferred_quality}\n"
            f"⏳ This may take a moment..."
        )
        
        try:
            # Fetch course data from API
            api_url = f"{self.api_base_url}/courses/{course_id}/classes?populate=full"
            response = requests.get(api_url, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get('state') != 200:
                error_msg = data.get('msg', 'Unknown error')
                await update.message.reply_text(f"❌ API Error: {error_msg}")
                return
                
            # Generate text file
            text_content = self.generate_course_file(data, preferred_quality)
            
            # Create filename
            filename = f"{course_title.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.txt"
            
            # Send file
            await update.message.reply_document(
                document=text_content.encode('utf-8'),
                filename=filename,
                caption=f"✅ {course_title}\nGenerated with {preferred_quality} quality"
            )
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error: {e}")
            await update.message.reply_text("❌ Network error. Please try again.")
        except Exception as e:
            logger.error(f"Error generating file: {e}")
            await update.message.reply_text("❌ Error generating course file. Please try again.")
            
    def generate_course_file(self, api_data, preferred_quality):
        """Generate formatted text file from API data"""
        lines = []
        
        # Header
        lines.append("=" * 80)
        lines.append("COURSE DATA - GENERATED BY TELEGRAM BOT")
        lines.append("=" * 80)
        lines.append("")
        
        course_info = api_data.get('data', {}).get('course', {})
        if course_info:
            lines.append(f"Course: {course_info.get('title', 'N/A')}")
            lines.append(f"Course ID: {course_info.get('id', 'N/A')}")
            lines.append("")
        
        # Process topics
        topics = api_data.get('data', {}).get('classes', [])
        
        for topic in topics:
            topic_name = topic.get('topicName', 'Unknown Topic')
            topic_id = topic.get('topicId', '')
            
            lines.append("=" * 80)
            lines.append(f"TOPIC: {topic_name.upper()}")
            lines.append("=" * 80)
            lines.append("")
            
            classes = topic.get('classes', [])
            
            for class_item in classes:
                # Class header
                class_title = class_item.get('title', 'No Title')
                teacher_name = class_item.get('teacherName', 'Unknown Teacher')
                class_id = class_item.get('classId', '')
                
                lines.append(f"Class: {class_title}")
                lines.append(f"Teacher: {teacher_name}")
                lines.append(f"Class ID: {class_id}")
                lines.append("")
                
                # Video links
                lines.append("VIDEO LECTURES:")
                lines.append("-" * 40)
                
                # Get video recordings
                mp4_recordings = class_item.get('mp4Recordings', [])
                class_link = class_item.get('class_link', '')
                
                # Add main class link if available
                if class_link and 'youtube.com' in class_link:
                    lines.append(f"YouTube: {class_link}")
                
                # Add MP4 recordings with preferred quality
                if mp4_recordings:
                    # Try to find preferred quality
                    found_quality = False
                    for recording in mp4_recordings:
                        quality = recording.get('quality', '').lower()
                        url = recording.get('url', '')
                        if url and quality == preferred_quality.lower():
                            lines.append(f"{quality.upper()}: {url}")
                            found_quality = True
                    
                    # If preferred quality not found, show all available
                    if not found_quality:
                        for recording in mp4_recordings:
                            quality = recording.get('quality', '').upper()
                            url = recording.get('url', '')
                            if url:
                                lines.append(f"{quality}: {url}")
                else:
                    lines.append("No video recordings available")
                
                lines.append("")
                
                # PDF materials
                lines.append("PDF MATERIALS:")
                lines.append("-" * 40)
                
                class_pdfs = class_item.get('classPdf', [])
                if class_pdfs:
                    for pdf in class_pdfs:
                        pdf_name = pdf.get('name', 'Unnamed PDF')
                        pdf_url = pdf.get('url', '')
                        if pdf_url:
                            lines.append(f"• {pdf_name}: {pdf_url}")
                else:
                    lines.append("No PDF materials available")
                
                # Class tests/practice sheets
                class_tests = class_item.get('classTest', [])
                if class_tests:
                    lines.append("")
                    lines.append("PRACTICE SHEETS/TESTS:")
                    lines.append("-" * 40)
                    for test in class_tests:
                        test_name = test.get('name', 'Unnamed Test')
                        test_url = test.get('url', '')
                        if test_url:
                            lines.append(f"• {test_name}: {test_url}")
                
                lines.append("")
                lines.append("=" * 80)
                lines.append("")
        
        # Footer
        lines.append("=" * 80)
        lines.append(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"Video Quality Preference: {preferred_quality.upper()}")
        lines.append("=" * 80)
        
        return '\n'.join(lines)
        
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
                InlineKeyboardButton("720p", callback_data="quality_720p"),
            ],
            [
                InlineKeyboardButton("1080p", callback_data="quality_1080p"),
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "🎥 **Select your preferred video quality:**\n\n"
            "This will be used for video links in the generated files.",
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
                        f"✅ **Selected Course:** {course['title']}\n\n"
                        f"Now use /get_course to generate the data file.",
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
            
            await query.edit_message_text(
                f"✅ **Video quality set to:** {quality.upper()}\n\n"
                f"This will be used for all future course file generations.",
                parse_mode='Markdown'
            )
            
    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text messages"""
        text = update.message.text
        
        if text.lower() in ['/cancel', 'cancel']:
            user_id = update.effective_user.id
            if user_id in self.user_sessions:
                self.user_sessions[user_id]['selected_course'] = None
                await update.message.reply_text("✅ Operation cancelled. Course selection cleared.")
            else:
                await update.message.reply_text("No active operation to cancel.")
        else:
            await update.message.reply_text(
                "Please use one of the available commands:\n\n"
                "/start - Welcome message\n"
                "/help - Usage instructions\n"
                "/batches - Show available courses\n"
                "/quality - Set video quality\n"
                "/get_course - Generate course file"
            )

def keep_alive():
    """Keep-alive mechanism for Render"""
    def ping_server():
        while True:
            try:
                logger.info("Bot is alive and running...")
                time.sleep(300)  # Log every 5 minutes
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
    bot = CourseDataBot(token)
    
    logger.info("Bot is starting...")
    bot.application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
