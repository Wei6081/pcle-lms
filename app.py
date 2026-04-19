import mysql.connector

from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import json
import os
from flask import render_template, request, redirect, url_for
from werkzeug.utils import secure_filename
import re

def convert_to_embed(url):
    # Case 1: youtube watch?v=
    match = re.search(r"v=([^&]+)", url)
    if match:
        video_id = match.group(1)
        return f"https://www.youtube.com/embed/{video_id}"

    # Case 2: youtu.be short link
    match = re.search(r"youtu\.be/([^?&]+)", url)
    if match:
        video_id = match.group(1)
        return f"https://www.youtube.com/embed/{video_id}"

    return url

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "change-this-secret-key-before-deployment")

# --- Database Connection Function (local)---
#def get_db_connection():
#    return mysql.connector.connect(
#        host=os.environ.get("DB_HOST", "localhost"),
#        user=os.environ.get("DB_USER", "root"),
#        password=os.environ.get("DB_PASSWORD", "Mysql@work12"),
#        database=os.environ.get("DB_NAME", "pcle_db")
#    )

# --- Database Connection Function (railway)---
def get_db_connection():
    return mysql.connector.connect(
        host=os.environ.get("DB_HOST"),
        port=int(os.environ.get("DB_PORT", 3306)),
        user=os.environ.get("DB_USER"),
        password=os.environ.get("DB_PASSWORD"),
        database=os.environ.get("DB_NAME")
    )


# Login required
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


def sync_progress_flags(user_id=None):
    initialize_progress_flags()
    if not user_id:
        user_id = session.get('user_id')
    if not user_id:
        return

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        session['subject_done'] = bool(session.get('module_name'))

        cursor.execute("SELECT learning_style FROM students WHERE user_id=%s", (user_id,))
        student = cursor.fetchone()
        if student and student.get('learning_style'):
            session['learning_style'] = student['learning_style']
            session['learning_style_full'] = STYLE_MAP.get(student['learning_style'])
            session['style_done'] = True

        cursor.execute("SELECT pre_score, final_score FROM assessment WHERE user_id=%s", (user_id,))
        assessment_row = cursor.fetchone()
        if assessment_row and assessment_row.get('pre_score') is not None:
            session['preassessment_done'] = True
        if assessment_row and assessment_row.get('final_score') is not None:
            session['assessment_done'] = True
            session['result_done'] = True

        if session.get('module_name') and session.get('learning_style'):
            session['module_done'] = True

        cursor.close()
        conn.close()
    except Exception:
        pass

STYLE_MAP = {
    "V": "Visual",
    "A": "Auditory",
    "R": "Reading/Writing",
    "K": "Kinesthetic"
}

# --- Page Routes ---
#@app.route('/')
#def home():
#    sync_progress_flags()
#    return render_template('home.html')

@app.route('/')
def home():
    return "PCLE LMS is running"

@app.route('/health')
def health():
    return "OK", 200

# LOGIN PAGE
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
        else:
            flash("Invalid email or password", "error")
            return redirect(url_for('login'))

    return render_template('login.html')

# REGISTER PAGE
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

# LOGOUT
@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out successfully.", "success")
    return redirect(url_for('home'))


#@app.route('/index')
#def index():
    #return render_template('index.html')

@app.route('/index')
def legacy_index():
    return redirect(url_for('home'))

# --- Protected Pages ---
#@app.route('/subject')
#@login_required
#def subject():
#    return render_template('subject.html')

#@app.route('/pre_assessment')
#@login_required
#def pre_assessment():
#    module = session.get('module_name')
#    return render_template('pre_assessment.html', module=module)

@app.route('/learning_style')
@login_required
def learning_style():
    return render_template('learning_style.html')

