import mysql.connector
import json
import os
import re
from functools import wraps

from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "change-this-secret-key-before-deployment")

UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

STYLE_MAP = {
    "V": "Visual",
    "A": "Auditory",
    "R": "Reading/Writing",
    "K": "Kinesthetic"
}

def get_db_connection():
    return mysql.connector.connect(
        host=os.environ.get("DB_HOST"),
        port=int(os.environ.get("DB_PORT", 3306)),
        user=os.environ.get("DB_USER"),
        password=os.environ.get("DB_PASSWORD"),
        database=os.environ.get("DB_NAME")
    )


def convert_to_embed(url):
    match = re.search(r"v=([^&]+)", url)
    if match:
        return f"https://www.youtube.com/embed/{match.group(1)}"

    match = re.search(r"youtu\.be/([^?&]+)", url)
    if match:
        return f"https://www.youtube.com/embed/{match.group(1)}"

    return url


def build_k_case_json(form):
    correct_answer = form.get("k_correct_answer", "").strip().upper()
    if correct_answer not in ["A", "B", "C", "D"]:
        correct_answer = ""

    case_data = {
        "scenario": form.get("k_scenario", "").strip(),
        "question": form.get("k_question", "").strip(),
        "option_a": form.get("k_option_a", "").strip(),
        "option_b": form.get("k_option_b", "").strip(),
        "option_c": form.get("k_option_c", "").strip(),
        "option_d": form.get("k_option_d", "").strip(),
        "correct_answer": correct_answer
    }
    return json.dumps(case_data)


def parse_k_case_json(content):
    try:
        return json.loads(content) if content else None
    except Exception:
        return None


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in to access this page.", "error")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            flash("Please log in as admin to access this page.", "error")
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function


def initialize_progress_flags():
    session.setdefault('subject_done', False)
    session.setdefault('preassessment_done', False)
    session.setdefault('style_done', False)
    session.setdefault('module_done', False)
    session.setdefault('assessment_done', False)
    session.setdefault('result_done', False)


def get_subject_id_by_name(module_name):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id FROM subjects WHERE module_name = %s", (module_name,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    return row["id"] if row else None


def get_current_subject_id():
    module_name = session.get("module_name")
    if not module_name:
        return None
    return get_subject_id_by_name(module_name)


def ensure_module_progress(user_id, subject_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO module_progress (user_id, subject_id)
        VALUES (%s, %s)
        ON DUPLICATE KEY UPDATE user_id = VALUES(user_id)
    """, (user_id, subject_id))
    conn.commit()
    cursor.close()
    conn.close()


def get_module_progress_row(user_id, subject_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT *
        FROM module_progress
        WHERE user_id = %s AND subject_id = %s
    """, (user_id, subject_id))
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    return row


def sync_progress_flags(user_id=None):
    initialize_progress_flags()

    if not user_id:
        user_id = session.get('user_id')
    if not user_id:
        return

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT learning_style FROM students WHERE user_id=%s", (user_id,))
        student = cursor.fetchone()

        if student and student.get('learning_style'):
            session['learning_style'] = student['learning_style']
            session['learning_style_full'] = STYLE_MAP.get(student['learning_style'])
            session['style_done'] = True
        else:
            session['style_done'] = False

        subject_id = get_current_subject_id()

        if subject_id:
            cursor.execute("""
                SELECT *
                FROM module_progress
                WHERE user_id = %s AND subject_id = %s
            """, (user_id, subject_id))
            progress = cursor.fetchone()

            session['subject_done'] = True
            session['preassessment_done'] = bool(progress and progress.get('pre_score') is not None)
            session['module_done'] = bool(progress and progress.get('completed_content') == 1)
            session['assessment_done'] = bool(progress and progress.get('final_score') is not None)
            session['result_done'] = bool(progress and progress.get('final_score') is not None)
        else:
            session['subject_done'] = False
            session['preassessment_done'] = False
            session['module_done'] = False
            session['assessment_done'] = False
            session['result_done'] = False

        cursor.close()
        conn.close()

    except Exception:
        pass


@app.route('/')
def home():
    sync_progress_flags()
    return render_template('home.html')


