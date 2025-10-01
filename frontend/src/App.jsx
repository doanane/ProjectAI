import React, { useState } from 'react';
import axios from 'axios';
import './App.css';

// Create axios instance with base URL - CHANGE THIS TO YOUR FASTAPI URL
const api = axios.create({
  baseURL: 'http://localhost:8000', // Your FastAPI server address
  withCredentials: true, // IMPORTANT: This sends cookies automatically
});

function App() {
  // State variables to track game status and data
  const [gameState, setGameState] = useState('not-started'); // 'not-started', 'playing', 'ended'
  const [currentQuestion, setCurrentQuestion] = useState('');
  const [userAnswer, setUserAnswer] = useState('');
  const [score, setScore] = useState(0);
  const [totalAnswered, setTotalAnswered] = useState(0);
  const [correctAnswers, setCorrectAnswers] = useState(0);
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(false);

  // Function to start a new game
  const startGame = async () => {
    setLoading(true);
    try {
      const response = await api.post('/start');
      setCurrentQuestion(response.data.question);
      setGameState('playing');
      setScore(0);
      setTotalAnswered(0);
      setCorrectAnswers(0);
      setMessage(response.data.message);
      setUserAnswer('');
    } catch (error) {
      setMessage('Error starting game: ' + (error.response?.data?.detail || error.message));
    } finally {
      setLoading(false);
    }
  };

  // Function to submit an answer
  const submitAnswer = async () => {
    if (!userAnswer.trim()) {
      setMessage('Please enter an answer!');
      return;
    }

    setLoading(true);
    try {
      const response = await api.post('/answer', {
        answer: userAnswer.trim()
      });

      // Update game state based on response
      setScore(response.data.score);
      setTotalAnswered(response.data.total_answered);
      setCorrectAnswers(response.data.correct_answers);
      setMessage(response.data.message);

      if (response.data.question) {
        setCurrentQuestion(response.data.question);
      }

      setUserAnswer(''); // Clear input field
    } catch (error) {
      setMessage('Error submitting answer: ' + (error.response?.data?.detail || error.message));
    } finally {
      setLoading(false);
    }
  };

  // Function to end the game
  const endGame = async () => {
    setLoading(true);
    try {
      const response = await api.post('/end');
      setMessage(response.data.message);
      setGameState('ended');
      // Final scores are in the response data
    } catch (error) {
      setMessage('Error ending game: ' + (error.response?.data?.detail || error.message));
    } finally {
      setLoading(false);
    }
  };

  // Function to check current score
  const checkScore = async () => {
    try {
      const response = await api.get('/score');
      setScore(response.data.score);
      setTotalAnswered(response.data.total_answered);
      setCorrectAnswers(response.data.correct_answers);
      setMessage(`Current score: ${response.data.score}, Success rate: ${response.data.success_rate}%`);
    } catch (error) {
      setMessage('Error checking score: ' + (error.response?.data?.detail || error.message));
    }
  };

  // Handle Enter key press in answer input
  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && gameState === 'playing') {
      submitAnswer();
    }
  };

  return (
    <div className="app">
      <header className="app-header">
        <h1> Programming Riddle Game</h1>
        <p>Test your programming knowledge with AI-generated riddles!</p>
      </header>

      <main className="game-container">
        {/* Game Controls */}
        <div className="controls">
          {gameState === 'not-started' && (
            <button 
              onClick={startGame} 
              disabled={loading}
              className="btn btn-primary"
            >
              {loading ? (
                <>
                  <div className="loading"></div>
                  Starting Game...
                </>
              ) : (
                ' Start New Game'
              )}
            </button>
          )}

          {gameState === 'ended' && (
            <button 
              onClick={startGame} 
              disabled={loading}
              className="btn btn-primary"
            >
              {loading ? (
                <>
                  <div className="loading"></div>
                  Starting...
                </>
              ) : (
                'Play Again'
              )}
            </button>
          )}

          {(gameState === 'playing' || gameState === 'ended') && (
            <button 
              onClick={checkScore} 
              className="btn btn-secondary"
            >
              Check Score
            </button>
          )}

          {gameState === 'playing' && (
            <button 
              onClick={endGame} 
              disabled={loading}
              className="btn btn-warning"
            >
              {loading ? (
                <>
                  <div className="loading"></div>
                  Ending...
                </>
              ) : (
                ' End Game'
              )}
            </button>
          )}
        </div>

        {/* Current Question Display */}
        {currentQuestion && (
          <div className="question-section">
            <h2>Current Riddle:</h2>
            <div className="question-box">
              <p>{currentQuestion}</p>
            </div>
          </div>
        )}

        {/* Answer Input (only show when playing) */}
        {gameState === 'playing' && (
          <div className="answer-section">
            <h3>Your Answer:</h3>
            <div className="input-group">
              <input
                type="text"
                value={userAnswer}
                onChange={(e) => setUserAnswer(e.target.value)}
                onKeyPress={handleKeyPress}
                placeholder="Type your answer here..."
                disabled={loading}
                className="answer-input"
              />
              <button 
                onClick={submitAnswer} 
                disabled={loading || !userAnswer.trim()}
                className="btn btn-success"
              >
                {loading ? (
                  <>
                    <div className="loading"></div>
                    Checking...
                  </>
                ) : (
                  ' Submit Answer'
                )}
              </button>
            </div>
          </div>
        )}

        {/* Score Display */}
        {(gameState === 'playing' || gameState === 'ended') && (
          <div className="score-section">
            <h3>Game Stats:</h3>
            <div className="stats-grid">
              <div className="stat">
                <span className="stat-label">Score:</span>
                <span className="stat-value">{score}</span>
              </div>
              <div className="stat">
                <span className="stat-label">Questions Answered:</span>
                <span className="stat-value">{totalAnswered}</span>
              </div>
              <div className="stat">
                <span className="stat-label">Correct Answers:</span>
                <span className="stat-value">{correctAnswers}</span>
              </div>
              <div className="stat">
                <span className="stat-label">Success Rate:</span>
                <span className="stat-value">
                  {totalAnswered > 0 ? Math.round((correctAnswers / totalAnswered) * 100) : 0}%
                </span>
              </div>
            </div>
          </div>
        )}

        {/* Message Display */}
        {message && (
          <div className="message-section">
            <div className={`message ${message.includes('✅') ? 'success' : message.includes('❌') ? 'error' : 'info'}`}>
              {message}
            </div>
          </div>
        )}

        {/* Loading Indicator */}
        {loading && (
          <div className="message-section">
            <div className="message info">
              <div className="loading"></div>
              Processing your request...
            </div>
          </div>
        )}

        {/* Game Instructions */}
        <div className="instructions">
          <h3>How to Play:</h3>
          <ol>
            <li>Click "Start New Game" to begin</li>
            <li>Read the programming riddle carefully</li>
            <li>Type your answer in the input field</li>
            <li>Press Enter or click " Submit Answer"</li>
            <li>Continue playing as long as you want!</li>
            <li>Click " End Game" when you're done to see final results</li>
            <li>Check your progress anytime with "Check Score"</li>
          </ol>
          <p><strong>Note:</strong> The app automatically remembers your game session - no login required!</p>
        </div>
      </main>
    </div>
  );
}

export default App;