@app.route('/content', defaults={'module_name': None})
@app.route('/content/<module_name>')
@login_required
def content(module_name=None):

    if module_name:
        session['module_name'] = module_name
        session['subject_done'] = True

    module_name = session.get('module_name')
    learning_style = session.get('learning_style')

    if not module_name:
        flash("Please choose a module first.", "error")
        return redirect(url_for('subject'))

    if not learning_style:
        flash("Please complete your learning style first.", "error")
        return redirect(url_for('learning_style'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if learning_style == "K":
        query = """
        SELECT lm.*, s.module_name
        FROM learning_materials lm
        JOIN subjects s ON lm.subject_id = s.id
        WHERE s.module_name = %s
        AND lm.learning_style = %s
        AND lm.material_type IN ('text', 'k_case')
        ORDER BY lm.id ASC
        """
        cursor.execute(query, (module_name, learning_style))
    else:
        style_map = {
            "V": "pdf",
            "A": "video",
            "R": "pdf"
        }

        material_type = style_map.get(learning_style)

        query = """
        SELECT lm.*, s.module_name
        FROM learning_materials lm
        JOIN subjects s ON lm.subject_id = s.id
        WHERE s.module_name = %s
        AND lm.material_type = %s
        AND lm.learning_style = %s
        """
        cursor.execute(query, (module_name, material_type, learning_style))

    materials = cursor.fetchall()

    for material in materials:
        if material['material_type'] == 'k_case':
            material['case_data'] = parse_k_case_json(material['content'])
        else:
            material['case_data'] = None

    cursor.close()
    conn.close()

    session['module_done'] = True

    return render_template(
        'content.html',
        materials=materials,
        learning_style=learning_style,
        module_name=module_name
    )


@app.route('/result')
@login_required
def result():
    user_id = session.get('user_id')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT pre_score, final_score
        FROM assessment
        WHERE user_id = %s
    """, (user_id,))

    data = cursor.fetchone()
    cursor.close()
    conn.close()

    pre_score = data['pre_score'] if data and data['pre_score'] is not None else 0
    final_score = data['final_score'] if data and data['final_score'] is not None else 0
    session['result_done'] = bool(data)

    return render_template(
        "result.html",
        pre_score=pre_score,
        final_score=final_score,
        pre_total=5,
        final_total=5
    )

@app.route('/feedback')
@login_required
def feedback():
    module_name = session.get('module_name')  # current module stored in session
    return render_template("feedback.html", module_name=module_name)

#@app.route('/recommended_module')
#def recommended_module():

#    print("SESSION:", dict(session))


#    chosen_style = session.get('learning_style')

#    if not chosen_style:
#        return render_template(
#            'recommended_module.html',
#            recommended_modules=[]
#        )

    # Normalize styles
#    train_df['Personalised learning styles'] = (
#        train_df['Personalised learning styles']
#        .astype(str)
#        .str.upper()
#        .str.replace(' ', '', regex=True)
#    )

#    users_with_style = train_df[
#        train_df['Personalised learning styles'].str.contains(chosen_style, na=False)
#    ]['Response number']

#    if users_with_style.empty:
#        return render_template(
#            'recommended_module.html',
#            recommended_modules=[]
#        )

    # Pick a representative learner
#    target_user = users_with_style.iloc[0]

    # 🔥 NCF + learner similarity
#    recs = recommend_modules_by_learner(target_user, top_n=5)

#    recommended_modules = [
#        {
#            "name": module,
#            "description": "Recommended based on similar learners"
#        }
#        for module, _ in recs
#    ]

#    return render_template(
#        'recommended_module.html',
#        recommended_modules=recommended_modules
#    )



# --- API: Save Student Info ---
#---@app.route('/save_student', methods=['POST'])
#def save_student():
#    data = request.get_json()

#    student_id = data['studentId']
#    student_name = data['studentName']
#    user_id = session.get('user_id')

#    conn = get_db_connection()
#    cursor = conn.cursor()

#    cursor.execute("""
#        INSERT INTO students (user_id, student_id)
#        VALUES (%s, %s)
#    """, (user_id, student_id))

#    conn.commit()
#    conn.close()

#    return jsonify({"message": "Student saved successfully!"})

# --- API: Module Direct ---
@app.route('/subject')
@login_required
def subject():

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM subjects")
    subjects = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('subject.html', modules=subjects)

@app.route('/module/<module_name>')
@login_required
def module(module_name):

    session['module_name'] = module_name
    session['subject_done'] = True

    return redirect(url_for('pre_assessment', module_name=module_name))

# --- API: Save Learning Style ---
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
    if not user_id:
        return jsonify({"message": "User not logged in"}), 401

    # ✅ STORE BOTH
    session['learning_style'] = normalized_style
    session['learning_style_full'] = STYLE_MAP.get(normalized_style)
    session['style_done'] = True

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE students
        SET learning_style=%s
        WHERE user_id=%s
    """, (normalized_style, user_id))

    conn.commit()
    conn.close()

    return jsonify({"message": "Learning style saved!"})

# --- API: Pre assessment ---
@app.route('/pre_assessment', defaults={'module_name': None})
@app.route('/pre_assessment/<module_name>')
@login_required
def pre_assessment(module_name=None):

    module_name = module_name or session.get('module_name')
    if not module_name:
        flash("Please choose a module first.", "error")
        return redirect(url_for('subject'))

    session['module_name'] = module_name
    session['subject_done'] = True

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    query = """
    SELECT q.id, q.question_text, q.question_type,
        q.option_a, q.option_b, q.option_c, q.option_d,
        q.correct_answer
    FROM questions q
    JOIN subjects s ON q.subject_id = s.id
    WHERE s.module_name = %s AND q.assessment_type = 'pre'
    """

    cursor.execute(query, (module_name,))
    questions = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        'pre_assessment.html',
        questions=questions,
        module_name=module_name
    )

# --- API: Save Pre Assessment score ---

# --- API: Save Pre Assessment score ---
@app.route('/save_pre_assessment', methods=['POST'])
@login_required
def save_pre_assessment():
    data = request.get_json()
    pre_score = data.get('pre_score')
    user_id = session.get('user_id')

    if not user_id:
        return jsonify({"message": "User not logged in"}), 401

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO assessment (user_id, pre_score)
        VALUES (%s, %s)
        ON DUPLICATE KEY UPDATE pre_score = VALUES(pre_score)
    """, (user_id, pre_score))

    conn.commit()
    conn.close()

    session['preassessment_done'] = True

    return jsonify({"message": "Pre-assessment saved!"})

# --- API: Final Assessment --
@app.route('/final_assessment', defaults={'module_name': None})
@app.route('/final_assessment/<module_name>')
@login_required
def final_assessment(module_name=None):

    module_name = module_name or session.get('module_name')
    if not module_name:
        flash("Please choose a module first.", "error")
        return redirect(url_for('subject'))

    session['module_name'] = module_name

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    query = """
    SELECT q.id, q.question_text, q.question_type,
        q.option_a, q.option_b, q.option_c, q.option_d,
        q.correct_answer
    FROM questions q
    JOIN subjects s ON q.subject_id = s.id
    WHERE s.module_name = %s AND q.assessment_type = 'final'
    """

    cursor.execute(query, (module_name,))
    questions = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        'final_assessment.html',
        questions=questions,
        module_name=module_name
    )


