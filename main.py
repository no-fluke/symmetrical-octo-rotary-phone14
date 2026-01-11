import os
import logging
import json
import requests
import asyncio
import threading
import time
from datetime import datetime
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import tempfile
from urllib.parse import urlparse

# Initialize Flask app for keeping Render awake
app = Flask(__name__)

@app.route('/')
def home():
    return "🤖 Course Data Bot is running!"

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
        self.setup_handlers()
        
    def setup_handlers(self):
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("getcourse", self.get_course_command))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text))
        
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        welcome_text = """
🤖 **Course Data Extractor Bot**

I can fetch course data from APIs and organize it for you!

**Commands:**
/start - Show this message
/help - Get help information
/getcourse - Fetch course data from API

**Features:**
- Fetches course data from API endpoints
- Extracts PDF links and video links
- Organizes by topics and classes
- Creates structured text files
        """
        await update.message.reply_text(welcome_text, parse_mode='Markdown')
        
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        help_text = """
📖 **Help Guide**

**How to use:**
1. Use /getcourse to fetch default course data
2. Or send me an API endpoint URL
3. I'll process the data and send you a structured file

**Supported APIs:**
- JSON APIs with course data structure
- Should have classes organized by topics
- Should include PDF and video links

**Output Format:**
- Organized by topics (BIOLOGY, CHEMISTRY, PHYSICS)
- Each class includes:
  - Class title
  - Video links (with quality)
  - PDF links (with names)
  - Teacher name
  - Status
        """
        await update.message.reply_text(help_text, parse_mode='Markdown')
        
    async def get_course_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("📡 Fetching course data from API...")
        
        try:
            # Default API endpoint
            api_url = "https://backend.multistreaming.site/api/courses/68e7b6e6aaf4383d1192dfb6/classes?populate=full"
            
            # Create the text file
            txt_content = await self.fetch_and_process_course_data(api_url)
            
            if txt_content:
                # Create a temporary file
                temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8')
                temp_file.write(txt_content)
                temp_file.close()
                
                # Send the file
                with open(temp_file.name, 'rb') as f:
                    await context.bot.send_document(
                        chat_id=update.message.chat_id,
                        document=f,
                        filename="course_data.txt",
                        caption="✅ Course data extracted successfully!"
                    )
                
                # Clean up
                os.unlink(temp_file.name)
                await update.message.reply_text("✅ File sent successfully!")
            else:
                await update.message.reply_text("❌ Failed to fetch or process course data.")
                
        except Exception as e:
            logger.error(f"Error in get_course_command: {e}")
            await update.message.reply_text(f"❌ Error: {str(e)}")
    
    async def fetch_and_process_course_data(self, api_url: str):
        try:
            # Fetch data from API
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(api_url, headers=headers, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            # Start building the text content
            txt_content = f"Course Data Extracted on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            txt_content += f"API Source: {api_url}\n"
            txt_content += "="*80 + "\n\n"
            
            # Check if data structure is as expected
            if 'data' in data and 'classes' in data['data']:
                topics = data['data']['classes']
                
                for topic in topics:
                    topic_name = topic.get('topicName', 'Unknown Topic')
                    topic_id = topic.get('topicId', '')
                    classes = topic.get('classes', [])
                    
                    txt_content += f"TOPIC: {topic_name} (ID: {topic_id})\n"
                    txt_content += "-"*60 + "\n\n"
                    
                    for class_item in classes:
                        # Basic class info
                        title = class_item.get('title', 'No Title')
                        class_id = class_item.get('classId', '')
                        teacher = class_item.get('teacherName', 'Unknown Teacher')
                        is_free = class_item.get('isFree', False)
                        status = class_item.get('status', 'unknown')
                        
                        txt_content += f"CLASS: {title}\n"
                        txt_content += f"ID: {class_id}\n"
                        txt_content += f"Teacher: {teacher}\n"
                        txt_content += f"Status: {status} | Free: {'Yes' if is_free else 'No'}\n"
                        txt_content += f"Priority: {class_item.get('priority', 'N/A')}\n"
                        
                        # Video links
                        mp4_recordings = class_item.get('mp4Recordings', [])
                        class_link = class_item.get('class_link', '')
                        
                        txt_content += "\n📹 VIDEO LECTURES:\n"
                        if class_link:
                            txt_content += f"  • Class Link: {class_link}\n"
                        
                        if mp4_recordings:
                            for video in mp4_recordings:
                                quality = video.get('quality', 'Unknown')
                                size = video.get('size', 0)
                                url = video.get('url', '')
                                if url:
                                    txt_content += f"  • {quality} ({size} MB): {url}\n"
                        else:
                            txt_content += "  • No video recordings available\n"
                        
                        # PDF links
                        class_pdfs = class_item.get('classPdf', [])
                        
                        txt_content += "\n📚 PDF & PRACTICE SHEETS:\n"
                        if class_pdfs:
                            for pdf in class_pdfs:
                                name = pdf.get('name', 'Unnamed PDF')
                                url = pdf.get('url', '')
                                priority = pdf.get('priority', 1)
                                if url:
                                    txt_content += f"  • PDF {priority}: {name}\n"
                                    txt_content += f"    URL: {url}\n"
                        else:
                            txt_content += "  • No PDFs available\n"
                        
                        # Practice tests (if available)
                        class_tests = class_item.get('classTest', [])
                        if class_tests:
                            txt_content += "\n📝 PRACTICE TESTS:\n"
                            for test in class_tests:
                                test_name = test.get('name', 'Practice Test')
                                test_url = test.get('url', '')
                                if test_url:
                                    txt_content += f"  • {test_name}: {test_url}\n"
                        
                        txt_content += "\n" + "="*60 + "\n\n"
                    
                    txt_content += "\n" + "="*80 + "\n\n"
                
                return txt_content
            else:
                # Try alternative structure
                txt_content = await self.process_alternative_structure(data)
                return txt_content
                
        except Exception as e:
            logger.error(f"Error processing API data: {e}")
            return f"Error processing API data: {str(e)}"
    
    async def process_alternative_structure(self, data):
        """Process alternative data structures"""
        txt_content = "Alternative Data Structure Found\n"
        txt_content += "="*80 + "\n\n"
        
        # Try to extract any useful information
        if isinstance(data, dict):
            for key, value in data.items():
                if key == 'classes' and isinstance(value, list):
                    for item in value:
                        if isinstance(item, dict):
                            title = item.get('title', '')
                            pdfs = item.get('classPdf', [])
                            videos = item.get('mp4Recordings', [])
                            
                            if title:
                                txt_content += f"CLASS: {title}\n"
                            
                            if pdfs:
                                txt_content += "PDFs:\n"
                                for pdf in pdfs:
                                    if isinstance(pdf, dict):
                                        name = pdf.get('name', 'PDF')
                                        url = pdf.get('url', '')
                                        if url:
                                            txt_content += f"  • {name}: {url}\n"
                            
                            if videos:
                                txt_content += "Videos:\n"
                                for video in videos:
                                    if isinstance(video, dict):
                                        url = video.get('url', '')
                                        quality = video.get('quality', '')
                                        if url:
                                            txt_content += f"  • {quality}: {url}\n"
                            
                            txt_content += "\n" + "-"*40 + "\n\n"
        
        return txt_content if len(txt_content) > 100 else "No valid course data found in the API response."
    
    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = update.message.text
        
        # Check if it's a URL
        if text.startswith(('http://', 'https://')):
            await update.message.reply_text("🔗 Processing your API URL...")
            
            try:
                txt_content = await self.fetch_and_process_course_data(text)
                
                if txt_content:
                    # Create a temporary file
                    temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8')
                    temp_file.write(txt_content)
                    temp_file.close()
                    
                    # Send the file
                    with open(temp_file.name, 'rb') as f:
                        await context.bot.send_document(
                            chat_id=update.message.chat_id,
                            document=f,
                            filename="api_data.txt",
                            caption=f"✅ Data extracted from: {text}"
                        )
                    
                    # Clean up
                    os.unlink(temp_file.name)
                    await update.message.reply_text("✅ File sent successfully!")
                else:
                    await update.message.reply_text("❌ Failed to process the API URL.")
                    
            except Exception as e:
                logger.error(f"Error processing URL: {e}")
                await update.message.reply_text(f"❌ Error processing URL: {str(e)}")
        else:
            await update.message.reply_text(
                "Please send me an API URL or use /getcourse to fetch default course data.\n"
                "Example API URL: https://backend.multistreaming.site/api/courses/68e7b6e6aaf4383d1192dfb6/classes?populate=full\n\n"
                "Use /help for more information."
            )

# Keep-alive mechanism for Render
def keep_alive():
    def ping_server():
        while True:
            try:
                logger.info("Bot is alive and running...")
                time.sleep(300)  # Ping every 5 minutes
            except Exception as e:
                logger.error(f"Keep-alive error: {e}")
                
    thread = threading.Thread(target=ping_server, daemon=True)
    thread.start()

def main():
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
    
    logger.info("Course Data Bot is starting...")
    bot.application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
