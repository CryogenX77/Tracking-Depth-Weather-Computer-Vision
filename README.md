# Autonomous Targeting Turret - Computer Vision Software 🤖

![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python)
![Domain](https://img.shields.io/badge/Domain-Robotics-orange)
![License](https://img.shields.io/badge/License-MIT-green)

This repository contains the core software for an autonomous targeting turret. The application uses computer vision to detect and track assigned targets in real-time, calculates precise aiming solutions, and generates commands for a 2-axis servo mechanism.

## 📸 Demo

![Demo GIF of the turret tracking a target]
*A live demonstration of the physical turret acquiring, tracking, and targeting a moving object using this software.*

---

## 🎯 Project Overview

This software serves as the "brain" for a physical 2-axis targeting turret. It's designed to provide a complete, closed-loop targeting solution using a single camera (monocular vision).

**How It Works:**
1.  **Input:** A webcam attached to the turret provides a live video feed.
2.  **Target Acquisition:** The Python script uses MediaPipe to analyze the feed and identify the primary target (in this version, human faces).
3.  **Calculation:**
    * It determines the target's X/Y coordinates relative to the center of the camera's view.
    * It uses monocular depth estimation techniques based on the target's size to approximate its distance.
4.  **Output:** The script generates the precise angular commands required for the X and Y servos to aim the turret directly at the target.
5.  **Monitoring:** A real-time display shows the camera feed, target lock, and all relevant telemetry (depth, servo angles, weather data) for monitoring purposes.

---

## ✨ Features

* **Real-Time Target Acquisition:** Smooth and efficient tracking of targets using MediaPipe.
* **2-Axis Servo Targeting:** Calculates precise angular commands to control a 2-axis servo gimbal.
* **Monocular Depth Estimation:** Approximates target distance using a single camera for ranging and precision.
* **Data-Rich UI Overlay:** Displays critical telemetry including target lock, depth, servo commands, and environmental data.
* **Modular & Extensible:** Built to allow for different targeting modules beyond face detection.

---

## 🛠️ Tech Stack & Hardware

### Software
* **Python 3.11**
* **OpenCV-Python:** For video capture and all UI rendering.
* **MediaPipe:** For high-performance, real-time target detection.
* **NumPy:** For high-speed numerical calculations.
* **Requests:** For fetching environmental data.

### Hardware (Not Included)
* A 2-axis servo-driven gimbal/turret.
* Servo motors (e.g., SG90, MG90S).
* A microcontroller (e.g., Arduino, ESP32) to translate script commands to servo movements.
* A webcam.

---

## 🚀 Getting Started (Software Setup)

Follow these instructions to get the computer vision software running on your local machine.

### Prerequisites

This project uses **Conda** to manage the Python environment. Please [install Anaconda](https://www.anaconda.com/download) if you don't already have it.

### Installation

1.  **Clone the Repository**
    ```bash
    git clone [https://github.com/your-username/your-repo-name.git](https://github.com/your-username/your-repo-name.git)
    cd your-repo-name
    ```

2.  **Create and Activate the Conda Environment**
    This command creates a new, isolated environment with a compatible version of Python.
    ```bash
    # Create the environment
    conda create -n tracker_env python=3.11 -y

    # Activate the environment (required every time you run the project)
    conda activate tracker_env
    ```

3.  **Install Dependencies**
    With the `(tracker_env)` active, install all required packages:
    ```bash
    pip install opencv-python numpy requests mediapipe
    ```

---

## ⚙️ Configuration

Before running, you must configure the OpenWeatherMap API key for the environmental data overlay.

1.  **Get an API Key:** Sign up for a free account at [OpenWeatherMap](https://openweathermap.org/appid).

2.  **Edit the Script:** Open the `cvdep.py` file and find the `CONFIG` class.

3.  **Add Your Key:** Paste your API key into the following line:
    ```python
    OPENWEATHER_API_KEY = "YOUR_API_KEY_HERE"
    ```

---

## ▶️ How to Run the Software

1.  Make sure your Conda environment is active:
    ```bash
    conda activate tracker_env
    ```

2.  Run the main script from your terminal:
    ```bash
    python cvdep.py
    ```

3.  A window will appear showing the camera feed and targeting data. Press the **`q`** key to quit.

---

## 📄 License

This project is licensed under the MIT License. See the `LICENSE` file for details.