# --- API: Save Final Assessment score ---


# --- API: Save Final Assessment score ---
@app.route('/save_final_assessment', methods=['POST'])
@login_required
def save_final_assessment():

    data = request.get_json()
    final_score = data.get('final_score')
    user_id = session.get('user_id')

    if not user_id:
        return jsonify({"message": "User not logged in"}), 401

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO assessment (user_id, final_score)
        VALUES (%s, %s)
        ON DUPLICATE KEY UPDATE final_score = VALUES(final_score)
    """, (user_id, final_score))

    conn.commit()
    conn.close()

    session['assessment_done'] = True
    session['result_done'] = True

    return jsonify({"message": "Final assessment saved!"})


# --- API: Save Feedback ---
@app.route('/save_feedback', methods=['POST'])
@login_required
def save_feedback():
    data = request.get_json()

    module_name = data.get('module_name') or session.get('module_name')
    helpfulness = data.get('helpfulness_score')
    recommend = data.get('recommend_score')
    comments = data.get('comments')

    if not module_name:
        return jsonify({"message": "Module name missing"}), 400

    user_id = session.get('user_id')

    if not user_id:
        return jsonify({"message": "User not logged in"}), 401

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO feedback (user_id, module_name, helpfulness_score, recommend_score, comments)
        VALUES (%s, %s, %s, %s, %s)
    """, (user_id, module_name, helpfulness, recommend, comments))

    conn.commit()
    conn.close()

    return jsonify({"message": "Feedback saved!"})

