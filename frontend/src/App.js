import React, { useState } from 'react';
import './App.css';

function App() {
  const [image, setImage] = useState(`${process.env.PUBLIC_URL}/img1.png`); // Default img1

  // Function to handle button click to fetch img2 from the Flask backend
  const handleTakePicture = async () => {
    try {
      const response = await fetch('http://localhost:5000/take-picture', {
        method: 'POST',
      });
      const data = await response.json();

      if (data.status === 'success') {
        setImage(data.image); // Update the image source to img2
      } else {
        console.error(data.message);
      }
    } catch (error) {
      console.error('Error taking picture:', error);
    }
  };

  return (
    <div className="App">
      <h1>Image Viewer</h1>
      <img src={image} alt="Displayed" />
      <div>
        <button onClick={handleTakePicture}>Take New Picture</button>
      </div>
    </div>
  );
}

export default App;
