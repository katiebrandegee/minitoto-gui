from flask import Flask, jsonify
import os
import subprocess  # If you're using subprocess to run your Python script

app = Flask(__name__)

# Route to handle picture taking
@app.route('/take-image', methods=['POST'])
def take_picture():
    try:
        # Call your Python script here, e.g., using subprocess
        subprocess.run(["python", "take_image.py"])  # Replace this with your actual script

        img2_path = "img2.jpg"  # Path to the newly generated image
        if os.path.exists(img2_path):
            return jsonify({'status': 'success', 'image': '/img2.jpg'})
        else:
            return jsonify({'status': 'error', 'message': 'Image not found'})

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

if __name__ == '__main__':
    app.run(debug=True)