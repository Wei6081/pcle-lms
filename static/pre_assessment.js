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

      // Get selected answer
      const selectedInput = qDiv.querySelector('input[type="radio"]:checked');
      const userAnswer = selectedInput ? selectedInput.value : "";

      // Get correct answer from data attribute
      const correctAnswer = qDiv.dataset.correct;

      const isCorrect = userAnswer === correctAnswer;

      // Count score
      if (isCorrect) {
        score++;
      }

      // Store answer
      answers[`q${index + 1}`] = userAnswer;

      // Show feedback
      const feedbackDiv = qDiv.querySelector('.feedback');

      if (feedbackDiv) {
        if (isCorrect) {
          feedbackDiv.innerHTML = "<span class='correct'>✔ Correct</span>";
        } else {
          feedbackDiv.innerHTML = `<span class='wrong'>✘ Wrong (Correct: ${correctAnswer})</span>`;
        }
      }

      // Highlight selected option
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

    // Save answers locally
    localStorage.setItem('preAssessment', JSON.stringify(answers));

    // Display result
    resultBox.style.display = "block";
    resultBox.innerHTML = `
      <h3>✅ Pre-Assessment Completed</h3>
      <p><strong>Score:</strong> ${score} / ${questions.length}</p>
    `;

    // Send score to Flask backend
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

    // Show next button
    nextBtn.style.display = "inline-block";
  });

  // Redirect to learning style page
  nextBtn.addEventListener('click', function () {
    window.location.href = "/learning_style";
  });

});