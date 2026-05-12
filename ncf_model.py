import os
import math
import random
import mysql.connector


# New subject rule:
# A subject needs at least 3 feedback records before it can be recommended by VARK-NCF.
MIN_FEEDBACK_PER_SUBJECT = 3

# Overall minimum feedback needed before training starts.
MIN_TOTAL_FEEDBACK = 5

VARK_MAP = {
    "V": 0,
    "A": 1,
    "R": 2,
    "K": 3
}


def get_db_connection():
    return mysql.connector.connect(
        host=os.environ.get("DB_HOST"),
        port=int(os.environ.get("DB_PORT", 3306)),
        user=os.environ.get("DB_USER"),
        password=os.environ.get("DB_PASSWORD"),
        database=os.environ.get("DB_NAME")
    )


def normalize(score):
    """
    Convert 1-5 feedback score to 0-1.
    Example: 4 / 5 = 0.8
    """
    return max(0.0, min(1.0, float(score) / 5.0))


def denormalize(score):
    """
    Convert 0-1 model output back to 1-5 score.
    Example: 0.82 * 5 = 4.1
    """
    return round(max(1.0, min(5.0, score * 5.0)), 4)


def sigmoid(x):
    """
    Sigmoid activation for output layer.
    Keeps prediction between 0 and 1.
    """
    if x < -60:
        return 0.0
    if x > 60:
        return 1.0
    return 1 / (1 + math.exp(-x))


def relu(x):
    """
    ReLU activation for hidden layer.
    """
    return max(0.0, x)


def relu_derivative(x):
    """
    Derivative of ReLU for backpropagation.
    """
    return 1.0 if x > 0 else 0.0


def dot(a, b):
    """
    Dot product between two vectors.
    """
    return sum(x * y for x, y in zip(a, b))


