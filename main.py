import os
import logging
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

**API Endpoints Used:**
• Video Classes: `/api/courses/{id}/classes?populate=full`
• Practice Sheets: `/api/courses/{id}/pdfs?groupBy=topic`

**Note:** The bot fetches real-time data from the APIs.
        """
        await update.message.reply_text(help_text, parse_mode='Markdown')
        
    async def batches_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show available courses with example data"""
        await update.message.reply_text("📚 Fetching available courses...")
        
        try:
            # Example courses - you can modify these or fetch from an API
            courses = [
                {
                    "id": "695b8c182feca20f81c25e42", 
                    "title": "RRB Group-D Target Batch (Complete)",
                    "description": "Complete RRB Group-D preparation with videos and practice sheets"
                },
                {
                    "id": "68dbdf3a63a1698bf4194576", 
                    "title": "Science Foundation Course",
                    "description": "Physics, Chemistry, Biology with practice materials"
                },
                {
                    "id": "68e7b6e6aaf4383d1192dfb6", 
                    "title": "Mathematics Master Course",
                    "description": "Complete math syllabus with problem sheets"
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
                "1. **RRB Group-D Target Batch** - Complete preparation\n"
                "2. **Science Foundation Course** - Physics, Chemistry, Biology\n"
                "3. **Mathematics Master Course** - Complete math syllabus\n\n"
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
            f"📡 **Fetching Complete Data for:** {course_title}\n"
            f"🎥 **Video Quality:** {preferred_quality.upper()}\n"
            f"⏳ **Fetching:**\n"
            f"   • Video lectures and class PDFs ✓\n"
            f"   • Practice sheets and test papers ✓\n\n"
            f"Please wait, this may take a moment..."
        )
        
        try:
            # Fetch data from both APIs
            video_data = await self.fetch_video_data(course_id)
            practice_data = await self.fetch_practice_data(course_id)
            
            if not video_data and not practice_data:
                await update.message.reply_text("❌ No data found for this course.")
                return
            
            # Generate complete text file
            text_content = self.generate_complete_file(
                video_data, 
                practice_data, 
                course_title, 
                preferred_quality
            )
            
            # Create filename
            safe_title = ''.join(c for c in course_title if c.isalnum() or c in (' ', '-', '_')).rstrip()
            filename = f"{safe_title.replace(' ', '_')}_Complete_{datetime.now().strftime('%Y%m%d')}.txt"
            
            # Send file
            await update.message.reply_document(
                document=text_content.encode('utf-8'),
                filename=filename,
                caption=(
                    f"✅ **{course_title}**\n\n"
                    f"📊 **Contains:**\n"
                    f"• Video lectures ({preferred_quality.upper()})\n"
                    f"• Class PDF materials\n"
                    f"• Practice sheets\n"
                    f"• Organized by topics\n\n"
                    f"📅 Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                ),
                parse_mode='Markdown'
            )
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error: {e}")
            await update.message.reply_text("❌ Network error. Please check your connection and try again.")
        except Exception as e:
            logger.error(f"Error generating file: {e}")
            await update.message.reply_text("❌ Error generating course file. Please try again.")
            
    async def fetch_video_data(self, course_id):
        """Fetch video classes and class PDFs from API"""
        try:
            api_url = f"{self.api_base_url}/courses/{course_id}/classes?populate=full"
            logger.info(f"Fetching video data from: {api_url}")
            
            response = requests.get(api_url, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get('state') != 200:
                logger.error(f"Video API error: {data.get('msg')}")
                return None
                
            return data.get('data', {})
            
        except Exception as e:
            logger.error(f"Error fetching video data: {e}")
            return None
            
    async def fetch_practice_data(self, course_id):
        """Fetch practice sheets from API"""
        try:
            api_url = f"{self.api_base_url}/courses/{course_id}/pdfs?groupBy=topic"
            logger.info(f"Fetching practice data from: {api_url}")
            
            response = requests.get(api_url, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get('state') != 200:
                logger.error(f"Practice API error: {data.get('msg')}")
                return None
                
            return data.get('data', {})
            
        except Exception as e:
            logger.error(f"Error fetching practice data: {e}")
            return None
            
    def generate_complete_file(self, video_data, practice_data, course_title, preferred_quality):
        """Generate complete text file with videos and practice sheets"""
        lines = []
        
        # Header
        lines.append("=" * 80)
        lines.append(f"COMPLETE COURSE DATA: {course_title.upper()}")
        lines.append("=" * 80)
        lines.append("")
        lines.append("GENERATED BY TELEGRAM COURSE BOT")
        lines.append(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"Video Quality Preference: {preferred_quality.upper()}")
        lines.append("")
        lines.append("This file contains:")
        lines.append("1. Video Lecture Links (with quality options)")
        lines.append("2. Class PDF Materials")
        lines.append("3. Practice Sheets (Topic-wise)")
        lines.append("4. Teacher Information")
        lines.append("")
        lines.append("=" * 80)
        lines.append("")
        
        # Get course info
        course_info = video_data.get('course', {}) if video_data else {}
        if course_info:
            lines.append(f"COURSE INFORMATION:")
            lines.append(f"Title: {course_info.get('title', 'N/A')}")
            lines.append(f"ID: {course_info.get('id', 'N/A')}")
            lines.append(f"Type: {'Live' if course_info.get('isLive') else 'Recorded'}")
            lines.append(f"Status: {'Free' if course_info.get('isFree') else 'Paid'}")
            lines.append("")
        
        # Get topics from video data
        video_topics = video_data.get('classes', []) if video_data else []
        
        # Get practice topics
        practice_topics = practice_data.get('pdfs', []) if practice_data else []
        
        # Create a combined list of all topics
        all_topic_ids = set()
        
        # Add video topic IDs
        for topic in video_topics:
            topic_id = topic.get('topicId')
            if topic_id:
                all_topic_ids.add(topic_id)
        
        # Add practice topic IDs
        for topic in practice_topics:
            topic_id = topic.get('topicId')
            if topic_id:
                all_topic_ids.add(topic_id)
        
        # Process each topic
        for topic_id in all_topic_ids:
            # Find topic in video data
            video_topic = next((t for t in video_topics if t.get('topicId') == topic_id), None)
            
            # Find topic in practice data
            practice_topic = next((t for t in practice_topics if t.get('topicId') == topic_id), None)
            
            topic_name = "Unknown Topic"
            if video_topic:
                topic_name = video_topic.get('topicName', 'Unknown Topic')
            elif practice_topic:
                topic_name = practice_topic.get('topicName', 'Unknown Topic')
            
            # Topic Header
            lines.append("")
            lines.append("=" * 80)
            lines.append(f"TOPIC: {topic_name.upper()}")
            lines.append("=" * 80)
            lines.append("")
            
            # VIDEO CLASSES SECTION
            if video_topic and video_topic.get('classes'):
                lines.append("📺 VIDEO LECTURES:")
                lines.append("-" * 40)
                
                classes = video_topic['classes']
                # Sort classes by priority if available
                classes.sort(key=lambda x: x.get('priority', 999))
                
                for class_item in classes:
                    # Class info
                    class_title = class_item.get('title', 'No Title')
                    teacher = class_item.get('teacherName', 'Unknown Teacher')
                    class_id = class_item.get('classId', '')
                    
                    lines.append("")
                    lines.append(f"📋 Class: {class_title}")
                    lines.append(f"👨‍🏫 Teacher: {teacher}")
                    
                    # Video links
                    video_links = []
                    
                    # YouTube link
                    class_link = class_item.get('class_link', '')
                    if class_link and 'youtube.com' in class_link:
                        video_links.append(f"🎬 YouTube: {class_link}")
                    
                    # MP4 recordings with preferred quality
                    mp4_recordings = class_item.get('mp4Recordings', [])
                    if mp4_recordings:
                        # Try to find preferred quality
                        found = False
                        for recording in mp4_recordings:
                            quality = recording.get('quality', '').lower()
                            url = recording.get('url', '')
                            if url and quality == preferred_quality.lower():
                                video_links.append(f"🎥 {quality.upper()}: {url}")
                                found = True
                                break
                        
                        # If preferred quality not found, show all available
                        if not found:
                            for recording in mp4_recordings:
                                quality = recording.get('quality', '').upper()
                                url = recording.get('url', '')
                                if url:
                                    video_links.append(f"🎥 {quality}: {url}")
                    
                    # Add video links to output
                    if video_links:
                        for link in video_links:
                            lines.append(link)
                    else:
                        lines.append("❌ No video recordings available")
                    
                    # CLASS PDFs (Study Materials)
                    class_pdfs = class_item.get('classPdf', [])
                    if class_pdfs:
                        lines.append("")
                        lines.append("📄 CLASS PDF MATERIALS:")
                        for pdf in class_pdfs:
                            pdf_name = pdf.get('name', 'Unnamed PDF')
                            pdf_url = pdf.get('url', '')
                            if pdf_url:
                                lines.append(f"   • {pdf_name}")
                                lines.append(f"     📎 {pdf_url}")
                    
                    lines.append("-" * 40)
                
                lines.append("")
            
            # PRACTICE SHEETS SECTION
            if practice_topic and practice_topic.get('pdfs'):
                lines.append("📝 PRACTICE SHEETS & TEST PAPERS:")
                lines.append("-" * 40)
                
                practice_sheets = practice_topic['pdfs']
                
                for i, sheet in enumerate(practice_sheets, 1):
                    sheet_name = sheet.get('name', f'Practice Sheet {i}')
                    sheet_url = sheet.get('url', '')
                    
                    if sheet_url:
                        lines.append(f"{i}. {sheet_name}")
                        lines.append(f"   📎 {sheet_url}")
                        lines.append("")
                
                lines.append("")
            
            # If no content for this topic
            if (not video_topic or not video_topic.get('classes')) and \
               (not practice_topic or not practice_topic.get('pdfs')):
                lines.append("ℹ️ No content available for this topic yet.")
                lines.append("")
        
        # Footer
        lines.append("")
        lines.append("=" * 80)
        lines.append("SUMMARY")
        lines.append("=" * 80)
        lines.append("")
        
        # Count totals
        total_video_classes = 0
        total_class_pdfs = 0
        total_practice_sheets = 0
        
        for topic in video_topics:
            classes = topic.get('classes', [])
            total_video_classes += len(classes)
            for class_item in classes:
                total_class_pdfs += len(class_item.get('classPdf', []))
        
        for topic in practice_topics:
            total_practice_sheets += len(topic.get('pdfs', []))
        
        lines.append(f"Total Topics Covered: {len(all_topic_ids)}")
        lines.append(f"Total Video Classes: {total_video_classes}")
        lines.append(f"Total Class PDFs: {total_class_pdfs}")
        lines.append(f"Total Practice Sheets: {total_practice_sheets}")
        lines.append("")
        lines.append(f"Video Quality Used: {preferred_quality.upper()}")
        lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")
        lines.append("=" * 80)
        lines.append("END OF COURSE DATA")
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
                InlineKeyboardButton("240p (Mobile Data)", callback_data="quality_240p"),
                InlineKeyboardButton("360p (Standard)", callback_data="quality_360p"),
            ],
            [
                InlineKeyboardButton("480p (Good Quality)", callback_data="quality_480p"),
                InlineKeyboardButton("720p (HD - Recommended)", callback_data="quality_720p"),
            ],
            [
                InlineKeyboardButton("1080p (Full HD)", callback_data="quality_1080p"),
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        current_quality = self.user_sessions[user_id]['preferred_quality']
        
        await update.message.reply_text(
            f"🎥 **Select your preferred video quality:**\n\n"
            f"**Current:** {current_quality.upper()}\n\n"
            f"This quality will be prioritized when multiple options are available.\n\n"
            f"**Recommendations:**\n"
            f"• 720p - Best balance of quality and file size\n"
            f"• 480p - Good for slower connections\n"
            f"• 1080p - Best quality if available",
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
                        f"📖 Description: {course.get('description', 'Complete course with videos and practice materials')}\n\n"
                        f"Now use `/get_course` to generate the complete data file.\n\n"
                        f"The file will include:\n"
                        f"• Video lecture links\n"
                        f"• Class PDF materials\n"
                        f"• Practice sheets\n"
                        f"• Organized by topics",
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
                f"This setting will be used for all future course file generations.\n\n"
                f"You can change it anytime using `/quality`",
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
    bot = CompleteCourseBot(token)
    
    logger.info("Bot is starting...")
    bot.application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
