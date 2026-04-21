let q1Rating = 0;
let q2Rating = 0;

function setupRating(questionId) {
  const spans = document.querySelectorAll(`#${questionId} span`);
  spans.forEach(span => {
    span.addEventListener('click', () => {
      spans.forEach(s => s.classList.remove('selected'));
      span.classList.add('selected');
      if (questionId === 'q1Options') q1Rating = span.dataset.value;
      if (questionId === 'q2Options') q2Rating = span.dataset.value;
    });
  });
}

setupRating('q1Options');
setupRating('q2Options');

document.getElementById('FeedbackForm').addEventListener('submit', function(e) {
  e.preventDefault();

  const comment = document.getElementById('comment').value.trim();
  const messageEl = document.getElementById('feedbackMessage');

  if (!q1Rating || !q2Rating) {
    alert("Please select a rating for both questions.");
    return;
  }

  if (!comment) {
    messageEl.textContent = "Please write a comment before submitting.";
    messageEl.style.color = "red";
    return;
  }

  const moduleName = document.getElementById('module_name').value;

  const feedbackData = {
    module_name: moduleName,
    helpfulness_score: q1Rating,
    recommend_score: q2Rating,
    comments: comment
  };

  fetch('/save_feedback', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(feedbackData)
  })
  .then(response => response.json())
  .then(data => {
    if (data.message !== "Feedback saved!") {
      throw new Error(data.message || "Unable to save feedback");
    }

    messageEl.textContent = "Thank you for your feedback!";
    messageEl.style.color = "green";

    setTimeout(() => {
      window.location.href = "/recommended_module";
    }, 1500);
  })
  .catch(error => {
    messageEl.textContent = error.message || "Error saving feedback.";
    messageEl.style.color = "red";
    console.error('Error saving feedback:', error);
  });
});