@app.route('/index')
def legacy_index():
    return redirect(url_for('home'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email'].strip()
        first_name = request.form['first_name'].strip()
        last_name = request.form['last_name'].strip()
        password = request.form['password']
        confirm_password = request.form.get('confirm_password', '')

        if not email or not first_name or not last_name or not password or not confirm_password:
            flash("Please fill in all fields.", "error")
            return redirect(url_for('register'))

        if password != confirm_password:
            flash("Password and confirm password do not match.", "error")
            return redirect(url_for('register'))

        if len(password) < 6:
            flash("Password must be at least 6 characters long.", "error")
            return redirect(url_for('register'))

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id FROM users WHERE email=%s", (email,))
        existing_user = cursor.fetchone()

        if existing_user:
            cursor.close()
            conn.close()
            flash("This email is already registered. Please login instead.", "error")
            return redirect(url_for('register'))

        cursor.close()
        cursor = conn.cursor()

        hashed_password = generate_password_hash(password)

        cursor.execute("""
            INSERT INTO users (email, first_name, last_name, password)
            VALUES (%s, %s, %s, %s)
        """, (email, first_name, last_name, hashed_password))

        user_id = cursor.lastrowid

        cursor.execute("""
            INSERT INTO students (user_id)
            VALUES (%s)
        """, (user_id,))

        conn.commit()
        cursor.close()
        conn.close()

        flash("Registration successful! Please login.", "success")
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email'].strip()
        password = request.form['password']
        next_url = request.args.get('next') or request.form.get('next')

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE email=%s", (email,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if user and check_password_hash(user['password'], password):
            session.clear()
            session['user_id'] = user['id']
            session['email'] = user['email']
            session['user_name'] = user['first_name']
            initialize_progress_flags()
            sync_progress_flags(user['id'])

            flash("Login successful!", "success")
            return redirect(next_url or url_for('home'))

        flash("Invalid email or password", "error")
        return redirect(url_for('login'))

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out successfully.", "success")
    return redirect(url_for('home'))


@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM admin WHERE username = %s", (username,))
        admin = cursor.fetchone()
        cursor.close()
        conn.close()

        if admin and check_password_hash(admin['password'], password):
            session.clear()
            session['admin_logged_in'] = True
            session['admin_id'] = admin['admin_id']
            session['admin_username'] = admin['username']
            session['admin_email'] = admin['email']

            flash("Admin login successful!", "success")
            return redirect(url_for('admin_home'))

        flash("Invalid admin username or password.", "error")
        return redirect(url_for('admin_login'))

    return render_template('admin_login.html')


@app.route('/subject')
@login_required
def subject():
    user_id = session.get("user_id")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT 
            s.id,
            s.module_name,
            s.module_description,
            mp.pre_score,
            mp.final_score,
            mp.completed_content,
            mp.completed_at
        FROM subjects s
        LEFT JOIN module_progress mp
            ON s.id = mp.subject_id AND mp.user_id = %s
        ORDER BY s.id ASC
    """, (user_id,))
    subjects = cursor.fetchall()

    for s in subjects:
        if s["final_score"] is not None:
            s["status"] = "Completed"
        elif s["pre_score"] is not None or s["completed_content"] == 1:
            s["status"] = "In Progress"
        else:
            s["status"] = "Not Started"

    cursor.close()
    conn.close()

    return render_template('subject.html', modules=subjects)


@app.route('/module/<module_name>')
@login_required
def module(module_name):
    user_id = session.get("user_id")
    subject_id = get_subject_id_by_name(module_name)

    if not subject_id:
        flash("Module not found.", "error")
        return redirect(url_for("subject"))

    progress = get_module_progress_row(user_id, subject_id)

    if progress and progress.get("final_score") is not None:
        flash("You already completed this module. You can view the result, but cannot redo it.", "error")
        session["module_name"] = module_name
        sync_progress_flags(user_id)
        return redirect(url_for("result"))

    session['module_name'] = module_name
    session['subject_done'] = True

    ensure_module_progress(user_id, subject_id)
    sync_progress_flags(user_id)

    return redirect(url_for('pre_assessment', module_name=module_name))


@app.route('/pre_assessment', defaults={'module_name': None})
@app.route('/pre_assessment/<module_name>')
@login_required
def pre_assessment(module_name=None):
    user_id = session.get("user_id")
    module_name = module_name or session.get('module_name')

    if not module_name:
        flash("Please choose a module first.", "error")
        return redirect(url_for('subject'))

    subject_id = get_subject_id_by_name(module_name)
    if not subject_id:
        flash("Module not found.", "error")
        return redirect(url_for("subject"))

    progress = get_module_progress_row(user_id, subject_id)
    if progress and progress.get("pre_score") is not None:
        flash("Pre-assessment already completed for this module.", "error")
        session["module_name"] = module_name
        sync_progress_flags(user_id)
        return redirect(url_for("learning_style"))

    session['module_name'] = module_name
    session['subject_done'] = True
    ensure_module_progress(user_id, subject_id)

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT q.id, q.question_text, q.question_type,
               q.option_a, q.option_b, q.option_c, q.option_d,
               q.correct_answer
        FROM questions q
        JOIN subjects s ON q.subject_id = s.id
        WHERE s.module_name = %s AND q.assessment_type = 'pre'
    """, (module_name,))

    questions = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template('pre_assessment.html', questions=questions, module_name=module_name)


@app.route('/save_pre_assessment', methods=['POST'])
@login_required
def save_pre_assessment():
    data = request.get_json()
    pre_score = data.get('pre_score')
    user_id = session.get('user_id')
    subject_id = get_current_subject_id()

    if not user_id or not subject_id:
        return jsonify({"message": "User or module missing"}), 400

    ensure_module_progress(user_id, subject_id)

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE module_progress
        SET pre_score = %s
        WHERE user_id = %s AND subject_id = %s
    """, (pre_score, user_id, subject_id))
    conn.commit()
    cursor.close()
    conn.close()

    session['preassessment_done'] = True
    return jsonify({"message": "Pre-assessment saved!"})


@app.route('/learning_style')
@login_required
def learning_style():
    user_id = session.get("user_id")
    subject_id = get_current_subject_id()

    if not subject_id:
        flash("Please choose a module first.", "error")
        return redirect(url_for("subject"))

    progress = get_module_progress_row(user_id, subject_id)
    if not progress or progress.get("pre_score") is None:
        flash("Please complete pre-assessment first.", "error")
        return redirect(url_for("pre_assessment"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT learning_style
        FROM module_progress
        WHERE user_id = %s AND subject_id = %s
    """, (user_id, subject_id))
    progress_row = cursor.fetchone()

    cursor.execute("""
        SELECT learning_style
        FROM students
        WHERE user_id = %s
    """, (user_id,))
    student_row = cursor.fetchone()

    style_info = {
        "V": {
            "icon": "👁️",
            "title": "Visual Learner",
            "description": "You usually learn better through diagrams, charts, images, and visual examples.",
            "preferred_content": "Visual materials such as slide notes, diagrams and illustrated content"
        },
        "A": {
            "icon": "🎧",
            "title": "Auditory Learner",
            "description": "You usually learn better through listening, discussion, and spoken explanation.",
            "preferred_content": "Audio or video-based learning materials"
        },
        "R": {
            "icon": "📘",
            "title": "Reading/Writing Learner",
            "description": "You usually learn better through reading and writing, such as notes, text explanations, and guides.",
            "preferred_content": "Text-rich materials such as notes, articles and written explanations"
        },
        "K": {
            "icon": "🛠️",
            "title": "Kinesthetic Learner",
            "description": "You usually learn better through practice, hands-on activities, and learning by doing.",
            "preferred_content": "Practical tasks, activities and interactive learning content"
        }
    }

    if progress_row and progress_row.get("learning_style"):
        saved_style = progress_row["learning_style"]
        saved_style_full = STYLE_MAP.get(saved_style, saved_style)
        info = style_info.get(saved_style, {})

        session['learning_style'] = saved_style
        session['learning_style_full'] = saved_style_full
        session['style_done'] = True

        cursor.close()
        conn.close()

        return render_template(
            'learning_style.html',
            locked=True,
            saved_style=saved_style,
            saved_style_full=saved_style_full,
            saved_icon=info.get("icon", "🎓"),
            saved_description=info.get("description", ""),
            preferred_content=info.get("preferred_content", "")
        )

    if student_row and student_row.get("learning_style"):
        saved_style = student_row["learning_style"]

        cursor2 = conn.cursor()
        cursor2.execute("""
            UPDATE module_progress
            SET learning_style = %s
            WHERE user_id = %s AND subject_id = %s
        """, (saved_style, user_id, subject_id))
        conn.commit()
        cursor2.close()

        saved_style_full = STYLE_MAP.get(saved_style, saved_style)
        info = style_info.get(saved_style, {})

        session['learning_style'] = saved_style
        session['learning_style_full'] = saved_style_full
        session['style_done'] = True

        cursor.close()
        conn.close()

        return render_template(
            'learning_style.html',
            locked=True,
            saved_style=saved_style,
            saved_style_full=saved_style_full,
            saved_icon=info.get("icon", "🎓"),
            saved_description=info.get("description", ""),
            preferred_content=info.get("preferred_content", "")
        )

    cursor.close()
    conn.close()

    return render_template(
        'learning_style.html',
        locked=False
    )


