document.addEventListener('DOMContentLoaded', function () {

  const form = document.getElementById('finalAssessmentForm');
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
          feedbackDiv.innerHTML = `<span class='wrong'>✘ Wrong (Correct: ${correctAnswer})</span>`;
        }
      }

      const labels = qDiv.querySelectorAll('label');

      labels.forEach(label => {
        const input = label.querySelector('input');

        if (input && input.checked) {
          if (input.value === correctAnswer) {
            label.style.color = "green";
          } else {
            label.style.color = "red";
          }
        }
      });

    });

    localStorage.setItem('finalAssessment', JSON.stringify(answers));

    resultBox.style.display = "block";
    resultBox.innerHTML = `
      <h3>✅ Final Assessment Completed</h3>
      <p><strong>Score:</strong> ${score} / ${questions.length}</p>
    `;

    fetch('/save_final_assessment', {
      method: 'POST',
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        final_score: score
      })
    })
      .then(res => res.json())
      .then(data => console.log(data.message))
      .catch(err => console.error(err));

    nextBtn.style.display = "inline-block";
  });

  nextBtn.addEventListener('click', function () {
    window.location.href = "/result";
  });

});