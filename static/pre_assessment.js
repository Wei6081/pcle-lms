document.addEventListener('DOMContentLoaded', function () {

  const form = document.getElementById('preAssessmentForm');
  const resultBox = document.getElementById('result');
  const nextBtn = document.getElementById('nextBtn');

  form.addEventListener('submit', function (e) {
    e.preventDefault();

    let score = 0;
    const answers = {};
    const questions = document.querySelectorAll('.question');

    questions.forEach((qDiv, index) => {
      const selectedInput = qDiv.querySelector('input[type="radio"]:checked');
      const userAnswer = selectedInput ? selectedInput.value : "";
      const correctAnswer = qDiv.dataset.correct;

      const isCorrect = userAnswer === correctAnswer;

      if (isCorrect) {
        score++;
      }

      answers[`q${index + 1}`] = userAnswer;

      const feedbackDiv = qDiv.querySelector('.feedback');

      if (feedbackDiv) {
        if (isCorrect) {
          feedbackDiv.innerHTML = "<span class='correct'>✔ Correct</span>";
        } else {
          feedbackDiv.innerHTML = "<span class='wrong'>✘ Incorrect</span>";
        }
      }

      const labels = qDiv.querySelectorAll('.options label');

      labels.forEach(label => {
        const input = label.querySelector('input');

        if (!input) return;

        if (input.checked) {
          if (isCorrect) {
            label.style.border = "2px solid #16a34a";
            label.style.backgroundColor = "#f0fdf4";
          } else {
            label.style.border = "2px solid #dc2626";
            label.style.backgroundColor = "#fef2f2";
          }
        } else {
          label.style.opacity = "0.85";
        }
      });
    });

    localStorage.setItem('preAssessment', JSON.stringify(answers));

    resultBox.style.display = "block";
    resultBox.innerHTML = `
      <h3>✅ Pre-Assessment Completed</h3>
      <p><strong>Score:</strong> ${score} / ${questions.length}</p>
    `;

    fetch('/save_pre_assessment', {
      method: 'POST',
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        pre_score: score
      })
    })
      .then(res => res.json())
      .then(data => console.log(data.message))
      .catch(err => console.error(err));

    nextBtn.style.display = "inline-block";
  });

  nextBtn.addEventListener('click', function () {
    window.location.href = "/learning_style";
  });

});