AI-Powered Smart Traffic Intelligence Platform
An end-to-end computer vision platform for intelligent traffic monitoring, vehicle analytics, speeding detection, license-plate recognition, and automated evidence generation.

The system combines YOLO11, ByteTrack, OpenCV, calibrated road geometry, a custom license-plate detector, and PaddleOCR to process traffic videos and produce lane-level analytics and violation records.

Demo
A short demo video is available here:

Watch the demo video

Project Overview
This project analyzes traffic video and automatically performs:

Vehicle detection
Multi-object tracking
Lane-based region filtering
Vehicle counting
Lane occupancy analysis
Traffic density estimation
Real-world speed estimation
Speeding violation detection
Best-frame evidence selection
License-plate detection
License-plate OCR
Turkish plate-format correction
CSV violation logging
Evidence image generation
Main Features
Module	Description
Vehicle Detection	Detects cars, motorcycles, buses, and trucks using YOLO11
Multi-Object Tracking	Maintains vehicle identities across frames using ByteTrack
Lane ROI Filtering	Restricts analytics to configured road lanes
Vehicle Counting	Counts vehicles crossing the configured counting line
Traffic Density	Classifies lane traffic as low, medium, or high
Speed Estimation	Estimates speed using calibrated road distance and video timing
Speeding Detection	Flags vehicles exceeding the configured threshold
Best-Frame Selection	Selects the sharpest and largest frame for evidence
Plate Detection	Detects license plates inside vehicle crops
OCR	Reads license plates using PaddleOCR
Plate Cleanup	Corrects common OCR errors using Turkish plate structure
Evidence Logging	Saves annotated frames, crops, plate images, and CSV records
System Architecture
Video Input
    |
    v
YOLO11 Vehicle Detection
    |
    v
ByteTrack Multi-Object Tracking
    |
    v
Lane ROI Filtering
    |
    v
Vehicle Counting and Density Analysis
    |
    v
Speed Estimation
    |
    v
Speeding Violation Detection
    |
    v
Best-Frame Selection
    |
    v
License-Plate Detection
    |
    v
Image Enhancement
    |
    v
PaddleOCR
    |
    v
Turkish Plate Normalization
    |
    v
CSV Records and Evidence Files
Results
Traffic Dashboard
Traffic dashboard

Lane Detection and Vehicle Tracking
Lane detection and tracking

Speed Estimation
Speed estimation

License-Plate Detection
License-plate detection

OCR and Violation Evidence
OCR violation evidence

CSV Violation Records
CSV results

Example Results
The final system successfully produced:

Lane-specific vehicle tracking
Calibrated speed estimation
Speeding violation detection
Best-frame evidence selection
License-plate detection confidence above 0.82
OCR confidence above 0.89
Cleaned Turkish plate outputs such as:
34 8U0 371 -> 34 BUO 371
01 AH 284  -> 01 AH 284
Repository Structure
smart-traffic-intelligence-platform/
|
|-- assets/
|   |-- architecture/
|   |-- gif/
|   |   `-- demo.mp4
|   |-- results/
|   `-- screenshots/
|
|-- config/
|   `-- lanes.json
|
|-- docs/
|-- notebooks/
|-- scripts/
|-- src/
|   |-- counting/
|   |-- detection/
|   |-- lanes/
|   |-- pipeline/
|   |-- speed/
|   |-- traffic/
|   |-- tracking/
|   |-- violations/
|   `-- visualization/
|
|-- tests/
|-- tools/
|-- .gitignore
|-- LICENSE
|-- requirements.txt
`-- README.md
Installation
1. Clone the repository
git clone https://github.com/medo-AAI/smart-traffic-intelligence-platform.git
cd smart-traffic-intelligence-platform
2. Create a virtual environment
python -m venv .venv
Windows:

.venv\Scripts\Activate.ps1
Linux or macOS:

source .venv/bin/activate
3. Install dependencies
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
4. Download model weights
Model files are not stored directly in the repository.

Required models:

YOLO11 vehicle detector
Custom license-plate detector
Update the model paths in your local pipeline configuration before running.

Usage
from pathlib import Path

from src.pipeline.pipeline import TrafficPipeline

PROJECT_ROOT = Path(__file__).resolve().parent

pipeline = TrafficPipeline(
    input_video_path=(
        PROJECT_ROOT
        / "data"
        / "samples"
        / "videos"
        / "day_video.MOV"
    ),
    output_video_path=(
        PROJECT_ROOT
        / "outputs"
        / "processed_video.mp4"
    ),
    vehicle_model_path="yolo11s.pt",
    vehicle_confidence=0.15,
    vehicle_image_size=960,
    lane_config_path=(
        PROJECT_ROOT
        / "config"
        / "lanes.json"
    ),
    left_speed_line_a_y=900,
    left_speed_line_b_y=1250,
    left_speed_distance_metres=77.82,
    right_speed_line_a_y=900,
    right_speed_line_b_y=1250,
    right_speed_distance_metres=77.82,
    speed_limit_kmh=80.0,
    speed_tolerance_kmh=5.0,
    license_plate_model_path=(
        PROJECT_ROOT
        / "runs"
        / "license_plate"
        / "weights"
        / "best.pt"
    ),
    enable_plate_ocr=True,
)

pipeline.run()
You can also run:

python scripts/run_day_demo.py
Generated Outputs
processed_video.mp4
speeding_violations.csv

speeding_evidence/
`-- event_0001_track_3/
    |-- full_frame.jpg
    |-- vehicle_crop.jpg
    |-- vehicle_crop_with_plate.jpg
    |-- plate_crop.jpg
    `-- plate_ocr_input.jpg
Technologies
Python
OpenCV
PyTorch
Ultralytics YOLO11
ByteTrack
PaddlePaddle
PaddleOCR
NumPy
Pandas
Jupyter Notebook
Future Work
Real-time RTSP camera support
Web-based traffic dashboard
PostgreSQL violation database
Red-light violation detection
Wrong-way driving detection
Illegal parking detection
Automatic PDF violation reports
REST API
Docker deployment
Edge-device deployment
Improved plate super-resolution
Additional country plate formats
Notes
Model weights, raw videos, generated outputs, and datasets are excluded from Git.
Speed accuracy depends on correct line placement, real-world distance calibration, camera stability, and video FPS.
OCR performance depends on plate size, lighting, blur, viewing angle, and model quality.
This project is intended for educational, research, and portfolio purposes.
Author
Ahmed
Artificial Intelligence Engineering Student
Computer Vision | Deep Learning | Intelligent Transportation Systems

License
This project is licensed under the MIT License.