@app.route('/save_learning_style', methods=['POST'])
@login_required
def save_learning_style():
    data = request.get_json()
    learning_style = data.get('learningStyle', '').upper().strip()

    style_map = {
        "VISUAL": "V",
        "AUDITORY": "A",
        "READING/WRITING": "R",
        "KINESTHETIC": "K",
        "V": "V",
        "A": "A",
        "R": "R",
        "K": "K"
    }

    normalized_style = style_map.get(learning_style, "")
    if not normalized_style:
        return jsonify({"message": "Invalid style"}), 400

    user_id = session.get('user_id')
    subject_id = get_current_subject_id()

    if not user_id or not subject_id:
        return jsonify({"message": "User or module missing"}), 400

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT learning_style
        FROM module_progress
        WHERE user_id = %s AND subject_id = %s
    """, (user_id, subject_id))
    existing_progress = cursor.fetchone()

    if existing_progress and existing_progress.get("learning_style"):
        cursor.close()
        conn.close()
        return jsonify({"message": "Learning style already saved. This step is locked."}), 400

    cursor.close()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE students
        SET learning_style = %s
        WHERE user_id = %s
    """, (normalized_style, user_id))

    cursor.execute("""
        UPDATE module_progress
        SET learning_style = %s
        WHERE user_id = %s AND subject_id = %s
    """, (normalized_style, user_id, subject_id))

    conn.commit()
    cursor.close()
    conn.close()

    session['learning_style'] = normalized_style
    session['learning_style_full'] = STYLE_MAP.get(normalized_style)
    session['style_done'] = True

    return jsonify({"message": "Learning style saved!"})