# Show Recommended Modules (old version)
#@app.route('/recommended_modules')
#def recommended_modules():

#    user_id = session.get('user_id')

#    if not user_id:
#        return redirect(url_for('login'))

#    conn = get_db_connection()
#    cursor = conn.cursor(dictionary=True)

    # Get recommendations + module details
#    cursor.execute("""
#        SELECT r.module_name, r.similarity_score,
#               s.module_description
#        FROM recommendation r
#        JOIN subjects s ON r.module_name = s.module_name
#        WHERE r.user_id = %s
#        ORDER BY r.similarity_score DESC
#    """, (user_id,))

#    recommended_modules = cursor.fetchall()

#    conn.close()

#    return render_template(
#        'recommended_modules.html',
#        recommended_modules=recommended_modules
#    )

# --- API: Save Recommendation(old that use excel) ---
#@app.route('/save_recommendations', methods=['POST'])
#def save_recommendations():
#    data = request.get_json()
#    recommendations = data.get('recommendations')  # list of modules

#    user_id = session.get('user_id')

#    if not user_id:
#        return jsonify({"message": "User not logged in"}), 401

#    conn = get_db_connection()
#    cursor = conn.cursor()

#    for rec in recommendations:
#        cursor.execute("""
#            INSERT INTO recommendations (user_id, module_name, recommendation_type)
#            VALUES (%s, %s, %s)
#        """, (user_id, rec, "system"))

#    conn.commit()
#    conn.close()

#    return jsonify({"message": "Recommendations saved!"})


# ------------------------------
# LOAD & PREPROCESS DATA(old that use excel)
# ------------------------------
#feedback_df = pd.read_csv("Module Feedback 3rd round.csv")
#draft_df = pd.read_csv("draft 3rd round.csv")

#draft_df.dropna(subset=['Personalised learning styles', 'Response number', 'Course'], inplace=True)
#merged_df = pd.merge(draft_df, feedback_df, on='Response number', how='inner')
#merged_df.dropna(subset=['(MD1F) How would you recommend this module to your friends?'], inplace=True)

#valid_modules = merged_df['Module'].value_counts()[merged_df['Module'].value_counts() >= 3].index
#merged_df = merged_df[merged_df['Module'].isin(valid_modules)]

#train_df, test_df = train_test_split(merged_df, test_size=0.4, random_state=42)

# Encode users & modules
#user_ids = train_df['Response number'].unique()
#user_to_idx = {u: i for i, u in enumerate(user_ids)}
#idx_to_user = {i: u for u, i in user_to_idx.items()}

#module_ids = train_df['Module'].unique()
#module_to_idx = {m: i for i, m in enumerate(module_ids)}
#idx_to_module = {i: m for m, i in module_to_idx.items()}

#def encode_learner_style(style):
#    style_map = {'V':0, 'A':1, 'R':2, 'K':3}
#    vector = np.zeros(4)
#    for s in str(style).replace(' ','').replace(',',''):
#        if s in style_map:
#            vector[style_map[s]] = 1
#    return vector

# -----------------------------
# Define NCF model
# -----------------------------
#embedding_dim = 10

#user_input = Input(shape=(1,), name="User_Input")
#module_input = Input(shape=(1,), name="Module_Input")
#style_input = Input(shape=(4,), name="Style_Input")

#user_embedding = Embedding(input_dim=len(user_ids), output_dim=embedding_dim, name="User_Embedding")(user_input)
#module_embedding = Embedding(input_dim=len(module_ids), output_dim=embedding_dim, name="Module_Embedding")(module_input)

#user_vec = Flatten()(user_embedding)
#module_vec = Flatten()(module_embedding)

#x = Concatenate()([user_vec, module_vec, style_input])
#x = Dense(32, activation='relu')(x)
#x = Dense(16, activation='relu')(x)
#output = Dense(1, activation='linear')(x)

#ncf_model = Model(inputs=[user_input, module_input, style_input], outputs=output)
#ncf_model.compile(optimizer='adam', loss='mse')

