let q1Rating = 0;
let q2Rating = 0;

// Function to make rating boxes clickable
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

// Submit feedback
document.getElementById('FeedbackForm').addEventListener('submit', function(e) {
  e.preventDefault();

  const comment = document.getElementById('comment').value.trim();

  if (!q1Rating || !q2Rating) {
    alert("Please select a rating for both questions.");
    return;
  }

  const moduleName = document.getElementById('module_name').value;

  const feedbackData = {
    module_name: moduleName,
    helpfulness_score: q1Rating,
    recommend_score: q2Rating,
    comments: comment
  };

  // Send to Flask backend
  fetch('/save_feedback', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(feedbackData)
  })
  .then(response => response.json())
  .then(data => {
    console.log(data.message);

    // Show thank-you message
    const messageEl = document.getElementById('feedbackMessage');
    messageEl.textContent = "Thank you for your feedback!";
    messageEl.style.color = "green";

    // Redirect
    setTimeout(() => {
      window.location.href = "/recommended_module";
    }, 1500);
  })
  .catch(error => {
    console.error('Error saving feedback:', error);
  });
});
//document.getElementById('FeedbackForm').addEventListener('submit', function(e) {
//  e.preventDefault();
//  const comment = document.getElementById('comment').value.trim();

//  if (!q1Rating || !q2Rating) {
//    alert("Please select a rating for both questions.");
//    return;
//  }

//  const feedback = { q1Rating, q2Rating, comment };

  // Save to localStorage (replace with backend/database later)
//  const moduleId = 'module123';
//  let feedbackList = JSON.parse(localStorage.getItem(`feedback_${moduleId}`)) || [];
// feedbackList.push(feedback);
//  localStorage.setItem(`feedback_${moduleId}`, JSON.stringify(feedbackList));

  // Show thank-you message
//  const messageEl = document.getElementById('feedbackMessage');
//  messageEl.textContent = "Thank you for your feedback!";
//  messageEl.style.color = "green";

  // Reset selections
//  q1Rating = 0;
//  q2Rating = 0;
//  document.querySelectorAll('.rating-options span').forEach(s => s.classList.remove('selected'));
//  document.getElementById('comment').value = "";

  // Redirect to Recommended Module page after 1.5 seconds
//  setTimeout(() => {
//    window.location.href = "/recommended_module"; // or use Flask url_for if rendered dynamically
//  }, 3000);
//});