@app.route('/content', defaults={'module_name': None})
@app.route('/content/<module_name>')
@login_required
def content(module_name=None):
    user_id = session.get("user_id")

    if module_name:
        session['module_name'] = module_name

    module_name = session.get('module_name')
    learning_style = session.get('learning_style')

    if not module_name:
        flash("Please choose a module first.", "error")
        return redirect(url_for('subject'))

    if not learning_style:
        flash("Please complete your learning style first.", "error")
        return redirect(url_for('learning_style'))

    subject_id = get_subject_id_by_name(module_name)
    progress = get_module_progress_row(user_id, subject_id)

    if progress and progress.get("final_score") is not None:
        flash("You already completed this module.", "error")
        return redirect(url_for("result"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if learning_style == "K":
        cursor.execute("""
            SELECT lm.*, s.module_name
            FROM learning_materials lm
            JOIN subjects s ON lm.subject_id = s.id
            WHERE s.module_name = %s
              AND lm.learning_style = %s
              AND lm.material_type IN ('text', 'k_case')
            ORDER BY lm.id ASC
        """, (module_name, learning_style))
    else:
        style_material_map = {
            "V": "pdf",
            "A": "video",
            "R": "pdf"
        }
        material_type = style_material_map.get(learning_style)

        cursor.execute("""
            SELECT lm.*, s.module_name
            FROM learning_materials lm
            JOIN subjects s ON lm.subject_id = s.id
            WHERE s.module_name = %s
              AND lm.material_type = %s
              AND lm.learning_style = %s
        """, (module_name, material_type, learning_style))

    materials = cursor.fetchall()

    for material in materials:
        if material['material_type'] == 'k_case':
            material['case_data'] = parse_k_case_json(material['content'])
        else:
            material['case_data'] = None

    cursor.close()
    conn.close()

    return render_template(
        'content.html',
        materials=materials,
        learning_style=learning_style,
        module_name=module_name
    )


@app.route('/mark_content_complete', methods=['POST'])
@login_required
def mark_content_complete():
    user_id = session.get("user_id")
    subject_id = get_current_subject_id()

    if not user_id or not subject_id:
        return jsonify({"message": "User or module missing"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE module_progress
        SET completed_content = 1
        WHERE user_id = %s AND subject_id = %s
    """, (user_id, subject_id))
    conn.commit()
    cursor.close()
    conn.close()

    session["module_done"] = True
    return jsonify({"message": "Content marked complete!"})


@app.route('/final_assessment', defaults={'module_name': None})
@app.route('/final_assessment/<module_name>')
@login_required
def final_assessment(module_name=None):
    user_id = session.get("user_id")
    module_name = module_name or session.get('module_name')

    if not module_name:
        flash("Please choose a module first.", "error")
        return redirect(url_for('subject'))

    subject_id = get_subject_id_by_name(module_name)
    progress = get_module_progress_row(user_id, subject_id)

    if not progress or progress.get("completed_content") != 1:
        flash("Please complete the learning content first.", "error")
        return redirect(url_for("content"))

    if progress.get("final_score") is not None:
        flash("Final assessment already completed for this module.", "error")
        return redirect(url_for("result"))

    session['module_name'] = module_name

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT q.id, q.question_text, q.question_type,
               q.option_a, q.option_b, q.option_c, q.option_d,
               q.correct_answer
        FROM questions q
        JOIN subjects s ON q.subject_id = s.id
        WHERE s.module_name = %s AND q.assessment_type = 'final'
    """, (module_name,))

    questions = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template('final_assessment.html', questions=questions, module_name=module_name)


@app.route('/save_final_assessment', methods=['POST'])
@login_required
def save_final_assessment():
    data = request.get_json()
    final_score = data.get('final_score')
    user_id = session.get('user_id')
    subject_id = get_current_subject_id()

    if not user_id or not subject_id:
        return jsonify({"message": "User or module missing"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE module_progress
        SET final_score = %s,
            completed_at = CURRENT_TIMESTAMP
        WHERE user_id = %s AND subject_id = %s
    """, (final_score, user_id, subject_id))
    conn.commit()
    cursor.close()
    conn.close()

    session['assessment_done'] = True
    session['result_done'] = True

    return jsonify({"message": "Final assessment saved!"})


@app.route('/result')
@login_required
def result():
    user_id = session.get('user_id')
    subject_id = get_current_subject_id()

    if not subject_id:
        flash("Please choose a module first.", "error")
        return redirect(url_for("subject"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT s.module_name, mp.pre_score, mp.final_score
        FROM module_progress mp
        JOIN subjects s ON mp.subject_id = s.id
        WHERE mp.user_id = %s AND mp.subject_id = %s
    """, (user_id, subject_id))

    data = cursor.fetchone()
    cursor.close()
    conn.close()

    if not data:
        flash("No result found for this module.", "error")
        return redirect(url_for("subject"))

    pre_score = data['pre_score'] if data['pre_score'] is not None else 0
    final_score = data['final_score'] if data['final_score'] is not None else 0
    improvement = final_score - pre_score

    session['result_done'] = data['final_score'] is not None

    return render_template(
        "result.html",
        module_name=data["module_name"],
        pre_score=pre_score,
        final_score=final_score,
        improvement=improvement
    )


@app.route('/feedback')
@login_required
def feedback():
    module_name = session.get('module_name')
    if not module_name:
        flash("Please choose a module first.", "error")
        return redirect(url_for("subject"))
    return render_template("feedback.html", module_name=module_name)


@app.route('/save_feedback', methods=['POST'])
@login_required
def save_feedback():
    data = request.get_json()

    module_name = data.get('module_name') or session.get('module_name')
    helpfulness = data.get('helpfulness_score')
    recommend = data.get('recommend_score')
    comments = (data.get('comments') or "").strip()

    if not module_name:
        return jsonify({"message": "Module name missing"}), 400

    if not comments:
        return jsonify({"message": "Comment is required"}), 400

    user_id = session.get('user_id')
    subject_id = get_subject_id_by_name(module_name)

    if not user_id or not subject_id:
        return jsonify({"message": "User or module missing"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE module_progress
        SET helpfulness_score = %s,
            recommend_score = %s,
            comments = %s
        WHERE user_id = %s AND subject_id = %s
    """, (helpfulness, recommend, comments, user_id, subject_id))

    cursor.execute("""
        INSERT INTO feedback (user_id, module_name, helpfulness_score, recommend_score, comments)
        VALUES (%s, %s, %s, %s, %s)
    """, (user_id, module_name, helpfulness, recommend, comments))

    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({"message": "Feedback saved!"})


@app.route('/recommend')
@login_required
def recommend():
    user_id = session.get('user_id')
    current_module = session.get('module_name')
    chosen_style = session.get('learning_style')

    if not chosen_style:
        flash("Please complete your learning style first.", "error")
        return redirect(url_for('learning_style'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT DISTINCT module_name
        FROM feedback
        WHERE user_id = %s
    """, (user_id,))
    done_modules = {row["module_name"] for row in cursor.fetchall()}

    cursor.execute("""
        SELECT f.module_name,
               AVG(f.recommend_score) AS avg_rating,
               COUNT(*) AS total_votes,
               s.module_description
        FROM feedback f
        JOIN students st ON f.user_id = st.user_id
        JOIN subjects s ON f.module_name = s.module_name
        WHERE st.learning_style = %s
          AND f.recommend_score IS NOT NULL
        GROUP BY f.module_name, s.module_description
        HAVING COUNT(*) > 0
        ORDER BY avg_rating DESC, total_votes DESC
    """, (chosen_style,))

    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    recommended_modules = []
    for row in rows:
        if row["module_name"] == current_module:
            continue
        if row["module_name"] in done_modules:
            continue
        recommended_modules.append(row)

    recommended_modules = recommended_modules[:5]

    return render_template("recommended_module.html", recommended_modules=recommended_modules)


@app.route('/recommended_module')
@login_required
def recommended_module():
    return redirect(url_for('recommend'))


@app.route('/modules')
@login_required
def modules():
    return redirect(url_for('subject'))


@app.route('/assessment')
@login_required
def assessment():
    module_name = session.get('module_name')
    if not module_name:
        flash("Please choose a module first.", "error")
        return redirect(url_for('subject'))
    return redirect(url_for('final_assessment', module_name=module_name))


@app.route('/results')
@login_required
def results():
    return redirect(url_for('result'))


# -----------------------------
# ADMIN DASHBOARD
# -----------------------------
@app.route('/admin_home')
@admin_required
def admin_home():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT 
            AVG(pre_score) AS avg_pre,
            AVG(final_score) AS avg_final,
            AVG(final_score - pre_score) AS avg_improvement
        FROM module_progress
        WHERE pre_score IS NOT NULL AND final_score IS NOT NULL
    """)
    performance = cursor.fetchone()

    if not performance or performance['avg_pre'] is None:
        performance = {
            'avg_pre': 0,
            'avg_final': 0,
            'avg_improvement': 0,
            'avg_pre_pct': 0,
            'avg_final_pct': 0,
            'avg_improvement_pct': 0
        }
    else:
        performance['avg_pre_pct'] = (performance['avg_pre'] / 5) * 100
        performance['avg_final_pct'] = (performance['avg_final'] / 5) * 100
        performance['avg_improvement_pct'] = (performance['avg_improvement'] / 5) * 100

    cursor.execute("SELECT COUNT(*) AS total_students FROM students")
    total_students = cursor.fetchone()['total_students']

    cursor.execute("SELECT COUNT(*) AS total_modules FROM subjects")
    total_modules = cursor.fetchone()['total_modules']

    cursor.execute("""
        SELECT 
            CASE
                WHEN final_score <= 2 THEN 'Low'
                WHEN final_score <= 4 THEN 'Medium'
                ELSE 'High'
            END AS category,
            COUNT(*) AS count
        FROM module_progress
        WHERE final_score IS NOT NULL
        GROUP BY category
    """)
    score_distribution = cursor.fetchall() or []

    cursor.execute("""
        SELECT 
            CASE
                WHEN learning_style = 'V' THEN 'Visual'
                WHEN learning_style = 'A' THEN 'Auditory'
                WHEN learning_style = 'R' THEN 'Reading/Writing'
                WHEN learning_style = 'K' THEN 'Kinesthetic'
                ELSE 'Unknown'
            END AS learning_style,
            COUNT(*) AS count
        FROM students
        GROUP BY learning_style
        ORDER BY count DESC
    """)
    learning_styles = cursor.fetchall() or []

    cursor.execute("""
        SELECT module_name, COUNT(*) AS rec_count
        FROM feedback
        WHERE recommend_score >= 4
        GROUP BY module_name
        ORDER BY rec_count DESC
        LIMIT 5
    """)
    recommendations = cursor.fetchall() or []

    top_recommended_module = recommendations[0]['module_name'] if recommendations else "No data"
    top_learning_style = learning_styles[0]['learning_style'] if learning_styles else "No data"

    summary_points = []
    if performance['avg_final'] > performance['avg_pre']:
        summary_points.append(
            f"Students improved by an average of {performance['avg_improvement']:.2f} marks ({performance['avg_improvement_pct']:.1f}%)."
        )
    else:
        summary_points.append("No positive improvement trend is currently visible in the assessment data.")

    summary_points.append(f"The most common learning style is {top_learning_style}.")
    summary_points.append(f"The most recommended module is {top_recommended_module}.")
    summary_points.append(f"The system currently has {total_students} registered student profiles.")

    cursor.close()
    conn.close()

    return render_template(
        'admin_home.html',
        performance=performance,
        total_students=total_students,
        total_modules=total_modules,
        score_distribution=score_distribution,
        learning_styles=learning_styles,
        recommendations=recommendations,
        top_recommended_module=top_recommended_module,
        summary_points=summary_points
    )


# -----------------------------
# ADMIN MODULE
# -----------------------------
@app.route('/admin_add_module', methods=['GET', 'POST'])
@admin_required
def admin_add_module():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        module_name = request.form['module_name'].strip()
        module_description = request.form['module_description'].strip()

        cursor.execute("""
            INSERT INTO subjects (module_name, module_description)
            VALUES (%s, %s)
        """, (module_name, module_description))

        conn.commit()
        flash("Module added successfully!", "success")
        return redirect(url_for('admin_add_module'))

    cursor.execute("SELECT * FROM subjects ORDER BY id ASC")
    modules = cursor.fetchall()

    cursor.close()
    conn.close()
    return render_template('admin_add_module.html', modules=modules)


@app.route('/delete_module/<int:module_id>')
@admin_required
def delete_module(module_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM subjects WHERE id=%s", (module_id,))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('admin_add_module'))


@app.route('/edit_module/<int:module_id>', methods=['GET', 'POST'])
@admin_required
def edit_module(module_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        module_name = request.form['module_name'].strip()
        module_description = request.form['module_description'].strip()

        cursor.execute("""
            UPDATE subjects
            SET module_name=%s, module_description=%s
            WHERE id=%s
        """, (module_name, module_description, module_id))

        conn.commit()
        cursor.close()
        conn.close()
        return redirect(url_for('admin_add_module'))

    cursor.execute("SELECT * FROM subjects WHERE id=%s", (module_id,))
    module = cursor.fetchone()

    cursor.close()
    conn.close()
    return render_template("admin_edit_module.html", module=module)


# -----------------------------
# ADMIN QUESTION
# -----------------------------
@app.route('/admin_add_question', methods=['GET', 'POST'])
@admin_required
def admin_add_question():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT id, module_name FROM subjects")
    modules = cursor.fetchall()

    if request.method == 'POST':
        subject_id = request.form['subject_id']
        assessment_type = request.form['assessment_type']
        question_text = request.form['question_text'].strip()
        correct_answer = request.form['correct_answer'].strip().upper()
        question_type = request.form['question_type']

        option_a = request.form.get('option_a', '').strip()
        option_b = request.form.get('option_b', '').strip()
        option_c = request.form.get('option_c', '').strip()
        option_d = request.form.get('option_d', '').strip()

        cursor.execute("""
            INSERT INTO questions
            (subject_id, assessment_type, question_text, correct_answer,
             question_type, option_a, option_b, option_c, option_d)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            subject_id, assessment_type, question_text, correct_answer,
            question_type, option_a, option_b, option_c, option_d
        ))

        conn.commit()
        flash("Question added successfully!", "success")
        return redirect(url_for('admin_add_question'))

    cursor.execute("""
        SELECT q.*, s.module_name
        FROM questions q
        JOIN subjects s ON q.subject_id = s.id
        ORDER BY q.id ASC
    """)
    questions = cursor.fetchall()

    cursor.close()
    conn.close()
    return render_template('admin_add_question.html', modules=modules, questions=questions)


@app.route('/delete_question/<int:question_id>')
@admin_required
def delete_question(question_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM questions WHERE id = %s", (question_id,))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('admin_add_question'))


@app.route('/edit_question/<int:question_id>', methods=['GET', 'POST'])
@admin_required
def edit_question(question_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM subjects")
    modules = cursor.fetchall()

    if request.method == 'POST':
        subject_id = request.form['subject_id']
        assessment_type = request.form['assessment_type']
        question_text = request.form['question_text'].strip()
        correct_answer = request.form['correct_answer'].strip().upper()
        question_type = request.form['question_type']

        option_a = request.form.get('option_a', '').strip()
        option_b = request.form.get('option_b', '').strip()
        option_c = request.form.get('option_c', '').strip()
        option_d = request.form.get('option_d', '').strip()

        cursor.execute("""
            UPDATE questions
            SET subject_id=%s,
                assessment_type=%s,
                question_text=%s,
                correct_answer=%s,
                question_type=%s,
                option_a=%s,
                option_b=%s,
                option_c=%s,
                option_d=%s
            WHERE id=%s
        """, (
            subject_id, assessment_type, question_text, correct_answer,
            question_type, option_a, option_b, option_c, option_d,
            question_id
        ))

        conn.commit()
        cursor.close()
        conn.close()
        return redirect(url_for('admin_add_question'))

    cursor.execute("SELECT * FROM questions WHERE id = %s", (question_id,))
    question = cursor.fetchone()

    cursor.close()
    conn.close()
    return render_template('admin_edit_question.html', question=question, modules=modules)


# -----------------------------
# ADMIN MATERIAL
# -----------------------------
@app.route('/admin/add_material', methods=['GET', 'POST'])
@admin_required
def admin_add_material():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM subjects")
    modules = cursor.fetchall()

    if request.method == 'POST':
        subject_id = request.form['subject_id']
        title = request.form['title'].strip()
        material_type = request.form['material_type']
        learning_style = request.form['learning_style']

        content = None

        if material_type == "text":
            content = request.form.get('content', '').strip()

        elif material_type == "video":
            raw_link = request.form.get('video_link', '').strip()
            content = convert_to_embed(raw_link) if raw_link else None

        elif material_type == "pdf":
            file = request.files.get('pdf_file')
            if file and file.filename != "":
                filename = secure_filename(file.filename)
                os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                content = filepath.replace("\\", "/")

        elif material_type == "k_case":
            content = build_k_case_json(request.form)

        cursor.execute("""
            INSERT INTO learning_materials
            (subject_id, title, material_type, content, learning_style)
            VALUES (%s, %s, %s, %s, %s)
        """, (subject_id, title, material_type, content, learning_style))

        conn.commit()
        flash("Material added successfully!", "success")
        return redirect(url_for('admin_add_material'))

    cursor.execute("""
        SELECT lm.*, s.module_name
        FROM learning_materials lm
        JOIN subjects s ON lm.subject_id = s.id
        ORDER BY lm.id DESC
    """)
    materials = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template("admin_add_material.html", modules=modules, materials=materials)


@app.route('/delete_material/<int:material_id>')
@admin_required
def delete_material(material_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM learning_materials WHERE id = %s", (material_id,))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('admin_add_material'))


@app.route('/edit_material/<int:material_id>', methods=['GET', 'POST'])
@admin_required
def edit_material(material_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM subjects")
    modules = cursor.fetchall()

    cursor.execute("SELECT * FROM learning_materials WHERE id=%s", (material_id,))
    material = cursor.fetchone()

    if request.method == 'POST':
        subject_id = request.form['subject_id']
        title = request.form['title'].strip()
        material_type = request.form['material_type']
        learning_style = request.form['learning_style']

        content = None

        if material_type == "text":
            content = request.form.get('content', '').strip()

        elif material_type == "video":
            raw_link = request.form.get('video_link', '').strip()
            content = convert_to_embed(raw_link) if raw_link else None

        elif material_type == "pdf":
            file = request.files.get('pdf_file')
            if file and file.filename != "":
                filename = secure_filename(file.filename)
                os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                content = filepath.replace("\\", "/")
            else:
                content = material['content']

        elif material_type == "k_case":
            content = build_k_case_json(request.form)

        cursor.execute("""
            UPDATE learning_materials
            SET subject_id=%s,
                title=%s,
                material_type=%s,
                content=%s,
                learning_style=%s
            WHERE id=%s
        """, (subject_id, title, material_type, content, learning_style, material_id))

        conn.commit()
        cursor.close()
        conn.close()

        flash("Material updated successfully!", "success")
        return redirect(url_for('admin_add_material'))

    k_case = None
    if material and material['material_type'] == 'k_case':
        k_case = parse_k_case_json(material['content'])

    cursor.close()
    conn.close()

    return render_template(
        'admin_edit_material.html',
        material=material,
        modules=modules,
        k_case=k_case
    )


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(
        host='0.0.0.0',
        port=port,
        debug=os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    )