# -----------------------------
# Prepare training data
# -----------------------------
#train_users = np.array([user_to_idx[u] for u in train_df['Response number']])
#train_modules = np.array([module_to_idx[m] for m in train_df['Module']])
#train_styles = np.array([encode_learner_style(s) for s in train_df['Personalised learning styles']])
#train_labels = train_df['(MD1F) How would you recommend this module to your friends?'].values

# Train model
#ncf_model.fit([train_users, train_modules, train_styles], train_labels, epochs=10, batch_size=8, verbose=1)

# -----------------------------
# Learner similarity
# -----------------------------
#user_embeddings = ncf_model.get_layer('User_Embedding').get_weights()[0]
#learner_similarity = cosine_similarity(user_embeddings)

#def recommend_modules_by_learner(user_id, top_n=5):
#    if user_id not in user_to_idx:
#        return []
#    u_idx = user_to_idx[user_id]
#    similar_users_idx = np.argsort(learner_similarity[u_idx])[::-1][1:top_n+5]
#    candidate_modules = {}
#    for su_idx in similar_users_idx:
#        sim_user_id = idx_to_user[su_idx]
#        sim_score = learner_similarity[u_idx][su_idx]
#        modules_taken = train_df[train_df['Response number']==sim_user_id]['Module'].values
#        for m in modules_taken:
#            candidate_modules[m] = candidate_modules.get(m, 0) + sim_score
#    return sorted(candidate_modules.items(), key=lambda x: x[1], reverse=True)[:top_n]

@app.route('/modules')
@login_required
def modules():
    if session.get('module_name') and session.get('learning_style'):
        return redirect(url_for('content'))
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


@app.route('/recommended_module')
@login_required
def recommended_module():
    return redirect(url_for('recommend'))

