document.addEventListener('DOMContentLoaded', function() {
    const chatMessages = document.getElementById('chat-messages');
    const userInput = document.getElementById('user-input');
    const sendButton = document.getElementById('send-button');

    // Function to add a message to the chat
    function addMessage(message, isUser) {
        const messageDiv = document.createElement('div');
        messageDiv.classList.add('message');
        messageDiv.classList.add(isUser ? 'user-message' : 'bot-message');

        const messageContent = document.createElement('div');
        messageContent.classList.add('message-content');
        
        // Handle newlines in messages
        if (message.includes('\n')) {
            message.split('\n').forEach((line, index) => {
                if (index > 0) {
                    messageContent.appendChild(document.createElement('br'));
                }
                messageContent.appendChild(document.createTextNode(line));
            });
        } else {
            messageContent.textContent = message;
        }

        messageDiv.appendChild(messageContent);
        
        // Add timestamp
        const timeDiv = document.createElement('div');
        timeDiv.className = 'message-time';
        timeDiv.textContent = new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
        messageDiv.appendChild(timeDiv);
        
        chatMessages.appendChild(messageDiv);
        
        // Scroll to the bottom of the chat
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    // Function to show loading indicator
    function showLoading() {
        const loadingDiv = document.createElement('div');
        loadingDiv.classList.add('message', 'bot-message');
        loadingDiv.id = 'loading-message';

        const loadingDots = document.createElement('div');
        loadingDots.classList.add('loading-dots');
        
        for (let i = 0; i < 3; i++) {
            const dot = document.createElement('div');
            dot.classList.add('dot');
            loadingDots.appendChild(dot);
        }

        loadingDiv.appendChild(loadingDots);
        chatMessages.appendChild(loadingDiv);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    // Function to remove loading indicator
    function removeLoading() {
        const loadingMessage = document.getElementById('loading-message');
        if (loadingMessage) {
            loadingMessage.remove();
        }
    }

    // Function to determine which endpoint to use
    function determineEndpoint() {
        const path = window.location.pathname;
        if (path.includes('gemini-chat')) {
            return {
                endpoint: '/api/gemini-chat',
                contentType: 'application/json',
                isJson: true
            };
        } else {
            return {
                endpoint: '/get',
                contentType: 'application/x-www-form-urlencoded',
                isJson: false
            };
        }
    }

    // Function to send a message
    async function sendMessage() {
        const message = userInput.value.trim();
        if (!message) return;

        // Add user message to chat
        addMessage(message, true);
        
        // Clear input field
        userInput.value = '';

        // Show loading indicator
        showLoading();

        try {
            // Determine which endpoint to use based on current page
            const { endpoint, contentType, isJson } = determineEndpoint();
            
            let body;
            if (isJson) {
                body = JSON.stringify({ message: message });
            } else {
                body = 'msg=' + encodeURIComponent(message);
            }

            // Send message to the backend
            const response = await fetch(endpoint, {
                method: 'POST',
                headers: {
                    'Content-Type': contentType
                },
                body: body
            });

            // Check if the response is JSON
            const responseContentType = response.headers.get('content-type');
            let data;
            
            if (responseContentType && responseContentType.includes('application/json')) {
                data = await response.json();
            } else {
                const text = await response.text();
                try {
                    data = JSON.parse(text);
                } catch (e) {
                    console.error('Response is not JSON:', text);
                    data = { error: 'Invalid response format' };
                }
            }
            
            // Remove loading indicator
            removeLoading();

            if (response.ok) {
                // Add bot response to chat
                const botMessage = data.response || data.message || 'Sorry, I couldn\'t process that.';
                addMessage(botMessage, false);
            } else {
                // Add error message
                addMessage('Sorry, something went wrong. Please try again. Error: ' + (data.error || 'Unknown error'), false);
                console.error('Error:', data.error || 'Unknown error');
            }
        } catch (error) {
            // Remove loading indicator
            removeLoading();
            
            // Add error message
            addMessage('Sorry, an error occurred. Please try again. Error: ' + error.message, false);
            console.error('Error:', error);
        }
    }

    // Event listeners
    if (sendButton) {
        sendButton.addEventListener('click', sendMessage);
    }
    
    if (userInput) {
        userInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                sendMessage();
            }
        });
    }

    // Function to set question from sidebar
    window.setQuestion = function(question) {
        if (userInput) {
            userInput.value = question;
            userInput.focus();
        }
    };
});
