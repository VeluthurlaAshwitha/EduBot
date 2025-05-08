from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
import random
import json
import pandas as pd
import os
from dotenv import load_dotenv
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # Change this in production

# Load environment variables for Gemini
load_dotenv()

# Configure Gemini client if API key exists
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
gemini_available = False

if GEMINI_API_KEY:
    try:
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-1.5-flash')
        gemini_available = True
        print("Gemini API configured successfully!")
    except Exception as e:
        print(f"Error configuring Gemini API: {e}")
else:
    print("No Gemini API key found. Basic chatbot will be used.")

# Load intents for basic chatbot
try:
    with open('intents.json') as file:
        intents = json.load(file)
except Exception as e:
    print(f"Error loading intents.json: {e}")
    intents = {"intents": []}

# Load course dataset
def load_courses():
    try:
        return pd.read_csv("courses.csv")
    except Exception as e:
        print("Error loading courses.csv:", e)
        return pd.DataFrame(columns=["course", "category", "description"])

courses_df = load_courses()

# Course recommendation logic
def recommend_courses(user_input):
    user_input = user_input.lower()
    keywords = {
        "technology": ["computer", "software", "ai", "tech", "programming"],
        "business": ["marketing", "finance", "business", "management"],
        "literature": ["english", "language", "poetry", "novel"],
        "science": ["physics", "chemistry", "science", "experiments"],
        "law": ["law", "justice", "legal"]
    }

    matched_category = None
    for category, words in keywords.items():
        if any(word in user_input for word in words):
            matched_category = category
            break

    if matched_category:
        matches = courses_df[courses_df['category'].str.lower() == matched_category]
        if not matches.empty:
            course_list = "\n".join(matches["course"].values)
            return f"Based on your interest in {matched_category.title()}, here are some recommended courses:\n{course_list}"

    return "I couldn't find a matching course. Try describing your interests more clearly!"

# Smart NLP match using pattern and tag similarity
def get_response(user_input):
    user_input_lower = user_input.lower()

    for intent in intents['intents']:
        for pattern in intent['patterns']:
            if pattern.lower() in user_input_lower or user_input_lower in pattern.lower():
                return random.choice(intent['responses'])

        if intent['tag'].lower() in user_input_lower:
            return random.choice(intent['responses'])

    if any(word in user_input_lower for word in ["recommend", "suggest", "interested", "course", "field", "study"]):
        return recommend_courses(user_input)

    return "I'm sorry, I didn't understand that. Can you try again?"