# ------------------------------
# LOAD DATA FROM DATABASE
# ------------------------------
@app.route('/recommend')
@login_required
def recommend():
    import pandas as pd
    import numpy as np
    #from sklearn.model_selection import train_test_split
    from sklearn.metrics.pairwise import cosine_similarity
    from tensorflow.keras.models import Model
    from tensorflow.keras.layers import Input, Embedding, Flatten, Dense, Concatenate

    chosen_style = session.get('learning_style')
    user_id = session.get('user_id')

    if not chosen_style:
        flash("Please complete your learning style before requesting recommendations.", "error")
        return redirect(url_for('learning_style'))

    chosen_style = str(chosen_style).upper().replace(' ', '')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    query = """
    SELECT 
        f.user_id AS `Response number`,
        f.module_name AS Module,
        f.recommend_score AS rating,
        s.learning_style AS `Personalised learning styles`
    FROM feedback f
    JOIN students s ON f.user_id = s.user_id
    WHERE f.recommend_score IS NOT NULL
    """

    train_df = pd.read_sql(query, conn)

    if train_df.empty:
        cursor.execute("""
            SELECT module_name, module_description
            FROM subjects
            ORDER BY module_name ASC
            LIMIT 5
        """)
        recommended_modules = [
            {**row, 'similarity_score': 0}
            for row in cursor.fetchall()
        ]
        cursor.close()
        conn.close()
        return render_template("recommended_module.html", recommended_modules=recommended_modules)

    train_df['Personalised learning styles'] = (
        train_df['Personalised learning styles']
        .astype(str)
        .str.upper()
        .str.replace(' ', '', regex=True)
    )

    same_style_df = train_df[
        train_df['Personalised learning styles'].str.contains(chosen_style, na=False)
    ].copy()

    if same_style_df.empty:
        same_style_df = train_df.copy()

    user_ids = same_style_df['Response number'].unique()
    module_ids = same_style_df['Module'].unique()

    if len(user_ids) < 2 or len(module_ids) == 0:
        fallback = (
            same_style_df.groupby('Module', as_index=False)['rating']
            .mean()
            .sort_values('rating', ascending=False)
            .head(5)
        )
        recommended_modules = []
        for _, row in fallback.iterrows():
            cursor.execute("SELECT module_description FROM subjects WHERE module_name=%s", (row['Module'],))
            subject_row = cursor.fetchone() or {'module_description': ''}
            recommended_modules.append({
                'module_name': row['Module'],
                'similarity_score': float(row['rating']),
                'module_description': subject_row['module_description']
            })
        cursor.close()
        conn.close()
        return render_template("recommended_module.html", recommended_modules=recommended_modules)

    user_to_idx = {u: i for i, u in enumerate(user_ids)}
    idx_to_user = {i: u for u, i in user_to_idx.items()}
    module_to_idx = {m: i for i, m in enumerate(module_ids)}

    def encode_learner_style(style):
        style_map = {'V': 0, 'A': 1, 'R': 2, 'K': 3}
        vector = np.zeros(4)
        for s in str(style).replace(' ', ''):
            if s in style_map:
                vector[style_map[s]] = 1
        return vector

    train_users = np.array([user_to_idx[u] for u in same_style_df['Response number']])
    train_modules = np.array([module_to_idx[m] for m in same_style_df['Module']])
    train_styles = np.array([encode_learner_style(s) for s in same_style_df['Personalised learning styles']])
    train_labels = same_style_df['rating'].astype(float).values

    embedding_dim = 10

    user_input = Input(shape=(1,))
    module_input = Input(shape=(1,))
    style_input = Input(shape=(4,))

    user_embedding_layer = Embedding(len(user_ids), embedding_dim)
    module_embedding_layer = Embedding(len(module_ids), embedding_dim)

    user_embedding = user_embedding_layer(user_input)
    module_embedding = module_embedding_layer(module_input)

    user_vec = Flatten()(user_embedding)
    module_vec = Flatten()(module_embedding)

    x = Concatenate()([user_vec, module_vec, style_input])
    x = Dense(32, activation='relu')(x)
    x = Dense(16, activation='relu')(x)
    output = Dense(1)(x)

    ncf_model = Model([user_input, module_input, style_input], output)
    ncf_model.compile(optimizer='adam', loss='mse')
    ncf_model.fit(
        [train_users, train_modules, train_styles],
        train_labels,
        epochs=10,
        batch_size=8,
        verbose=0
    )

    user_embedding_weights = user_embedding_layer.get_weights()[0]
    learner_similarity = cosine_similarity(user_embedding_weights)

    target_user = user_id if user_id in user_to_idx else same_style_df['Response number'].iloc[0]

    def recommend_modules_by_learner(target_user_id, top_n=5):
        if target_user_id not in user_to_idx:
            return []

        u_idx = user_to_idx[target_user_id]
        similar_users_idx = np.argsort(learner_similarity[u_idx])[::-1][1:top_n + 5]
        user_seen_modules = set(
            same_style_df[same_style_df['Response number'] == target_user_id]['Module'].tolist()
        )
        candidate_modules = {}

        for su_idx in similar_users_idx:
            sim_user_id = idx_to_user[su_idx]
            sim_score = learner_similarity[u_idx][su_idx]
            modules_taken = same_style_df[
                same_style_df['Response number'] == sim_user_id
            ]['Module'].values

            for m in modules_taken:
                if m in user_seen_modules:
                    continue
                candidate_modules[m] = candidate_modules.get(m, 0) + float(sim_score)

        return sorted(candidate_modules.items(), key=lambda x: x[1], reverse=True)[:top_n]

    recs = recommend_modules_by_learner(target_user)

    if not recs:
        fallback = (
            same_style_df.groupby('Module', as_index=False)['rating']
            .mean()
            .sort_values('rating', ascending=False)
            .head(5)
        )
        recs = [(row['Module'], float(row['rating'])) for _, row in fallback.iterrows()]

    cursor.execute("DELETE FROM recommendations WHERE user_id = %s", (user_id,))
    for module_name, sim_score in recs:
        cursor.execute("""
            INSERT INTO recommendations (user_id, module_name, similarity_score)
            VALUES (%s, %s, %s)
        """, (user_id, module_name, sim_score))
    conn.commit()

    cursor.execute("""
        SELECT r.module_name, r.similarity_score, s.module_description
        FROM recommendations r
        JOIN subjects s ON r.module_name = s.module_name
        WHERE r.user_id = %s
        ORDER BY r.similarity_score DESC
    """, (user_id,))
    recommended_modules = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template("recommended_module.html", recommended_modules=recommended_modules)

