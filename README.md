# magic-mouce-project

## Description
The magic-mouce-project is a futuristic hand-gesture cursor control system that allows users to interact with their computer using hand movements. It provides a smooth and intuitive experience similar to that of an Apple trackpad, supporting multi-display setups and achieving up to 60 frames per second.

## Features
- Gesture-based cursor control using hand movements.
- Multi-display support for enhanced productivity.
- Smooth operation with a frame rate of 60 FPS.

## Tech Stack
- Language: Python
- Framework: Custom Project
- Database: Not applicable
- Tools: OpenCV, MediaPipe, NumPy

## Project Structure
```
auto bot/
├── air_mouse.py
├── config.py
├── hand_landmarker.task
├── requirements.txt
└── run.bat
```

## Installation
1. Clone Repository: `git clone <repository_url>`
2. Install Dependencies: `pip install -r auto bot/requirements.txt`
3. Run Project: `python auto bot/air_mouse.py`

## Usage
To use the application, ensure your camera is set up and run the main script. The system will recognize hand gestures to control the cursor. Specific gestures include moving the cursor with the index finger, clicking with pinches, and scrolling with three fingers or the pinky. Use the 'Q' or 'ESC' keys to quit and 'D' to toggle the HUD.

## Future Improvements
- Enhance gesture recognition accuracy and speed.
- Implement additional gestures for more functionality.
- Optimize performance for lower-end hardware.
- Expand compatibility with different operating systems.

## Author
Omkar biradar

## License
MIT License