// Synthetic example for demonstrating pattern-based JavaScript checks.
function renderMessage(userInput) {
  // Deliberately unsafe demo pattern; never use untrusted input this way.
  document.body.innerHTML = userInput;
}

renderMessage("<p>Demo only</p>");