# -----------------------------
# Admin Login
#ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME")
#ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")

# -----------------------------
# Admin Login
# -----------------------------
#@app.route('/admin_login', methods=['GET', 'POST'])
#def admin_login():
#    if request.method == 'POST':
#        username = request.form['username']
#        password = request.form['password']

        # Hardcoded admin credentials for now
#        if username == "admin" and password == "admin123":
        #if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
#            session['admin_logged_in'] = True
#            flash("Admin login successful!", "success")
#            return redirect(url_for('admin_home'))
#        else:
#            flash("Invalid admin username or password.", "error")
#            return redirect(url_for('admin_login'))

#    return render_template('admin_login.html')

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

        if admin and admin['password'] == password:
            session.clear()
            session['admin_logged_in'] = True
            session['admin_id'] = admin['admin_id']
            session['admin_username'] = admin['username']
            session['admin_email'] = admin['email']

            flash("Admin login successful!", "success")
            return redirect(url_for('admin_home'))
        else:
            flash("Invalid admin username or password.", "error")
            return redirect(url_for('admin_login'))

    return render_template('admin_login.html')

# Temporary storage
subjects_list = []

# Admin home
@app.route('/admin_home')
@admin_required
def admin_home():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # 1. Student Performance
    cursor.execute("""
        SELECT 
            AVG(pre_score) AS avg_pre,
            AVG(final_score) AS avg_final,
            AVG(final_score - pre_score) AS avg_improvement
        FROM assessment
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

    # 2. Total Students
    cursor.execute("SELECT COUNT(*) AS total_students FROM students")
    total_students = cursor.fetchone()['total_students']

    # Total modules
    cursor.execute("SELECT COUNT(*) AS total_modules FROM subjects")
    total_modules = cursor.fetchone()['total_modules']

    # 3. Score Distribution
    cursor.execute("""
        SELECT 
            CASE
                WHEN final_score <= 2 THEN 'Low'
                WHEN final_score <= 4 THEN 'Medium'
                ELSE 'High'
            END AS category,
            COUNT(*) AS count
        FROM assessment
        WHERE final_score IS NOT NULL
        GROUP BY category
    """)
    score_distribution = cursor.fetchall() or []

    # 4. Learning Styles
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

    # 5. Recommendations
    # Top recommended modules only
    cursor.execute("""
        SELECT module_name, COUNT(*) AS rec_count
        FROM recommendations
        WHERE module_name IS NOT NULL
        AND module_name <> ''
        AND module_name <> 'None'
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

# Admin add module
@app.route('/admin_add_module', methods=['GET', 'POST'])
@admin_required
def admin_add_module():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        module_name = request.form['module_name']
        module_description = request.form['module_description']

        cursor.execute("""
            INSERT INTO subjects (module_name, module_description)
            VALUES (%s, %s)
        """, (module_name, module_description))

        conn.commit()
        flash("Module added successfully!", "success")
        return redirect(url_for('admin_add_module'))

    cursor.execute("SELECT * FROM subjects")
    modules = cursor.fetchall()

    conn.close()
    return render_template('admin_add_module.html', modules=modules)

# Admin delete module
@app.route('/delete_module/<int:module_id>')
@admin_required
def delete_module(module_id):

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM subjects WHERE id=%s", (module_id,))

    conn.commit()
    conn.close()

    return redirect(url_for('admin_add_module'))


# Admin edit module
@app.route('/edit_module/<int:module_id>', methods=['GET', 'POST'])
@admin_required
def edit_module(module_id):

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        module_name = request.form['module_name']
        module_description = request.form['module_description']

        cursor.execute("""
            UPDATE subjects
            SET module_name=%s,
                module_description=%s
            WHERE id=%s
        """, (module_name, module_description, module_id))

        conn.commit()
        conn.close()

        return redirect(url_for('admin_add_module'))

    # GET data
    cursor.execute("SELECT * FROM subjects WHERE id=%s", (module_id,))
    module = cursor.fetchone()

    conn.close()

    return render_template("admin_edit_module.html", module=module)

# Admin add questions
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
        question_text = request.form['question_text']
        correct_answer = request.form['correct_answer']
        question_type = request.form['question_type']

        option_a = request.form.get('option_a')
        option_b = request.form.get('option_b')
        option_c = request.form.get('option_c')
        option_d = request.form.get('option_d')

        cursor.execute("""
            INSERT INTO questions 
            (subject_id, assessment_type, question_text, correct_answer,
             question_type, option_a, option_b, option_c, option_d)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            subject_id,
            assessment_type,
            question_text,
            correct_answer,
            question_type,
            option_a,
            option_b,
            option_c,
            option_d
        ))

        conn.commit()
        flash("Question added successfully!", "success")
        return redirect(url_for('admin_add_question'))

    cursor.execute("""
        SELECT q.*, s.module_name
        FROM questions q
        JOIN subjects s ON q.subject_id = s.id
    """)
    questions = cursor.fetchall()

    conn.close()
    return render_template('admin_add_question.html',
                           modules=modules,
                           questions=questions)

# Admin delete questions
@app.route('/delete_question/<int:question_id>')
@admin_required
def delete_question(question_id):

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM questions WHERE id = %s", (question_id,))

    conn.commit()
    conn.close()

    return redirect(url_for('admin_add_question'))

# Admin edit questions
@app.route('/edit_question/<int:question_id>', methods=['GET', 'POST'])
@admin_required
def edit_question(question_id):

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Get modules for dropdown
    cursor.execute("SELECT * FROM subjects")
    modules = cursor.fetchall()

    if request.method == 'POST':

        subject_id = request.form['subject_id']
        assessment_type = request.form['assessment_type']
        question_text = request.form['question_text']
        correct_answer = request.form['correct_answer']
        question_type = request.form['question_type']

        option_a = request.form.get('option_a')
        option_b = request.form.get('option_b')
        option_c = request.form.get('option_c')
        option_d = request.form.get('option_d')

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
        conn.close()

        return redirect(url_for('admin_add_question'))

    # GET: fetch question
    cursor.execute("SELECT * FROM questions WHERE id = %s", (question_id,))
    question = cursor.fetchone()

    conn.close()

    return render_template(
        'admin_edit_question.html',
        question=question,
        modules=modules
    )

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
    except:
        return None
    
# Admin add material
UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


@app.route('/admin/add_material', methods=['GET', 'POST'])
@admin_required
def admin_add_material():

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM subjects")
    modules = cursor.fetchall()

    if request.method == 'POST':

        subject_id = request.form['subject_id']
        title = request.form['title']
        material_type = request.form['material_type']
        learning_style = request.form['learning_style']

        content = None

        # TEXT
        if material_type == "text":
            content = request.form.get('content')

        # VIDEO
        elif material_type == "video":
            raw_link = request.form.get('video_link')
            content = convert_to_embed(raw_link) if raw_link else None

        # PDF
        elif material_type == "pdf":
            file = request.files.get('pdf_file')

            if file and file.filename != "":
                filename = secure_filename(file.filename)
                os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                content = filepath

        # K CASE
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

    return render_template(
        "admin_add_material.html",
        modules=modules,
        materials=materials
    )


# Admin delete material
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


# Admin edit material
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
        title = request.form['title']
        material_type = request.form['material_type']
        learning_style = request.form['learning_style']

        content = None

        # TEXT
        if material_type == "text":
            content = request.form.get('content')

        # VIDEO
        elif material_type == "video":
            raw_link = request.form.get('video_link')
            content = convert_to_embed(raw_link) if raw_link else None

        # PDF
        elif material_type == "pdf":
            file = request.files.get('pdf_file')

            if file and file.filename != "":
                filename = secure_filename(file.filename)
                os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                content = filepath
            else:
                content = material['content']

        # K CASE
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

# run for local
#if __name__ == '__main__':
#    app.run(debug=os.environ.get('FLASK_DEBUG', 'False').lower() == 'true')

# run for railway
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(
        host='0.0.0.0',
        port=port,
        debug=os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    )

