import os
import logging
import requests
from datetime import datetime
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# Get port from environment variable (Render provides this)
port = int(os.environ.get('PORT', 5000))

# Initialize Flask app
app = Flask(__name__)

@app.route('/')
def home():
    return "🤖 Telegram Course Bot is running!"

@app.route('/health')
def health():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class CourseBot:
    def __init__(self, token: str):
        self.token = token
        self.application = Application.builder().token(token).build()
        self.api_base_url = "https://backend.multistreaming.site/api"
        self.user_preferences = {}
        self.available_courses = []
        self.setup_handlers()
        
    def setup_handlers(self):
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("batches", self.batches_command))
        self.application.add_handler(CommandHandler("get_course", self.get_course_command))
        self.application.add_handler(CommandHandler("quality", self.quality_command))
        self.application.add_handler(CommandHandler("sheets", self.sheets_command))
        self.application.add_handler(CallbackQueryHandler(self.quality_callback, pattern="^quality_"))
        self.application.add_handler(CallbackQueryHandler(self.course_callback, pattern="^course_"))
        self.application.add_handler(CallbackQueryHandler(self.sheets_callback, pattern="^sheets_"))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text))
        
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if user_id not in self.user_preferences:
            self.user_preferences[user_id] = "720p"
        
        welcome_text = f"""🤖 Course Data Bot

I can fetch course data from the API and send you formatted text files containing:

• Topics and classes
• Video lecture links (your chosen quality)
• PDF material links
• Practice sheets/PDFs
• Teacher information

Your current video quality preference: {self.user_preferences[user_id]}

Commands:
/start - Show this message  
/help - Get help information  
/batches - Show all available batches
/quality - Change video quality preference  
/get_course - Fetch course data from API and get a text file
/sheets - Get practice sheets separately"""
        await update.message.reply_text(welcome_text)
        
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        help_text = """📖 Help Guide

/batches
- Shows all available courses/batches
- Select a batch to get its data

/get_course
- Fetches data from the course API
- Generates a .txt file with:
  • Course info
  • Topics and classes
  • Video links (your preferred quality)
  • PDF links with names
  • Practice sheets (if available)

/sheets
- Get practice sheets separately as a text file
- Shows available topics for practice sheets

/quality
- Change your preferred video quality
- Available options: 240p, 360p, 480p, 720p, 1080p
- The bot will prioritize your chosen quality

The bot generates a structured text file with all the links."""
        await update.message.reply_text(help_text)
    
    async def batches_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show all available batches/courses"""
        await update.message.reply_text("📚 Fetching available batches...")
        
        try:
            # Fetch all courses from API
            api_url = f"{self.api_base_url}/courses"
            logger.info(f"Fetching batches from: {api_url}")
            
            response = requests.get(api_url, timeout=30)
            logger.info(f"API Response Status: {response.status_code}")
            
            response.raise_for_status()
            
            data = response.json()
            logger.info(f"API Response Data: {data}")
            
            if data.get('state') != 200:
                error_msg = data.get('msg', 'Unknown error')
                logger.error(f"API returned error state: {error_msg}")
                await update.message.reply_text(f"❌ API Error: {error_msg}")
                return
            
            courses = data.get('data', [])
            logger.info(f"Found {len(courses)} courses")

            if not courses:
                await update.message.reply_text("❌ No batches found in the API.")
                return
            
            self.available_courses = courses
            context.user_data['available_courses'] = courses
            
            # Create keyboard with batches
            keyboard = []
            for i, course in enumerate(courses, 1):
                course_title = course.get('title', f'Batch {i}')[:64]  # Limit title length
                keyboard.append([InlineKeyboardButton(f"{i}. {course_title}", callback_data=f"course_{i-1}")])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                f"📚 Available Batches ({len(courses)} found):\n\nClick on a batch to get its data:",
                reply_markup=reply_markup
            )
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error fetching batches: {e}")
            await update.message.reply_text("❌ Network error fetching batches. Please try again later.")
        except Exception as e:
            logger.error(f"Unexpected error fetching batches: {e}")
            await update.message.reply_text("❌ Error fetching batches. Please try again later.")
    
    async def course_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle course selection"""
        query = update.callback_query
        await query.answer()
        
        try:
            course_index = int(query.data.replace("course_", ""))
            courses = context.user_data.get('available_courses', [])
            
            if not courses or course_index >= len(courses):
                await query.edit_message_text("❌ Course not found. Please try /batches again.")
                return
            
            selected_course = courses[course_index]
            course_id = selected_course.get('id')
            course_title = selected_course.get('title', 'Unknown Course')
            
            # Store selected course ID in context for get_course_command
            context.user_data['selected_course_id'] = course_id
            context.user_data['selected_course_title'] = course_title
            
            # Automatically fetch course data and send as file
            await query.edit_message_text(f"✅ Selected: {course_title}\n\nFetching course data...")
            await self.fetch_and_send_course_data(update, context, course_id, course_title)
            
        except Exception as e:
            logger.error(f"Error in course callback: {e}")
            await query.edit_message_text("❌ Error selecting course. Please try again.")
    
    async def get_course_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Fetch course data for the selected batch"""
        user_id = update.effective_user.id
        preferred_quality = self.user_preferences.get(user_id, "720p")
        
        # Check if we have a selected course
        course_id = context.user_data.get('selected_course_id')
        course_title = context.user_data.get('selected_course_title', 'Unknown Course')
        
        if not course_id:
            await update.message.reply_text(
                "❌ No course selected. Please use /batches to select a batch first."
            )
            return
        
        await update.message.reply_text(
            f"📡 Fetching data for: {course_title}\n"
            f"🎥 Using quality preference: {preferred_quality.upper()}"
        )
        
        await self.fetch_and_send_course_data(update, context, course_id, course_title, preferred_quality)
    
    async def fetch_and_send_course_data(self, update: Update, context: ContextTypes.DEFAULT_TYPE, course_id: str, course_title: str, preferred_quality: str = None):
        """Fetch and process course data and send as file"""
        if preferred_quality is None:
            user_id = update.effective_user.id
            preferred_quality = self.user_preferences.get(user_id, "720p")
        
        try:
            # Fetch course classes data
            api_url = f"{self.api_base_url}/courses/{course_id}/classes?populate=full"
            logger.info(f"Fetching course data from: {api_url}")
            
            response = requests.get(api_url, timeout=30)
            logger.info(f"Course API Response Status: {response.status_code}")
            
            response.raise_for_status()
            
            data = response.json()
            logger.info(f"Course API Response Keys: {list(data.keys())}")
            
            # Check if API returned success
            if data.get('state') != 200:
                error_msg = data.get('msg', 'Unknown error')
                logger.error(f"Course API returned error: {error_msg}")
                await update.effective_message.reply_text(f"❌ API Error: {error_msg}")
                return
            
            # Check if data structure is as expected
            if 'data' not in data:
                logger.error(f"Unexpected data structure: {data}")
                await update.effective_message.reply_text("❌ Unexpected data format from API.")
                return
            
            course_info = data['data'].get('course', {})
            classes_data = data['data'].get('classes', [])
            
            logger.info(f"Found {len(classes_data)} topics in course")
            
            # Fetch practice sheets
            practice_sheets = await self.fetch_practice_sheets(course_id)
            
            if not classes_data and not practice_sheets:
                await update.effective_message.reply_text("❌ No class data or practice sheets found for this course.")
                return
            
            text_content = self.generate_formatted_text_file(course_info, classes_data, preferred_quality, practice_sheets)
            
            # Remove numbering/timestamp from filename - just use course title
            filename = f"{course_title.replace(' ', '_')}.txt"
            
            # Send as text file
            await update.effective_message.reply_document(
                document=text_content.encode('utf-8'),
                filename=filename,
                caption=(
                    f"📚 Course Data: {course_title}\n"
                    f"🎥 Quality Preference: {preferred_quality.upper()}\n"
                    f"📊 Practice Sheets: {len(practice_sheets.get('pdfs', [])) if practice_sheets else 0}\n"
                    f"📅 Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                )
            )
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error fetching course data: {e}")
            await update.effective_message.reply_text("❌ Network error fetching course data. Please try again later.")
        except ValueError as e:
            logger.error(f"JSON parsing error: {e}")
            await update.effective_message.reply_text("❌ Data format error from API. Please try again later.")
        except Exception as e:
            logger.error(f"Unexpected error in fetch_course_data: {e}")
            await update.effective_message.reply_text("❌ Error fetching course data. Please try again later.")
    
    async def fetch_practice_sheets(self, course_id: str):
        """Fetch practice sheets for a course"""
        try:
            api_url = f"{self.api_base_url}/courses/{course_id}/pdfs?groupBy=topic"
            logger.info(f"Fetching practice sheets from: {api_url}")
            
            response = requests.get(api_url, timeout=30)
            logger.info(f"Practice Sheets API Response Status: {response.status_code}")
            
            response.raise_for_status()
            
            data = response.json()
            
            if data.get('state') != 200:
                logger.warning(f"Practice sheets API returned error: {data.get('msg')}")
                return None
            
            # Extract PDFs from the response
            practice_sheets_data = data.get('data', {})
            
            # Flatten all PDFs from all topics into a single list
            all_pdfs = []
            topics = practice_sheets_data.get('topics', [])
            
            for topic in topics:
                topic_name = topic.get('topicName', 'Unknown Topic')
                pdfs = topic.get('pdfs', [])
                
                for pdf in pdfs:
                    pdf['topic_name'] = topic_name
                    all_pdfs.append(pdf)
            
            logger.info(f"Found {len(all_pdfs)} practice sheets")
            
            return {
                'topics': topics,
                'pdfs': all_pdfs
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error fetching practice sheets: {e}")
            return None
        except Exception as e:
            logger.error(f"Error fetching practice sheets: {e}")
            return None
    
    async def sheets_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Get practice sheets separately"""
        # Check if we have a selected course
        course_id = context.user_data.get('selected_course_id')
        course_title = context.user_data.get('selected_course_title', 'Unknown Course')
        
        if not course_id:
            await update.message.reply_text(
                "❌ No course selected. Please use /batches to select a batch first."
            )
            return
        
        await update.message.reply_text(f"📄 Fetching practice sheets for: {course_title}")
        
        try:
            practice_sheets = await self.fetch_practice_sheets(course_id)
            
            if not practice_sheets or not practice_sheets.get('pdfs'):
                await update.message.reply_text("❌ No practice sheets found for this course.")
                return
            
            # Create keyboard with options
            keyboard = [
                [
                    InlineKeyboardButton("📄 All Sheets", callback_data="sheets_all"),
                    InlineKeyboardButton("📁 By Category", callback_data="sheets_category")
                ],
                [
                    InlineKeyboardButton("🧮 Maths Only", callback_data="sheets_maths"),
                    InlineKeyboardButton("📚 Topic-wise", callback_data="sheets_topics")
                ]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            total_sheets = len(practice_sheets['pdfs'])
            categories = set()
            for pdf in practice_sheets['pdfs']:
                category_name = pdf.get('category', {}).get('categoryName', 'Unknown')
                categories.add(category_name)
            
            await update.message.reply_text(
                f"📊 Found {total_sheets} practice sheets\n"
                f"📁 Categories: {', '.join(categories)}\n\n"
                f"Select how you want to organize the sheets:",
                reply_markup=reply_markup
            )
            
            # Store practice sheets in context
            context.user_data['practice_sheets'] = practice_sheets
            
        except Exception as e:
            logger.error(f"Error in sheets command: {e}")
            await update.message.reply_text("❌ Error fetching practice sheets. Please try again.")
    
    async def sheets_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle practice sheets organization choice"""
        query = update.callback_query
        await query.answer()
        
        action = query.data.replace("sheets_", "")
        practice_sheets = context.user_data.get('practice_sheets', {})
        course_title = context.user_data.get('selected_course_title', 'Unknown Course')
        
        if not practice_sheets:
            await query.edit_message_text("❌ Practice sheets data not found. Please try /sheets again.")
            return
        
        await query.edit_message_text(f"📄 Generating {action.replace('_', ' ').title()} format...")
        
        try:
            if action == "all":
                text_content = self.format_all_sheets(practice_sheets)
            elif action == "category":
                text_content = self.format_by_category(practice_sheets)
            elif action == "maths":
                text_content = self.format_maths_only(practice_sheets)
            elif action == "topics":
                text_content = self.format_by_topic(practice_sheets)
            else:
                text_content = self.format_all_sheets(practice_sheets)
            
            filename = f"{course_title.replace(' ', '_')}_Practice_Sheets.txt"
            
            await query.message.reply_document(
                document=text_content.encode('utf-8'),
                filename=filename,
                caption=(
                    f"📄 Practice Sheets: {course_title}\n"
                    f"📊 Format: {action.replace('_', ' ').title()}\n"
                    f"📅 Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                )
            )
            
        except Exception as e:
            logger.error(f"Error generating practice sheets: {e}")
            await query.edit_message_text("❌ Error generating practice sheets file.")
    
    def format_all_sheets(self, practice_sheets):
        """Format all sheets in one list"""
        lines = ["📄 ALL PRACTICE SHEETS 📄\n"]
        lines.append("=" * 50 + "\n")
        
        for i, pdf in enumerate(practice_sheets.get('pdfs', []), 1):
            lines.append(f"{i}. {pdf.get('title', 'Untitled')}")
            lines.append(f"   📁 Topic: {pdf.get('topic_name', 'Unknown')}")
            lines.append(f"   📚 Category: {pdf.get('category', {}).get('categoryName', 'Unknown')}")
            lines.append(f"   🏷️ Section: {pdf.get('section', {}).get('sectionName', 'Unknown')}")
            lines.append(f"   👨‍🏫 Teacher: {pdf.get('teacherName', 'Unknown')}")
            lines.append(f"   🔗 URL: {pdf.get('uploadPdf', 'No URL')}")
            lines.append("")
        
        return '\n'.join(lines)
    
    def format_by_category(self, practice_sheets):
        """Format sheets grouped by category"""
        lines = ["📄 PRACTICE SHEETS BY CATEGORY 📄\n"]
        lines.append("=" * 50 + "\n")
        
        # Group by category
        categories = {}
        for pdf in practice_sheets.get('pdfs', []):
            category_name = pdf.get('category', {}).get('categoryName', 'Unknown')
            if category_name not in categories:
                categories[category_name] = []
            categories[category_name].append(pdf)
        
        for category_name, pdfs in categories.items():
            lines.append(f"\n📁 {category_name.upper()} ({len(pdfs)} sheets)")
            lines.append("-" * 40)
            
            for i, pdf in enumerate(pdfs, 1):
                lines.append(f"{i}. {pdf.get('title', 'Untitled')}")
                lines.append(f"   👨‍🏫 {pdf.get('teacherName', 'Unknown')}")
                lines.append(f"   🔗 {pdf.get('uploadPdf')}")
                lines.append("")
        
        return '\n'.join(lines)
    
    def format_maths_only(self, practice_sheets):
        """Format only Maths sheets"""
        lines = ["🧮 MATHS PRACTICE SHEETS 🧮\n"]
        lines.append("=" * 50 + "\n")
        
        maths_pdfs = []
        for pdf in practice_sheets.get('pdfs', []):
            category_name = pdf.get('category', {}).get('categoryName', '')
            if 'math' in category_name.lower() or 'maths' in category_name.lower():
                maths_pdfs.append(pdf)
        
        if not maths_pdfs:
            lines.append("No Maths practice sheets found.")
            return '\n'.join(lines)
        
        # Group by topic
        topics = {}
        for pdf in maths_pdfs:
            topic_name = pdf.get('topic', {}).get('topicName', 'Unknown')
            if topic_name not in topics:
                topics[topic_name] = []
            topics[topic_name].append(pdf)
        
        for topic_name, pdfs in topics.items():
            lines.append(f"\n📚 {topic_name.upper()} ({len(pdfs)} sheets)")
            lines.append("-" * 40)
            
            for i, pdf in enumerate(pdfs, 1):
                lines.append(f"{i}. {pdf.get('title', 'Untitled')}")
                lines.append(f"   👨‍🏫 {pdf.get('teacherName', 'Unknown')}")
                lines.append(f"   🔗 {pdf.get('uploadPdf')}")
                lines.append("")
        
        return '\n'.join(lines)
    
    def format_by_topic(self, practice_sheets):
        """Format sheets grouped by topic"""
        lines = ["📄 PRACTICE SHEETS BY TOPIC 📄\n"]
        lines.append("=" * 50 + "\n")
        
        topics_data = practice_sheets.get('topics', [])
        
        for topic_data in topics_data:
            topic_name = topic_data.get('topicName', 'Unknown Topic')
            pdfs = topic_data.get('pdfs', [])
            
            lines.append(f"\n📌 {topic_name.upper()} ({len(pdfs)} sheets)")
            lines.append("-" * 40)
            
            for i, pdf in enumerate(pdfs, 1):
                lines.append(f"{i}. {pdf.get('title', 'Untitled')}")
                lines.append(f"   📚 {pdf.get('category', {}).get('categoryName', 'Unknown')}")
                lines.append(f"   👨‍🏫 {pdf.get('teacherName', 'Unknown')}")
                lines.append(f"   🔗 {pdf.get('uploadPdf')}")
                lines.append("")
        
        return '\n'.join(lines)
    
    def get_preferred_video_url(self, class_data, preferred_quality):
        """Get only the preferred quality video URL"""
        mp4_recordings = class_data.get('mp4Recordings', [])
        
        # If no recordings, try class_link
        if not mp4_recordings:
            class_link = class_data.get('class_link')
            if class_link and class_link.startswith(('http://', 'https://')):
                return class_link
            return None
        
        # Look for exact quality match first
        for recording in mp4_recordings:
            quality = recording.get('quality', '').lower()
            if quality == preferred_quality.lower():
                return recording.get('url')
        
        # If exact match not found, look for closest quality
        quality_priority = ['1080p', '720p', '480p', '360p', '240p']
        if preferred_quality.lower() in quality_priority:
            pref_index = quality_priority.index(preferred_quality.lower())
            for i in range(pref_index, len(quality_priority)):
                for recording in mp4_recordings:
                    if recording.get('quality', '').lower() == quality_priority[i]:
                        return recording.get('url')
        
        # If still not found, return the first available recording
        if mp4_recordings:
            return mp4_recordings[0].get('url')
        
        # Fallback to class_link
        class_link = class_data.get('class_link')
        if class_link and class_link.startswith(('http://', 'https://')):
            return class_link
        
        return None
    
    def generate_formatted_text_file(self, course_info, classes_data, preferred_quality, practice_sheets=None):
        """Generate text file with proper arrangement of videos, PDFs, and practice sheets"""
        import re
        lines = []
        
        # Add course header
        lines.append("📚 COURSE CONTENT 📚\n")
        lines.append("=" * 60)
        
        # First, collect all video classes and their PDFs
        all_classes = []
        
        for topic in classes_data:
            topic_name = topic.get('topicName', 'Unknown Topic')
            topic_classes = topic.get('classes', [])
            
            for class_data in topic_classes:
                class_title = class_data.get('title', '')
                teacher_name = class_data.get('teacherName', 'Unknown Teacher')
                
                # Extract class number from title
                class_number = "01"
                if class_title:
                    match = re.search(r'(\d+)', class_title)
                    if match:
                        class_number = match.group(1).zfill(2)
                
                # Get video URL
                video_url = self.get_preferred_video_url(class_data, preferred_quality)
                
                # Get PDFs for this class
                pdfs = []
                class_pdfs = class_data.get('classPdf', [])
                for pdf in class_pdfs:
                    pdf_url = pdf.get('url')
                    pdf_name = pdf.get('name', 'Unknown PDF')
                    if pdf_url and pdf_url.startswith(('http://', 'https://')):
                        pdfs.append({
                            'name': pdf_name,
                            'url': pdf_url,
                            'teacher': teacher_name
                        })
                
                if video_url:
                    all_classes.append({
                        'class_number': class_number,
                        'class_title': class_title,
                        'teacher_name': teacher_name,
                        'topic_name': topic_name,
                        'video_url': video_url,
                        'pdfs': pdfs
                    })
        
        # Sort classes by topic and then by class number
        all_classes.sort(key=lambda x: (x['topic_name'], x['class_number']))
        
        # Group by topic
        current_topic = None
        
        for class_info in all_classes:
            # Add topic header if it's a new topic
            if class_info['topic_name'] != current_topic:
                if current_topic is not None:
                    lines.append("")  # Empty line between topics
                current_topic = class_info['topic_name']
                lines.append(f"📌 {current_topic.upper()}")
                lines.append("-" * 40)
            
            # Add video line
            video_line = f"Class-{class_info['class_number']} || {class_info['class_title']} | {class_info['teacher_name']}"
            lines.append(video_line)
            lines.append(f"🎥 Video: {class_info['video_url']}")
            
            # Add PDFs for this class
            if class_info['pdfs']:
                lines.append("📎 Class PDFs:")
                for pdf in class_info['pdfs']:
                    pdf_line = f"  • {pdf['name']}: {pdf['url']}"
                    lines.append(pdf_line)
            
            lines.append("")  # Empty line between classes
        
        # Add practice sheets section if available
        if practice_sheets and practice_sheets.get('pdfs'):
            lines.append("\n\n" + "=" * 60)
            lines.append("📄 PRACTICE SHEETS 📄")
            lines.append("=" * 60)
            
            practice_pdfs = practice_sheets.get('pdfs', [])
            
            # Group practice sheets by category
            practice_by_category = {}
            for pdf in practice_pdfs:
                category_name = pdf.get('category', {}).get('categoryName', 'Unknown')
                if category_name not in practice_by_category:
                    practice_by_category[category_name] = []
                practice_by_category[category_name].append(pdf)
            
            for category_name, pdfs in practice_by_category.items():
                lines.append(f"\n📁 {category_name.upper()}")
                lines.append("-" * 40)
                
                for i, pdf in enumerate(pdfs, 1):
                    lines.append(f"{i}. {pdf.get('title', 'Untitled')}")
                    lines.append(f"   👨‍🏫 Teacher: {pdf.get('teacherName', 'Unknown')}")
                    lines.append(f"   📚 Topic: {pdf.get('topic_name', 'Unknown')}")
                    lines.append(f"   🔗 URL: {pdf.get('uploadPdf')}")
                    lines.append("")
        
        # Add footer
        lines.append("\n" + "=" * 60)
        lines.append(f"🎥 Video Quality: {preferred_quality.upper()}")
        lines.append(f"📅 Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("=" * 60)
        
        return '\n'.join(lines)
    
    async def quality_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        keyboard = [
            [
                InlineKeyboardButton("240p", callback_data="quality_240p"),
                InlineKeyboardButton("360p", callback_data="quality_360p"),
                InlineKeyboardButton("480p", callback_data="quality_480p"),
            ],
            [
                InlineKeyboardButton("720p", callback_data="quality_720p"),
                InlineKeyboardButton("1080p", callback_data="quality_1080p"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "🎥 Select your preferred video quality:",
            reply_markup=reply_markup
        )
    
    async def quality_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        quality = query.data.replace("quality_", "")
        
        self.user_preferences[user_id] = quality
        await query.edit_message_text(
            f"✅ Video quality preference set to: {quality.upper()}"
        )
    
    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        current_quality = self.user_preferences.get(user_id, "720p")
        
        await update.message.reply_text(
            f"👋 Available commands:\n\n"
            f"/start - Show welcome message\n"
            f"/help - Help & usage\n"
            f"/batches - Show all available batches\n"
            f"/quality - Change video quality (Current: {current_quality.upper()})\n"
            f"/get_course - Fetch data for selected batch\n"
            f"/sheets - Get practice sheets separately"
        )

def run_flask():
    app.run(host='0.0.0.0', port=port)

def main():
    token = os.getenv('TELEGRAM_BOT_TOKEN') or os.getenv('BOT_TOKEN')
    
    if not token:
        logger.error("❌ TELEGRAM_BOT_TOKEN environment variable is required")
        logger.error("Please set TELEGRAM_BOT_TOKEN in your Render environment variables")
        return
    
    logger.info("✅ Bot token found, starting bot...")
    
    try:
        # Start Flask in a separate thread
        import threading
        flask_thread = threading.Thread(target=run_flask, daemon=True)
        flask_thread.start()
        
        logger.info(f"🌐 Flask server started on port {port}")
        
        # Start the bot
        bot = CourseBot(token)
        logger.info("🤖 Bot is starting...")
        bot.application.run_polling(allowed_updates=Update.ALL_TYPES)
        
    except Exception as e:
        logger.error(f"❌ Failed to start bot: {e}")

if __name__ == '__main__':
    main()
