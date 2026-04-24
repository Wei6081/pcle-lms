import os
import math
import random
import mysql.connector


def get_db_connection():
    return mysql.connector.connect(
        host=os.environ.get("DB_HOST"),
        port=int(os.environ.get("DB_PORT", 3306)),
        user=os.environ.get("DB_USER"),
        password=os.environ.get("DB_PASSWORD"),
        database=os.environ.get("DB_NAME")
    )


def normalize(score):
    return max(0.0, min(1.0, float(score) / 5.0))


def denormalize(score):
    return round(max(1.0, min(5.0, score * 5.0)), 4)


def sigmoid(x):
    return 1 / (1 + math.exp(-x))


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def train_and_save_ncf():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        UPDATE feedback f
        JOIN subjects s ON TRIM(f.module_name) = TRIM(s.module_name)
        SET f.subject_id = s.id
        WHERE f.subject_id IS NULL
    """)
    conn.commit()

    cursor.execute("""
        SELECT user_id, subject_id, recommend_score
        FROM feedback
        WHERE subject_id IS NOT NULL
          AND recommend_score IS NOT NULL
    """)
    rows = cursor.fetchall()

    if len(rows) < 5:
        cursor.close()
        conn.close()
        return "Not enough feedback data"

    cursor.execute("SELECT user_id FROM students WHERE learning_style IS NOT NULL")
    users = [r["user_id"] for r in cursor.fetchall()]

    cursor.execute("SELECT id, module_name FROM subjects")
    subjects = cursor.fetchall()

    subject_ids = [s["id"] for s in subjects]
    subject_names = {s["id"]: s["module_name"] for s in subjects}

    factors = 8
    epochs = 300
    lr = 0.03
    reg = 0.02

    user_vec = {u: [random.uniform(-0.1, 0.1) for _ in range(factors)] for u in users}
    item_vec = {s: [random.uniform(-0.1, 0.1) for _ in range(factors)] for s in subject_ids}

    user_bias = {u: 0.0 for u in users}
    item_bias = {s: 0.0 for s in subject_ids}

    ratings = []
    completed = set()

    for r in rows:
        ratings.append({
            "user_id": r["user_id"],
            "subject_id": r["subject_id"],
            "rating": normalize(r["recommend_score"])
        })
        completed.add((r["user_id"], r["subject_id"]))

    global_mean = sum(r["rating"] for r in ratings) / len(ratings)

    for _ in range(epochs):
        random.shuffle(ratings)

        for r in ratings:
            u = r["user_id"]
            s = r["subject_id"]
            actual = r["rating"]

            if u not in user_vec or s not in item_vec:
                continue

            raw = global_mean + user_bias[u] + item_bias[s] + dot(user_vec[u], item_vec[s])
            pred = sigmoid(raw)

            error = actual - pred
            grad = error * pred * (1 - pred)

            user_bias[u] += lr * (grad - reg * user_bias[u])
            item_bias[s] += lr * (grad - reg * item_bias[s])

            old_u = user_vec[u][:]
            old_s = item_vec[s][:]

            for i in range(factors):
                user_vec[u][i] += lr * (grad * old_s[i] - reg * old_u[i])
                item_vec[s][i] += lr * (grad * old_u[i] - reg * old_s[i])

    cursor.execute("DELETE FROM recommendations WHERE recommendation_type = 'NCF'")
    conn.commit()

    insert_count = 0

    for u in users:
        for s in subject_ids:
            if (u, s) in completed:
                continue

            raw = global_mean + user_bias.get(u, 0) + item_bias.get(s, 0) + dot(user_vec[u], item_vec[s])
            predicted_score = denormalize(sigmoid(raw))

            cursor.execute("""
                INSERT INTO recommendations
                (user_id, module_name, recommendation_type, predicted_score, subject_id)
                VALUES (%s, %s, 'NCF', %s, %s)
            """, (u, subject_names[s], predicted_score, s))

            insert_count += 1

    conn.commit()
    cursor.close()
    conn.close()

    return f"NCF updated: {insert_count} predictions saved"