def train_and_save_ncf():
    """
    VARK-NCF model.

    Inputs:
    - user_id
    - subject_id
    - learning_style

    Target:
    - feedback.recommend_score

    Output:
    - predicted recommendation score for unseen modules

    New subject handling:
    - A subject must have at least MIN_FEEDBACK_PER_SUBJECT feedback records.
    - If not, it will not appear in VARK-NCF recommendation yet.
    """

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Step 1: Make sure feedback.subject_id is filled based on module_name.
    cursor.execute("""
        UPDATE feedback f
        JOIN subjects s ON TRIM(f.module_name) = TRIM(s.module_name)
        SET f.subject_id = s.id
        WHERE f.subject_id IS NULL
    """)
    conn.commit()

    # Step 2: Only include subjects/modules that have at least 3 feedback records.
    cursor.execute("""
        SELECT subject_id, COUNT(*) AS feedback_count
        FROM feedback
        WHERE subject_id IS NOT NULL
          AND recommend_score IS NOT NULL
        GROUP BY subject_id
        HAVING feedback_count >= %s
    """, (MIN_FEEDBACK_PER_SUBJECT,))

    eligible_subject_ids = [row["subject_id"] for row in cursor.fetchall()]

    if not eligible_subject_ids:
        cursor.close()
        conn.close()
        return "No subject has enough feedback for VARK-NCF yet."

    placeholders = ",".join(["%s"] * len(eligible_subject_ids))

    # Step 3: Get training data.
    # The model learns from user + subject + VARK style + recommend score.
    cursor.execute(f"""
        SELECT 
            f.user_id,
            f.subject_id,
            f.recommend_score,
            st.learning_style
        FROM feedback f
        JOIN students st ON f.user_id = st.user_id
        WHERE f.subject_id IN ({placeholders})
          AND f.recommend_score IS NOT NULL
          AND st.learning_style IS NOT NULL
    """, tuple(eligible_subject_ids))

    rows = cursor.fetchall()

    if len(rows) < MIN_TOTAL_FEEDBACK:
        cursor.close()
        conn.close()
        return "Not enough total feedback data for VARK-NCF."

    # Step 4: Get all students who already have VARK learning style.
    cursor.execute("""
        SELECT user_id, learning_style
        FROM students
        WHERE learning_style IS NOT NULL
    """)
    user_rows = cursor.fetchall()

    user_styles = {
        row["user_id"]: row["learning_style"]
        for row in user_rows
        if row["learning_style"] in VARK_MAP
    }

    users = list(user_styles.keys())

    if not users:
        cursor.close()
        conn.close()
        return "No users with valid VARK learning style."

    # Step 5: Get eligible subjects only.
    cursor.execute(f"""
        SELECT id, module_name
        FROM subjects
        WHERE id IN ({placeholders})
    """, tuple(eligible_subject_ids))

    subject_rows = cursor.fetchall()

    subject_ids = [row["id"] for row in subject_rows]
    subject_names = {
        row["id"]: row["module_name"]
        for row in subject_rows
    }

    if not subject_ids:
        cursor.close()
        conn.close()
        return "No eligible subjects found."

    # Step 6: Get completed modules.
    # We do not recommend modules already completed by the same student.
    cursor.execute("""
        SELECT user_id, subject_id
        FROM module_progress
        WHERE final_score IS NOT NULL
    """)
    completed_rows = cursor.fetchall()

    completed = {
        (row["user_id"], row["subject_id"])
        for row in completed_rows
    }

    # Step 7: Create index mapping.
    user_to_idx = {user_id: idx for idx, user_id in enumerate(users)}
    subject_to_idx = {subject_id: idx for idx, subject_id in enumerate(subject_ids)}

    # Step 8: Model settings.
    embedding_dim = 8
    hidden_dim = 12
    epochs = 350
    lr = 0.03
    reg = 0.001

    random.seed(42)

    # Step 9: Create embeddings.
    # User embedding = learns student preference pattern.
    user_emb = [
        [random.uniform(-0.1, 0.1) for _ in range(embedding_dim)]
        for _ in users
    ]

    # Subject embedding = learns module pattern.
    subject_emb = [
        [random.uniform(-0.1, 0.1) for _ in range(embedding_dim)]
        for _ in subject_ids
    ]

    # VARK embedding = learns learning style influence.
    vark_emb = [
        [random.uniform(-0.1, 0.1) for _ in range(embedding_dim)]
        for _ in range(4)
    ]

    # Combined input = user embedding + subject embedding + VARK embedding.
    input_dim = embedding_dim * 3

    # Hidden layer weights.
    w1 = [
        [random.uniform(-0.1, 0.1) for _ in range(input_dim)]
        for _ in range(hidden_dim)
    ]
    b1 = [0.0 for _ in range(hidden_dim)]

    # Output layer weights.
    w2 = [random.uniform(-0.1, 0.1) for _ in range(hidden_dim)]
    b2 = 0.0

    # Step 10: Build training samples.
    training_data = []

    for row in rows:
        user_id = row["user_id"]
        subject_id = row["subject_id"]
        style = row["learning_style"]

        if user_id not in user_to_idx:
            continue

        if subject_id not in subject_to_idx:
            continue

        if style not in VARK_MAP:
            continue

        training_data.append({
            "user_idx": user_to_idx[user_id],
            "subject_idx": subject_to_idx[subject_id],
            "vark_idx": VARK_MAP[style],
            "rating": normalize(row["recommend_score"])
        })

    if len(training_data) < MIN_TOTAL_FEEDBACK:
        cursor.close()
        conn.close()
        return "Not enough valid training rows for VARK-NCF."

    # Step 11: Train the VARK-NCF model.
    for _ in range(epochs):
        random.shuffle(training_data)

        for sample in training_data:
            u = sample["user_idx"]
            s = sample["subject_idx"]
            v = sample["vark_idx"]
            actual = sample["rating"]

            # Forward pass: concatenate embeddings.
            x = user_emb[u] + subject_emb[s] + vark_emb[v]

            # Hidden layer.
            z1 = []
            h1 = []

            for j in range(hidden_dim):
                z = dot(w1[j], x) + b1[j]
                z1.append(z)
                h1.append(relu(z))

            # Output layer.
            raw_output = dot(w2, h1) + b2
            pred = sigmoid(raw_output)

            # Error.
            error = actual - pred

            # Output gradient.
            grad_output = error * pred * (1 - pred)

            old_w2 = w2[:]

            # Update output layer.
            for j in range(hidden_dim):
                w2[j] += lr * (grad_output * h1[j] - reg * w2[j])
            b2 += lr * grad_output

            # Hidden gradient.
            grad_hidden = []

            for j in range(hidden_dim):
                grad_h = grad_output * old_w2[j] * relu_derivative(z1[j])
                grad_hidden.append(grad_h)

            # Input gradient.
            grad_x = [0.0 for _ in range(input_dim)]

            # Update hidden layer.
            for j in range(hidden_dim):
                old_w1_j = w1[j][:]

                for i in range(input_dim):
                    w1[j][i] += lr * (grad_hidden[j] * x[i] - reg * w1[j][i])
                    grad_x[i] += grad_hidden[j] * old_w1_j[i]

                b1[j] += lr * grad_hidden[j]

            # Update user embedding.
            for i in range(embedding_dim):
                user_emb[u][i] += lr * (grad_x[i] - reg * user_emb[u][i])

            # Update subject embedding.
            for i in range(embedding_dim):
                subject_emb[s][i] += lr * (
                    grad_x[embedding_dim + i] - reg * subject_emb[s][i]
                )

            # Update VARK embedding.
            for i in range(embedding_dim):
                vark_emb[v][i] += lr * (
                    grad_x[(embedding_dim * 2) + i] - reg * vark_emb[v][i]
                )

    # Step 12: Delete old VARK-NCF predictions.
    cursor.execute("""
        DELETE FROM recommendations
        WHERE recommendation_type = 'VARK_NCF'
    """)
    conn.commit()

    insert_count = 0

    # Step 13: Generate prediction for every student and every eligible subject.
    for user_id in users:
        if user_id not in user_to_idx:
            continue

        style = user_styles.get(user_id)

        if style not in VARK_MAP:
            continue

        u = user_to_idx[user_id]
        v = VARK_MAP[style]

        for subject_id in subject_ids:
            if subject_id not in subject_to_idx:
                continue

            # Do not recommend completed module.
            if (user_id, subject_id) in completed:
                continue

            s = subject_to_idx[subject_id]

            x = user_emb[u] + subject_emb[s] + vark_emb[v]

            h1 = []

            for j in range(hidden_dim):
                z = dot(w1[j], x) + b1[j]
                h1.append(relu(z))

            raw_output = dot(w2, h1) + b2
            predicted_score = denormalize(sigmoid(raw_output))

            cursor.execute("""
                INSERT INTO recommendations
                (user_id, module_name, recommendation_type, predicted_score, subject_id)
                VALUES (%s, %s, 'VARK_NCF', %s, %s)
            """, (
                user_id,
                subject_names[subject_id],
                predicted_score,
                subject_id
            ))

            insert_count += 1

    conn.commit()
    cursor.close()
    conn.close()

    return f"VARK-NCF updated: {insert_count} predictions saved."