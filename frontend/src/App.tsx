import { useState, useEffect } from 'react'
import './App.css'

function App() {
  const [message, setMessage] = useState("Loading...")

  useEffect(() => {
    fetch("http://localhost:8000/")
      .then((res) => res.json())
      .then((data) => setMessage(data.message))
      .catch(() => setMessage("Backend not available."));
  }, []);

  return (
    <div>
      <h1>Message from the backend:</h1>
      <p>{message}</p>
    </div>
  )
}

export default App