# Initialize database
def init_db():
    conn = sqlite3.connect('students.db')
    c = conn.cursor()
    
    # Create students table if it doesn't exist
    c.execute('''
    CREATE TABLE IF NOT EXISTS students (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT UNIQUE NOT NULL,
        first_name TEXT NOT NULL,
        last_name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        phone TEXT,
        department TEXT,
        semester TEXT,
        password TEXT NOT NULL,
        cgpa REAL DEFAULT 3.5,
        credits INTEGER DEFAULT 60,
        attendance REAL DEFAULT 85.5
    )
    ''')
    
    # Create courses table for sample courses
    c.execute('''
    CREATE TABLE IF NOT EXISTS courses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT NOT NULL,
        name TEXT NOT NULL,
        instructor TEXT NOT NULL,
        grade TEXT
    )
    ''')
    
    # Create student_courses for relationship
    c.execute('''
    CREATE TABLE IF NOT EXISTS student_courses (
        student_id INTEGER,
        course_id INTEGER,
        FOREIGN KEY (student_id) REFERENCES students (id),
        FOREIGN KEY (course_id) REFERENCES courses (id)
    )
    ''')
    
    # Create feedback table
    c.execute('''
    CREATE TABLE IF NOT EXISTS feedback (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT NOT NULL,
        student_id TEXT,
        rating INTEGER NOT NULL,
        feedback_type TEXT,
        message TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    conn.commit()
    conn.close()

# Insert sample data
def insert_sample_data():
    conn = sqlite3.connect('students.db')
    c = conn.cursor()
    
    # Check if sample data exists
    c.execute("SELECT COUNT(*) FROM students")
    count = c.fetchone()[0]
    
    if count == 0:
        # Add sample student
        hashed_password = generate_password_hash('password123')
        c.execute('''
        INSERT INTO students (student_id, first_name, last_name, email, phone, department, semester, password)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', ('STU001', 'John', 'Doe', 'john.doe@example.com', '555-123-4567', 'Computer Science', '3rd', hashed_password))
        
        student_id = c.lastrowid
        
        # Add sample courses
        sample_courses = [
            ('CS101', 'Introduction to Programming', 'Dr. Smith', 'A'),
            ('CS202', 'Data Structures', 'Dr. Johnson', 'B+'),
            ('MATH101', 'Calculus I', 'Prof. Williams', 'A-'),
            ('ENG201', 'Technical Writing', 'Prof. Brown', 'B')
        ]
        
        for course in sample_courses:
            c.execute('''
            INSERT INTO courses (code, name, instructor, grade)
            VALUES (?, ?, ?, ?)
            ''', course)
            
            course_id = c.lastrowid
            
            # Link student to course
            c.execute('''
            INSERT INTO student_courses (student_id, course_id)
            VALUES (?, ?)
            ''', (student_id, course_id))
    
    conn.commit()
    conn.close()

# Get student data with courses
def get_student_with_courses(student_id):
    conn = sqlite3.connect('students.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    # Get student data
    c.execute('''
    SELECT * FROM students WHERE id = ?
    ''', (student_id,))
    
    student = dict(c.fetchone())
    
    # Get student's courses
    c.execute('''
    SELECT c.* FROM courses c
    JOIN student_courses sc ON c.id = sc.course_id
    WHERE sc.student_id = ?
    ''', (student_id,))
    
    courses = [dict(row) for row in c.fetchall()]
    student['courses'] = courses
    student['name'] = f"{student['first_name']} {student['last_name']}"
    
    conn.close()
    return student

# Login required decorator
def login_required(f):
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    
    # Preserve the original function name
    decorated_function.__name__ = f.__name__
    return decorated_function

# Initialize database
@app.before_first_request
def setup_database():
    init_db()
    insert_sample_data()

# Routes for basic chatbot
@app.route("/")
def home():
    return render_template("base.html")

@app.route("/chat")
def chat():
    return render_template("chat.html")

@app.route("/get", methods=["POST"])
def chatbot_response():
    user_message = request.form["msg"]
    response = get_response(user_message)

    with open("user_log.txt", "a") as log_file:
        log_file.write(f"User: {user_message} -> Bot: {response}\n")

    return jsonify({"response": response})

# Routes for Gemini chatbot
@app.route('/gemini-chat')
def gemini_chat():
    return render_template('gemini_chat.html')

@app.route('/api/gemini-chat', methods=['POST'])
def gemini_chat_api():
    user_message = request.json.get('message', '')

    if not user_message:
        return jsonify({"error": "No message provided"}), 400

    # Check if Gemini API is available
    if not gemini_available:
        return jsonify({
            "message": "The AI assistant is currently unavailable. Using basic chatbot instead.\n\n" + get_response(user_message),
            "status": "fallback"
        })

    try:
        # Define your custom instruction
        custom_prompt = (
            "You are a helpful assistant that provides clear and simple explanations with practical examples whenever possible.\n"
            "You are specially trained to answer questions related to University.\n"
            "You can answer questions about: courses, admissions, fees, scholarships, hostel facilities, "
            "library resources, sports facilities, campus facilities, timetables, exam schedules, "
            "results, attendance policies, faculty information, placement opportunities, "
            "internet access, transportation, health services, security measures, certificates, "
            "student ID cards, events, holidays, and graduation requirements.\n"
            "If the user asks about something specific like fees, placements, hostel, or course structure, "
            "first confirm the relevant details before answering (e.g., ask for the specific branch or course).\n"
            "Never assume information without asking.\n"
            "Use simple and conversational language that sounds friendly and helpful.\n\n"
            f"User: {user_message}"
        )

        # Generate response using Gemini
        response = model.generate_content(custom_prompt)
        assistant_message = response.text
        
        # Log the conversation
        with open("gemini_log.txt", "a") as log_file:
            log_file.write(f"User: {user_message} -> AI: {assistant_message[:100]}...\n")

        return jsonify({
            "message": assistant_message,
            "status": "success"
        })

    except Exception as e:
        print(f"ERROR TYPE: {type(e).__name__}")
        print(f"ERROR DETAILS: {str(e)}")
        
        # Fallback to basic chatbot
        fallback_response = get_response(user_message)
        
        return jsonify({
            "message": "Sorry, I encountered an error. Using basic chatbot instead.\n\n" + fallback_response,
            "status": "fallback"
        })

@app.route('/gemini-simple-chat')
def gemini_simple_chat():
    return render_template('gemini_chat_simple.html')


# Student authentication routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        student_id = request.form['student_id']
        password = request.form['password']
        
        conn = sqlite3.connect('students.db')
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        # Find student by ID
        c.execute('SELECT * FROM students WHERE student_id = ?', (student_id,))
        student = c.fetchone()
        
        if student and check_password_hash(student['password'], password):
            # Login successful
            session['user_id'] = student['id']
            session['student_name'] = f"{student['first_name']} {student['last_name']}"
            
            flash('Login successful!', 'success')
            return redirect(url_for('profile'))
        else:
            flash('Invalid student ID or password', 'danger')
        
        conn.close()
    
    return render_template('student_login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        student_id = request.form['student_id']
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        email = request.form['email']
        phone = request.form['phone']
        department = request.form['department']
        semester = request.form['semester']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        
        # Validate form data
        if password != confirm_password:
            flash('Passwords do not match', 'danger')
            return redirect(url_for('register'))
        
        conn = sqlite3.connect('students.db')
        c = conn.cursor()
        
        # Check if student ID already exists
        c.execute('SELECT * FROM students WHERE student_id = ?', (student_id,))
        if c.fetchone():
            flash('Student ID already exists', 'danger')
            return redirect(url_for('register'))
        
        # Check if email already exists
        c.execute('SELECT * FROM students WHERE email = ?', (email,))
        if c.fetchone():
            flash('Email already exists', 'danger')
            return redirect(url_for('register'))
        
        # Hash password
        hashed_password = generate_password_hash(password)
        
        # Insert new student
        c.execute('''
        INSERT INTO students (student_id, first_name, last_name, email, phone, department, semester, password)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (student_id, first_name, last_name, email, phone, department, semester, hashed_password))
        
        conn.commit()
        conn.close()
        
        flash('Registration successful! You can now log in', 'success')
        return redirect(url_for('login'))
    
    return render_template('student_register.html')

@app.route('/profile')
@login_required
def profile():
    student = get_student_with_courses(session['user_id'])
    return render_template('student_profile.html', student=student)

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out', 'success')
    return redirect(url_for('home'))

# Feedback routes
@app.route('/feedback')
def feedback():
    return render_template('feedback.html')

@app.route('/submit-feedback', methods=['POST'])
def submit_feedback():
    try:
        # Get form data
        name = request.form.get('name')
        email = request.form.get('email')
        rating = request.form.get('rating')
        feedback_type = request.form.get('feedback-type')
        message = request.form.get('message')
        
        # Log feedback to a file
        with open('feedback_log.txt', 'a') as f:
            f.write(f"Name: {name}, Email: {email}, Rating: {rating}, Type: {feedback_type}, Message: {message}\n")
        
        # Store in database
        conn = sqlite3.connect('students.db')
        c = conn.cursor()
        c.execute('''
        INSERT INTO feedback (name, email, rating, feedback_type, message)
        VALUES (?, ?, ?, ?, ?)
        ''', (name, email, rating, feedback_type, message))
        conn.commit()
        conn.close()
        
        flash('Thank you for your feedback!', 'success')
        return redirect(url_for('feedback'))
    
    except Exception as e:
        flash(f'An error occurred: {str(e)}', 'error')
        return redirect(url_for('feedback'))

# API endpoint for AJAX feedback submission
@app.route('/api/submit-feedback', methods=['POST'])
def api_submit_feedback():
    try:
        data = request.json
        name = data.get('name')
        email = data.get('email')
        rating = data.get('rating')
        feedback_type = data.get('feedbackType')
        message = data.get('message')
        
        # Log feedback to a file
        with open('feedback_log.txt', 'a') as f:
            f.write(f"Name: {name}, Email: {email}, Rating: {rating}, Type: {feedback_type}, Message: {message}\n")
        
        # Store in database
        conn = sqlite3.connect('students.db')
        c = conn.cursor()
        c.execute('''
        INSERT INTO feedback (name, email, rating, feedback_type, message)
        VALUES (?, ?, ?, ?, ?)
        ''', (name, email, rating, feedback_type, message))
        conn.commit()
        conn.close()
        
        return jsonify({"status": "success", "message": "Feedback submitted successfully"})
    
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    # Make sure templates directory exists
    if not os.path.exists("templates"):
        os.makedirs("templates")
    
    # Make sure static directory exists
    if not os.path.exists("static"):
        os.makedirs("static")
        
    app.run(port=5000, debug=True)
