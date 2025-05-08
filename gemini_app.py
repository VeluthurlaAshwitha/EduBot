from flask import Flask, render_template, request, jsonify
import os
from dotenv import load_dotenv
import traceback
import sys
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("gemini_app.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Configure Gemini client
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    logger.error("No Gemini API key found. Please set GEMINI_API_KEY in your .env file.")
    logger.info("You can create a .env file with the content: GEMINI_API_KEY=your_api_key_here")

gemini_available = False
model = None

try:
    # Try importing the library and configuring the API
    import google.generativeai as genai
    genai.configure(api_key=GEMINI_API_KEY)
    # Use the current supported model version
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    # Test the model with a simple query to verify it works
    test_response = model.generate_content("Hello")
    if test_response and hasattr(test_response, 'text'):
        logger.info("Gemini API configured and tested successfully!")
        gemini_available = True
    else:
        logger.error("Gemini API configuration test failed.")
        gemini_available = False
except ImportError:
    logger.error("The google-generativeai package is not installed.")
    logger.info("Please install it with: pip install google-generativeai")
except Exception as e:
    logger.error(f"Error configuring Gemini API: {e}")
    logger.error(traceback.format_exc())

# Basic chatbot fallback responses
def get_basic_response(user_input):
    user_input = user_input.lower()
    
    if "hi" in user_input or "hello" in user_input:
        return "Hello! How can I assist you today?"
    elif "course" in user_input:
        return "We offer various courses including Computer Science, Engineering, Business, and Arts. What specific course are you interested in?"
    elif "fee" in user_input or "tuition" in user_input:
        return "Our tuition fees vary by program. Undergraduate programs range from $10,000 to $25,000 per year. Would you like information about a specific program?"
    elif "scholarship" in user_input:
        return "We offer merit-based and need-based scholarships. Applications open three months before the academic year starts."
    elif "hostel" in user_input or "accommodation" in user_input:
        return "We have on-campus accommodation with single and shared rooms. Facilities include Wi-Fi, laundry, and 24/7 security."
    elif "library" in user_input:
        return "Our library is open 24/7 and contains over 100,000 books and digital resources. Students can borrow up to 5 books at a time."
    elif "sport" in user_input:
        return "We have facilities for basketball, tennis, swimming, and a fully-equipped gym. There are also various sports clubs you can join."
    elif "admission" in user_input:
        return "Admissions for the next academic year are currently open. You can apply online through our admissions portal."
    else:
        return "I'm here to help with any questions about our university. Feel free to ask about courses, admissions, facilities, or student life."

@app.route('/')
def home():
    return render_template('gemini_chat_simple.html')

@app.route('/gemini-chat')
def gemini_chat():
    return render_template('gemini_chat.html')

@app.route('/gemini-simple-chat')
def gemini_simple_chat():
    return render_template('gemini_chat_simple.html')

@app.route('/api/gemini-chat', methods=['POST'])
def gemini_chat_api():
    try:
        # Handle both JSON and form data
        if request.is_json:
            user_message = request.json.get('message', '')
        else:
            user_message = request.form.get('message', '')

        if not user_message:
            return jsonify({"error": "No message provided"}), 400

        # Log the incoming message
        logger.info(f"Received message: {user_message[:50]}..." if len(user_message) > 50 else f"Received message: {user_message}")

        # Check if Gemini API is available
        if not GEMINI_API_KEY or not gemini_available or not model:
            # Fallback to basic chatbot
            fallback_response = get_basic_response(user_message)
            logger.warning("Using fallback response because Gemini is not available")
            return jsonify({
                "message": f"Sorry, the AI assistant is currently unavailable. Using basic chatbot instead.\n\n{fallback_response}",
                "status": "fallback"
            })

        # Define your custom instruction with more university context
        custom_prompt = (
            "You are a helpful university assistant named EduBot that provides clear and simple explanations with practical examples whenever possible.\n"
            "You are specially trained to answer questions about university topics including:\n"
            "- Courses, programs, admissions, fees, and scholarships\n"
            "- Campus facilities like hostels, libraries, sports facilities, and food options\n"
            "- Academic matters like timetables, exams, and results\n"
            "- Student services like ID cards, transportation, and healthcare\n"
            "If the user asks about specific details you don't know for certain, ask for clarification instead of making assumptions.\n"
            "Keep your responses conversational, helpful, and focused on university-related topics.\n\n"
            f"User: {user_message}"
        )

        # Generate response using Gemini
        response = model.generate_content(custom_prompt)
        
        if not response or not hasattr(response, 'text'):
            raise Exception("Invalid response from Gemini API")
            
        assistant_message = response.text
        logger.info(f"Generated response (first 50 chars): {assistant_message[:50]}...")

        # Log the conversation
        try:
            with open("gemini_log.txt", "a", encoding="utf-8") as log_file:
                log_file.write(f"User: {user_message}\nAI: {assistant_message}\n---\n")
        except Exception as log_error:
            logger.error(f"Error writing to log file: {log_error}")

        return jsonify({
            "message": assistant_message,
            "status": "success"
        })

    except Exception as e:
        error_details = traceback.format_exc()
        logger.error(f"ERROR TYPE: {type(e).__name__}")
        logger.error(f"ERROR DETAILS: {str(e)}")
        logger.error(f"TRACEBACK: {error_details}")
        
        # Fallback to basic chatbot with error details
        fallback_response = get_basic_response(user_message)
        
        return jsonify({
            "message": f"Sorry, I encountered an error: {str(e)}. Using basic chatbot instead.\n\n{fallback_response}",
            "status": "error"
        })

if __name__ == '__main__':
    # Make sure templates and static directories exist
    if not os.path.exists("templates"):
        os.makedirs("templates")
        logger.info("Created templates directory")
        
    if not os.path.exists("static"):
        os.makedirs("static")
        logger.info("Created static directory")
        
    # Check if we have the required files
    required_templates = ["gemini_chat.html", "gemini_chat_simple.html"]
    for template in required_templates:
        template_path = os.path.join("templates", template)
        if not os.path.exists(template_path):
            logger.warning(f"{template} not found in templates directory!")
            
    # Print instructions for setting up the Gemini API key
    if not GEMINI_API_KEY:
        print("\n==== IMPORTANT ====")
        print("To use the Gemini AI bot, you need to:")
        print("1. Get a Gemini API key from Google AI Studio (https://ai.google.dev/)")
        print("2. Create a .env file in the same directory as this script")
        print("3. Add the line: GEMINI_API_KEY=your_api_key_here")
        print("===================\n")
            
    app.run(port=5001, debug=True)
