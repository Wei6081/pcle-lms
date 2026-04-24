document.addEventListener('DOMContentLoaded', function () {
  const form = document.getElementById('finalAssessmentForm');
  const resultBox = document.getElementById('result');
  const nextBtn = document.getElementById('nextBtn');

  form.addEventListener('submit', async function (e) {
    e.preventDefault();

    let score = 0;
    const answers = {};
    const questions = document.querySelectorAll('.question');

    questions.forEach((qDiv, index) => {
      const selectedInput = qDiv.querySelector('input[type="radio"]:checked');
      const userAnswer = selectedInput ? selectedInput.value : "";
      const correctAnswer = qDiv.dataset.correct;
      const isCorrect = userAnswer === correctAnswer;

      if (isCorrect) score++;

      answers[`q${index + 1}`] = userAnswer;

      const feedbackDiv = qDiv.querySelector('.feedback');

      if (feedbackDiv) {
        feedbackDiv.innerHTML = isCorrect
          ? "<span class='correct'>✔ Correct</span>"
          : `<span class='wrong'>✘ Wrong (Correct: ${correctAnswer})</span>`;
      }

      qDiv.querySelectorAll('.options label').forEach(label => {
        const input = label.querySelector('input');
        if (!input) return;

        if (input.checked) {
          label.style.border = isCorrect ? "2px solid #16a34a" : "2px solid #dc2626";
          label.style.backgroundColor = isCorrect ? "#f0fdf4" : "#fef2f2";
        } else {
          label.style.opacity = "0.85";
        }
      });
    });

    try {
      const res = await fetch('/save_final_assessment', {
        method: 'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          final_score: score
        })
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.message || "Unable to save final assessment.");
      }

      localStorage.setItem('finalAssessment', JSON.stringify(answers));

      resultBox.style.display = "block";
      resultBox.innerHTML = `
        <h3>✅ Final Assessment Completed</h3>
        <p><strong>Score:</strong> ${score} / ${questions.length}</p>
      `;

      nextBtn.style.display = "inline-block";
      form.querySelector('button[type="submit"]').disabled = true;

    } catch (err) {
      resultBox.style.display = "block";
      resultBox.innerHTML = `<p class="wrong">${err.message}</p>`;
    }
  });

  nextBtn.addEventListener('click', function () {
    window.location.href = "/result";
  });
});