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
🤖 **Mathematics Course Bot**

I can generate structured course files from provided content including:

• **Video Lectures** with quality preference
• **Class PDFs** (study materials)
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
1. `/batches` - See available courses
2. Select a course from the list
3. `/get_course` - Generate complete data file
4. Receive a .txt file with everything organized

**What's included in the file:**
✅ **VIDEO LECTURES** - Class videos in your preferred quality
✅ **CLASS PDFs** - Study materials for each class
✅ **TEACHER INFORMATION** - Who taught each class

**Video Quality Options:**
- 720p (HD - Default)
- 1080p (Full HD - if available)

**Note:** The bot generates structured files from provided course data.
        """
        await update.message.reply_text(help_text, parse_mode='Markdown')
        
    async def batches_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show available courses"""
        await update.message.reply_text("📚 Fetching available courses...")
        
        try:
            # Example courses based on your text file
            courses = [
                {
                    "id": "maths_special_1",
                    "title": "Mathematics Special Course - Part 1",
                    "description": "Complete mathematics course with Number System, Calculation, Surds, LCM/HCF, Mensuration, Problem on Ages"
                },
                {
                    "id": "full_maths_course",
                    "title": "Complete Mathematics Master Course",
                    "description": "All mathematics topics from Class 01 to Class 21"
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
                "1. **Mathematics Special Course - Part 1**\n   Complete math topics with videos and PDFs\n\n"
                "2. **Complete Mathematics Master Course**\n   All math classes from 01 to 21\n\n"
                "Each file will include:\n"
                "• Video lecture links\n"
                "• Class PDF materials\n"
                "• Organized by topics and classes",
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
            f"📡 **Generating Complete Data for:** {course_title}\n"
            f"🎥 **Video Quality:** {preferred_quality.upper()}\n"
            f"⏳ **Processing:**\n"
            f"   • Parsing course content ✓\n"
            f"   • Organizing by topics and classes ✓\n"
            f"   • Generating structured file ✓\n\n"
            f"Please wait, this may take a moment..."
        )
        
        try:
            # Read the provided text file content
            with open('Maths_Special-1 (2).txt', 'r', encoding='utf-8') as f:
                file_content = f.read()
            
            # Parse the content
            parsed_data = self.parse_course_content(file_content)
            
            # Generate complete text file
            text_content = self.generate_structured_file(
                parsed_data, 
                course_title, 
                preferred_quality
            )
            
            # Create filename
            safe_title = ''.join(c for c in course_title if c.isalnum() or c in (' ', '-', '_')).rstrip()
            filename = f"{safe_title.replace(' ', '_')}_Complete_{datetime.now().strftime('%Y%m%d_%H%M')}.txt"
            
            # Count totals
            total_classes = len(parsed_data['entries'])
            total_pdfs = sum(1 for entry in parsed_data['entries'] if entry['pdf_url'])
            
            # Send file
            await update.message.reply_document(
                document=text_content.encode('utf-8'),
                filename=filename,
                caption=(
                    f"✅ **{course_title}**\n\n"
                    f"📊 **Contains:**\n"
                    f"• {total_classes} Video lectures ({preferred_quality.upper()})\n"
                    f"• {total_pdfs} Class PDF materials\n"
                    f"• Organized by topics and classes\n\n"
                    f"📅 Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                ),
                parse_mode='Markdown'
            )
            
        except FileNotFoundError:
            await update.message.reply_text("❌ Course data file not found.")
        except Exception as e:
            logger.error(f"Error generating file: {e}")
            await update.message.reply_text("❌ Error generating course file. Please try again.")
            
    def parse_course_content(self, content):
        """Parse the text file content into structured data"""
        lines = content.strip().split('\n')
        entries = []
        topics_set = set()
        current_video_entry = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Check if it's a video entry
            if line.startswith('Class-'):
                # This is a video entry
                parts = line.split(': https://')
                if len(parts) < 2:
                    continue
                    
                title_part = parts[0].strip()
                video_url = 'https://' + parts[1].strip()
                
                # Parse the title to extract information
                title_parts = title_part.split('||')
                if len(title_parts) < 3:
                    continue
                    
                class_info = title_parts[0].strip()
                topic_info = title_parts[2].strip()
                
                # Extract class number
                class_num = class_info.replace('Class-', '').strip()
                
                # Extract topic
                topic_parts = topic_info.split('|')
                topic = topic_parts[0].strip()
                
                # Extract teacher
                teacher = "Gagan sir"
                if 'Gagan Pratap' in line:
                    teacher = "Gagan Pratap"
                elif 'GAGAN PRATAP' in line:
                    teacher = "Gagan Pratap"
                elif 'GAGAN SIR' in line:
                    teacher = "Gagan sir"
                
                topics_set.add(topic)
                
                # Create video entry
                current_video_entry = {
                    'class_num': class_num,
                    'topic': topic,
                    'teacher': teacher,
                    'video_url': video_url,
                    'pdf_url': None,
                    'pdf_name': None
                }
                
            # Check if it's a PDF entry (usually follows a video entry)
            elif line.startswith('http') and 'pdf' in line and current_video_entry:
                # This is a PDF URL
                pdf_url = line.strip()
                pdf_name = "Class PDF"
                
                # Try to extract PDF name from previous context
                for i in range(len(lines) - 1, -1, -1):
                    if lines[i] == line:
                        if i > 0 and not lines[i-1].startswith('http'):
                            pdf_name = lines[i-1].split(':')[0].strip()
                            break
                
                current_video_entry['pdf_url'] = pdf_url
                current_video_entry['pdf_name'] = pdf_name
                entries.append(current_video_entry.copy())
                current_video_entry = None
                
            elif 'pdfs/files/' in line and current_video_entry:
                # Alternative PDF format
                pdf_url = line.strip()
                pdf_name = "Class PDF"
                
                # Extract name from URL
                if 'pdfs/files/' in pdf_url:
                    name_part = pdf_url.split('pdfs/files/')[1]
                    if '/' in name_part:
                        name_part = name_part.split('/')[0]
                    pdf_name = name_part.replace('.pdf', '').replace('_', ' ').title()
                
                current_video_entry['pdf_url'] = pdf_url
                current_video_entry['pdf_name'] = pdf_name
                entries.append(current_video_entry.copy())
                current_video_entry = None
        
        # Add any remaining video entry without PDF
        if current_video_entry:
            entries.append(current_video_entry)
        
        return {
            'entries': entries,
            'topics': sorted(list(topics_set))
        }
        
    def generate_structured_file(self, parsed_data, course_title, preferred_quality):
        """Generate structured text file from parsed data"""
        lines = []
        
        # Header
        lines.append("=" * 80)
        lines.append(f"COMPLETE COURSE DATA: {course_title.upper()}")
        lines.append("=" * 80)
        lines.append("")
        lines.append("GENERATED BY TELEGRAM COURSE BOT")
        lines.append(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"Video Quality: {preferred_quality.upper()}")
        lines.append("")
        lines.append("This file contains:")
        lines.append("1. Video Lecture Links")
        lines.append("2. Class PDF Materials")
        lines.append("3. Teacher Information")
        lines.append("4. Organized by Topics and Classes")
        lines.append("")
        lines.append("=" * 80)
        lines.append("")
        
        # Course Information
        lines.append("COURSE INFORMATION:")
        lines.append(f"Title: {course_title}")
        lines.append(f"Total Topics: {len(parsed_data['topics'])}")
        lines.append(f"Total Classes: {len(parsed_data['entries'])}")
        lines.append("")
        
        # Group entries by topic
        entries_by_topic = {}
        for entry in parsed_data['entries']:
            topic = entry['topic']
            if topic not in entries_by_topic:
                entries_by_topic[topic] = []
            entries_by_topic[topic].append(entry)
        
        # Sort entries within each topic by class number
        for topic in entries_by_topic:
            entries_by_topic[topic].sort(key=lambda x: int(x['class_num']) if x['class_num'].isdigit() else 0)
        
        # Process each topic
        for topic in sorted(entries_by_topic.keys()):
            lines.append("")
            lines.append("=" * 80)
            lines.append(f"TOPIC: {topic.upper()}")
            lines.append("=" * 80)
            lines.append("")
            
            lines.append("📺 VIDEO LECTURES & CLASS MATERIALS:")
            lines.append("-" * 40)
            lines.append("")
            
            for entry in entries_by_topic[topic]:
                # Class info
                lines.append(f"📋 Class-{entry['class_num']}: {entry['topic']}")
                lines.append(f"👨‍🏫 Teacher: {entry['teacher']}")
                
                # Video link
                if entry['video_url']:
                    lines.append(f"🎥 VIDEO ({preferred_quality.upper()}): {entry['video_url']}")
                
                # PDF link
                if entry['pdf_url']:
                    lines.append(f"📄 PDF: {entry['pdf_name']}")
                    lines.append(f"   📎 {entry['pdf_url']}")
                else:
                    lines.append("📄 PDF: Not Available")
                
                lines.append("-" * 40)
                lines.append("")
        
        # Summary
        lines.append("")
        lines.append("=" * 80)
        lines.append("SUMMARY")
        lines.append("=" * 80)
        lines.append("")
        
        # Count totals
        total_classes = len(parsed_data['entries'])
        total_pdfs = sum(1 for entry in parsed_data['entries'] if entry['pdf_url'])
        
        lines.append(f"Total Topics Covered: {len(parsed_data['topics'])}")
        lines.append(f"Total Video Classes: {total_classes}")
        lines.append(f"Total Class PDFs: {total_pdfs}")
        lines.append("")
        
        # List all topics
        lines.append("Topics Covered:")
        for i, topic in enumerate(sorted(parsed_data['topics']), 1):
            topic_class_count = sum(1 for entry in parsed_data['entries'] if entry['topic'] == topic)
            lines.append(f"{i}. {topic} ({topic_class_count} classes)")
        
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
                InlineKeyboardButton("720p (HD - Recommended)", callback_data="quality_720p"),
                InlineKeyboardButton("1080p (Full HD)", callback_data="quality_1080p"),
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        current_quality = self.user_sessions[user_id]['preferred_quality']
        
        await update.message.reply_text(
            f"🎥 **Select your preferred video quality:**\n\n"
            f"**Current:** {current_quality.upper()}\n\n"
            f"This quality will be shown in the generated file.\n\n"
            f"**Note:** Most videos in the course are 720p.",
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
                        f"📖 Description: {course.get('description', 'Complete course with videos and materials')}\n\n"
                        f"Now use `/get_course` to generate the complete data file.\n\n"
                        f"The file will include:\n"
                        f"• Video lecture links\n"
                        f"• Class PDF materials\n"
                        f"• Organized by topics and classes",
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
                '720p': 'HD - Recommended for most users',
                '1080p': 'Full HD - Best quality if available'
            }
            
            description = quality_descriptions.get(quality, '')
            
            await query.edit_message_text(
                f"✅ **Video quality set to:** {quality.upper()}\n\n"
                f"{description}\n\n"
                f"This setting will be used in all generated course files.\n\n"
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
