#tanks gpt for ur so so error handling, ui, black magic math, and renaming all my variables!!
#also never do this code format where everything is in one file, i did it cause it was easier to upload files to the raspy pi!

from flask import Flask, jsonify, render_template_string, send_file, request
import board
import busio
import math
import time
import logging
from adafruit_bno08x.i2c import BNO08X_I2C
from adafruit_bno08x import (
    BNO_REPORT_ACCELEROMETER,
    BNO_REPORT_GYROSCOPE,
    BNO_REPORT_MAGNETOMETER,
    BNO_REPORT_ROTATION_VECTOR,
)

app = Flask(__name__)

class DataEndpointFilter(logging.Filter):
    def filter(self, record):
        if hasattr(record, 'getMessage'):
            message = record.getMessage()
            if 'GET /data' in message:
                return False
        return True

werkzeug_logger = logging.getLogger('werkzeug')
werkzeug_logger.addFilter(DataEndpointFilter())

quaternion_offset = {'x': 0, 'y': 0, 'z': 0, 'w': 1}

axis_config = {
    'primary_axis': 'x', 
    'invert': False       
}

calibration_points = {
    'zero_deg': None,
    'ninety_deg': None,
    'minus_ninety_deg': None,
    'is_calibrated': False
}

recording_data = []
is_recording = False
is_playing_back = False
playback_start_time = None
current_playback_index = 0
recording_start_time = None

sensor_status = {
    'sensor_4a': {'connected': False, 'error_count': 0, 'last_error': None},
    'sensor_4b': {'connected': False, 'error_count': 0, 'last_error': None}
}

MAX_ERROR_COUNT = 5

i2c = None
sensor_4a = None
sensor_4b = None
sensor_4b_available = False

def init_i2c():
    global i2c
    try:
        if i2c:
            i2c.deinit()
        i2c = busio.I2C(board.SCL, board.SDA)
        return True
    except Exception as e:
        print(f"Error initializing I2C: {e}")
        return False

def init_sensor_4a():
    global sensor_4a, sensor_status
    try:
        if sensor_4a:
            try:
                sensor_4a.deinit()
            except:
                pass
        
        sensor_4a = BNO08X_I2C(i2c)
        sensor_4a.enable_feature(BNO_REPORT_ACCELEROMETER)
        sensor_4a.enable_feature(BNO_REPORT_GYROSCOPE)
        sensor_4a.enable_feature(BNO_REPORT_MAGNETOMETER)
        sensor_4a.enable_feature(BNO_REPORT_ROTATION_VECTOR)
        
        sensor_status['sensor_4a']['connected'] = True
        sensor_status['sensor_4a']['error_count'] = 0
        sensor_status['sensor_4a']['last_error'] = None
        print("Sensor 4A initialized successfully")
        return True
    except Exception as e:
        print(f"Error initializing sensor 4A: {e}")
        sensor_status['sensor_4a']['connected'] = False
        sensor_status['sensor_4a']['last_error'] = str(e)
        sensor_4a = None
        return False

def init_sensor_4b():
    global sensor_4b, sensor_4b_available, sensor_status
    try:
        if sensor_4b:
            try:
                sensor_4b.deinit()
            except:
                pass
        
        sensor_4b = BNO08X_I2C(i2c, address=0x4B)
        sensor_4b.enable_feature(BNO_REPORT_ACCELEROMETER)
        sensor_4b.enable_feature(BNO_REPORT_GYROSCOPE)
        sensor_4b.enable_feature(BNO_REPORT_MAGNETOMETER)
        sensor_4b.enable_feature(BNO_REPORT_ROTATION_VECTOR)
        
        sensor_4b_available = True
        sensor_status['sensor_4b']['connected'] = True
        sensor_status['sensor_4b']['error_count'] = 0
        sensor_status['sensor_4b']['last_error'] = None
        print("Sensor 4B initialized successfully")
        return True
    except Exception as e:
        print(f"Error initializing sensor 4B: {e}")
        sensor_4b_available = False
        sensor_status['sensor_4b']['connected'] = False
        sensor_status['sensor_4b']['last_error'] = str(e)
        sensor_4b = None
        return False

def init_all_sensors():
    success = True
    
    if not init_i2c():
        return False
    
    if not init_sensor_4a():
        success = False
    
    if not init_sensor_4b():
        pass
    
    return success

def safe_read_sensor_data(sensor_name, sensor_obj):
    if not sensor_obj:
        return None
        
    try:
        accel = sensor_obj.acceleration
        gyro = sensor_obj.gyro
        mag = sensor_obj.magnetic
        quat = sensor_obj.quaternion
        
        # Reset error count on successful read
        sensor_status[sensor_name]['error_count'] = 0
        sensor_status[sensor_name]['connected'] = True
        
        quaternion_obj = None
        if quat:
            quaternion_obj = {
                'x': quat[0],
                'y': quat[1],
                'z': quat[2],
                'w': quat[3]
            }
        
        return {
            'acceleration': accel,
            'gyroscope': gyro,
            'magnetometer': mag,
            'quaternion': quaternion_obj
        }
        
    except Exception as e:
        sensor_status[sensor_name]['error_count'] += 1
        sensor_status[sensor_name]['last_error'] = str(e)
        
        print(f"Error reading {sensor_name}: {e} (error count: {sensor_status[sensor_name]['error_count']})")
        
        if sensor_status[sensor_name]['error_count'] >= MAX_ERROR_COUNT:
            sensor_status[sensor_name]['connected'] = False
            print(f"Sensor {sensor_name} marked as disconnected after {MAX_ERROR_COUNT} consecutive errors")
        
        return None

def attempt_sensor_reconnection(sensor_name):
    print(f"Attempting to reconnect {sensor_name}...")
    
    if sensor_name == 'sensor_4a':
        return init_sensor_4a()
    elif sensor_name == 'sensor_4b':
        return init_sensor_4b()
    else:
        return False

def reconnect_all_sensors():
    print("Attempting to reconnect all sensors...")
    return init_all_sensors()

print("Initializing sensors...")
init_all_sensors()

sensor = sensor_4a

@app.route('/dummy.png')
def serve_dummy():
    return send_file('dummy.png', mimetype='image/png')

@app.route('/')
def index():
    return render_template_string('''
        <html>
        <head>
            <title>BNO085 Live Data - Crash Dummy</title>
            <style>
                body {
                    font-family: Arial, sans-serif;
                    margin: 20px;
                    background-color: #f0f0f0;
                }
                .container {
                    display: flex;
                    gap: 30px;
                    align-items: flex-start;
                }
                .dummy-container {
                    background: white;
                    padding: 20px;
                    border-radius: 10px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                    text-align: center;
                }
                .dummy-head {
                    width: 200px;
                    height: 200px;
                    border: 2px solid #333;
                    border-radius: 10px;
                    margin-bottom: 0;
                    transform-origin: 50% 100%;
                    transition: transform 0.1s ease;
                }
                .neck-container {
                    position: relative;
                    width: 40px;
                    height: 140px;
                    margin: 0 auto;
                    display: flex;
                    flex-direction: column;
                    gap: 8px;
                }
                .neck-segment {
                    width: 40px;
                    height: 20px;
                    background: linear-gradient(to bottom, #ffdbcc 0%, #f4c2a1 50%, #d4a574 100%);
                    border: 2px solid #333;
                    border-radius: 8px;
                    position: relative;
                    box-shadow: inset 0 0 5px rgba(0,0,0,0.1);
                    transform-origin: 50% 100%;
                    transition: transform 0.1s ease;
                }
                .neck-segment:last-child {
                    margin-bottom: 0;
                }
                .neck-segment:first-child {
                    opacity: 0;
                }
                .neck-segment::before {
                    content: '';
                    position: absolute;
                    top: 50%;
                    left: 50%;
                    width: 60%;
                    height: 2px;
                    background: #d4a574;
                    transform: translate(-50%, -50%);
                    border-radius: 1px;
                }
                .neck-top {
                    transform-origin: 50% 100% !important;
                }
                .neck-middle {
                    transform-origin: 50% 50% !important;
                }
                .neck-bottom {
                    transform-origin: 50% 0% !important;
                }
                .head-neck-assembly {
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                }
                .data-container {
                    background: white;
                    padding: 20px;
                    border-radius: 10px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                    flex: 1;
                }
                .reset-btn {
                    background-color: #ff4444;
                    color: white;
                    border: none;
                    padding: 10px 20px;
                    border-radius: 5px;
                    cursor: pointer;
                    font-size: 16px;
                    margin-top: 15px;
                }
                .reset-btn:hover {
                    background-color: #cc3333;
                }
                .calibration-section {
                    margin-top: 20px;
                    padding: 15px;
                    background-color: #f9f9f9;
                    border-radius: 5px;
                    border: 1px solid #ddd;
                }
                .calibration-btn {
                    background-color: #4CAF50;
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 5px;
                    cursor: pointer;
                    font-size: 14px;
                    margin: 5px;
                }
                .calibration-btn:hover {
                    background-color: #45a049;
                }
                .calibration-btn:disabled {
                    background-color: #cccccc;
                    cursor: not-allowed;
                }
                .calibration-status {
                    font-size: 12px;
                    color: #666;
                    margin-top: 5px;
                }
                .rotation-info {
                    margin-top: 10px;
                    font-size: 14px;
                    color: #666;
                }
                .recording-section {
                    margin-top: 20px;
                    padding: 15px;
                    background-color: #f0f8ff;
                    border-radius: 5px;
                    border: 1px solid #ddd;
                }
                .recording-btn {
                    background-color: #dc3545;
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 5px;
                    cursor: pointer;
                    font-size: 14px;
                    margin: 5px;
                }
                .recording-btn:hover {
                    background-color: #c82333;
                }
                .recording-btn:disabled {
                    background-color: #cccccc;
                    cursor: not-allowed;
                }
                .recording-btn.recording {
                    background-color: #ff0000;
                    animation: pulse 1s infinite;
                }
                .recording-btn.playing {
                    background-color: #007bff;
                }
                @keyframes pulse {
                    0% { opacity: 1; }
                    50% { opacity: 0.5; }
                    100% { opacity: 1; }
                }
                .recording-status {
                    font-size: 12px;
                    color: #666;
                    margin-top: 5px;
                }
                .chart-container {
                    margin-top: 15px;
                    background: white;
                    border: 1px solid #ddd;
                    border-radius: 5px;
                    padding: 15px;
                    position: relative;
                }
                .chart-canvas {
                    width: 100%;
                    height: 400px;
                    border: 1px solid #ccc;
                    cursor: crosshair;
                    background: #fafafa;
                }
                .chart-stats {
                    display: flex;
                    justify-content: space-between;
                    margin-top: 10px;
                    font-size: 11px;
                    color: #555;
                }
                .chart-tooltip {
                    position: absolute;
                    background: rgba(0,0,0,0.8);
                    color: white;
                    padding: 5px 8px;
                    border-radius: 3px;
                    font-size: 11px;
                    pointer-events: none;
                    z-index: 1000;
                    display: none;
                }
                .hover-label {
                    text-align: center;
                    font-size: 14px;
                    color: #333;
                    background: #f0f0f0;
                    border: 1px solid #ccc;
                    border-radius: 5px;
                    padding: 8px;
                    margin-top: 10px;
                    min-height: 20px;
                }
                .max-min-display {
                    display: flex;
                    justify-content: space-around;
                    margin: 15px 0;
                    font-weight: bold;
                }
                .max-min-item {
                    text-align: center;
                    padding: 10px;
                    background: #f8f9fa;
                    border-radius: 8px;
                    border: 2px solid #ddd;
                    min-width: 120px;
                }
                .max-accel {
                    border-color: #ff0000;
                    color: #ff0000;
                }
                .min-accel {
                    border-color: #0000ff;
                    color: #0000ff;
                }
                .chart-controls {
                    margin-top: 8px;
                    font-size: 11px;
                }
                .zoom-controls {
                    display: flex;
                    gap: 5px;
                    flex-wrap: wrap;
                }
                .zoom-btn {
                    background-color: #007bff;
                    color: white;
                    border: none;
                    padding: 5px 10px;
                    border-radius: 3px;
                    cursor: pointer;
                    font-size: 11px;
                    transition: background-color 0.2s;
                }
                .zoom-btn:hover {
                    background-color: #0056b3;
                }
                .zoom-btn.auto-scale-active {
                    background-color: #28a745;
                }
                .zoom-btn.auto-scale-active:hover {
                    background-color: #218838;
                }
                .chart-toggle {
                    margin-right: 15px;
                }
                .chart-toggle input[type="checkbox"] {
                    margin-right: 5px;
                }
                .axis-config-section {
                    margin-top: 20px;
                    padding: 15px;
                    background-color: #f8f9fa;
                    border-radius: 5px;
                    border: 1px solid #ddd;
                }
                .axis-config {
                    display: flex;
                    align-items: center;
                    gap: 15px;
                    margin-top: 10px;
                }
                .axis-config label {
                    font-weight: bold;
                    color: #333;
                }
                .axis-config select {
                    padding: 5px 10px;
                    border: 1px solid #ccc;
                    border-radius: 3px;
                    background-color: white;
                    font-size: 14px;
                }
                .axis-config input[type="checkbox"] {
                    margin-right: 5px;
                }
                .sensor-chart-section {
                    margin-bottom: 15px;
                    padding: 10px;
                    background: #fafafa;
                    border: 1px solid #e0e0e0;
                    border-radius: 5px;
                }
                .sensor-chart-section h5 {
                    margin: 0 0 10px 0;
                    color: #333;
                    font-size: 16px;
                }
                .sync-time-display {
                    text-align: center;
                    font-weight: bold;
                    background: #e8f4f8;
                    border: 1px solid #b8daec;
                    border-radius: 5px;
                    padding: 10px;
                    margin-top: 15px;
                }
                .chart-canvas.synchronized {
                    box-shadow: 0 0 5px rgba(0, 123, 255, 0.5);
                    border: 2px solid #007bff;
                }
                .sensor-status-section {
                    margin-top: 20px;
                    padding: 15px;
                    background-color: #fff3cd;
                    border: 1px solid #ffeaa7;
                    border-radius: 5px;
                }
                .sensor-status-item {
                    margin: 5px 0;
                    padding: 8px;
                    border-radius: 3px;
                    font-size: 14px;
                }
                .sensor-connected {
                    background-color: #d4edda;
                    color: #155724;
                    border: 1px solid #c3e6cb;
                }
                .sensor-disconnected {
                    background-color: #f8d7da;
                    color: #721c24;
                    border: 1px solid #f5c6cb;
                }
                .sensor-warning {
                    background-color: #fff3cd;
                    color: #856404;
                    border: 1px solid #ffeaa7;
                }
                .reconnect-btn {
                    background-color: #ffc107;
                    color: #212529;
                    border: none;
                    padding: 10px 20px;
                    border-radius: 5px;
                    cursor: pointer;
                    font-size: 16px;
                    margin-top: 10px;
                    font-weight: bold;
                }
                .reconnect-btn:hover {
                    background-color: #e0a800;
                }
                .reconnect-btn:disabled {
                    background-color: #6c757d;
                    cursor: not-allowed;
                }
                .status-indicator {
                    display: inline-block;
                    width: 10px;
                    height: 10px;
                    border-radius: 50%;
                    margin-right: 8px;
                }
                .status-connected {
                    background-color: #28a745;
                }
                .status-disconnected {
                    background-color: #dc3545;
                }
                .status-warning {
                    background-color: #ffc107;
                }
            </style>
        </head>
        <body>
            <h1>Crash Dummy Head Tracker - BNO085 IMU</h1>
            <div class="container">
                <div class="dummy-container">
                    <h2>Dummy Head (Side Profile)</h2>
                    <div class="head-neck-assembly" id="headNeckAssembly">
                        <img id="dummyHead" class="dummy-head" src="/dummy.png" alt="Dummy Head">
                        <div class="neck-container" id="neckContainer">
                            <div class="neck-segment neck-top" id="neckSeg1"></div>
                            <div class="neck-segment neck-top" id="neckSeg2"></div>
                            <div class="neck-segment neck-middle" id="neckSeg3"></div>
                            <div class="neck-segment neck-bottom" id="neckSeg4"></div>
                            <div class="neck-segment neck-bottom" id="neckSeg5"></div>
                        </div>
                    </div>
                    <div class="rotation-info">
                        <div><span id="rotationLabel">X Rotation</span>: <span id="xRotation">0°</span></div>
                        <div>Raw Quat <span id="rawAxisLabel">X</span>: <span id="xValue">0.0</span></div>
                        <div>Quaternion <span id="quaternionLabel">X</span>: <span id="quatX">0.0</span></div>
                        <div><small>Mode: <span id="calculationMode">Reset Offset</span></small></div>
                    </div>
                    <button class="reset-btn" onclick="resetQuaternion()">Reset Position</button>
                    
                    <div class="axis-config-section">
                        <h3>Axis Configuration</h3>
                        <div class="axis-config">
                            <label for="axisSelect">Primary Axis:</label>
                            <select id="axisSelect" onchange="updateAxisConfig()">
                                <option value="x">X Axis</option>
                                <option value="y">Y Axis</option>
                                <option value="z">Z Axis</option>
                            </select>
                            <label>
                                <input type="checkbox" id="invertAxis" onchange="updateAxisConfig()">
                                Invert Direction
                            </label>
                        </div>
                    </div>
                    
                    <div class="calibration-section">
                        <h3>Calibration</h3>
                        <button class="calibration-btn" onclick="calibrateZero()">Set 0° Position</button>
                        <button class="calibration-btn" onclick="calibrateNinety()">Set 90° Position</button>
                        <button class="calibration-btn" onclick="calibrateMinusNinety()">Set -90° Position</button>
                        <button class="calibration-btn" onclick="clearCalibration()">Clear Calibration</button>
                        <div class="calibration-status">
                            <div>0° Point: <span id="zeroStatus">Not Set</span></div>
                            <div>90° Point: <span id="ninetyStatus">Not Set</span></div>
                            <div>-90° Point: <span id="minusNinetyStatus">Not Set</span></div>
                            <div>Status: <span id="calibrationStatus">Not Calibrated</span></div>
                            <div><small><strong>Tip:</strong> Use all 3 points for best accuracy</small></div>
                        </div>
                    </div>
                    
                    <div class="sensor-status-section">
                        <h3>Sensor Status & Connection</h3>
                        <div class="sensor-status-item" id="sensor4AStatus">
                            <span class="status-indicator status-connected" id="sensor4AIndicator"></span>
                            <strong>Primary Sensor (4A):</strong> <span id="sensor4AText">Checking...</span>
                        </div>
                        <div class="sensor-status-item" id="sensor4BStatus" style="display: none;">
                            <span class="status-indicator status-connected" id="sensor4BIndicator"></span>
                            <strong>Secondary Sensor (4B):</strong> <span id="sensor4BText">Checking...</span>
                        </div>
                        <button class="reconnect-btn" id="reconnectBtn" onclick="reconnectSensors()">Reconnect Sensors</button>
                        <div style="margin-top: 10px; font-size: 12px; color: #666;">
                            <div><strong>Auto-reconnection:</strong> Enabled (attempts reconnection after 5 consecutive errors)</div>
                            <div><strong>Manual reconnection:</strong> Use button above to force reconnection</div>
                        </div>
                    </div>
                    
                    <div class="recording-section">
                        <h3>Recording & Playback</h3>
                        <button class="recording-btn" id="recordBtn" onclick="toggleRecording()">Start Recording</button>
                        <button class="recording-btn" id="playBtn" onclick="playbackRecording()" disabled>Playback</button>
                        <button class="recording-btn" onclick="clearRecording()">Clear Recording</button>
                        <div class="recording-status">
                            <div>Status: <span id="recordingStatus">Ready</span></div>
                            <div>Duration: <span id="recordingDuration">0.0s</span></div>
                            <div>Data Points: <span id="dataPointCount">0</span></div>
                            <div><small><strong>Note:</strong> Recording captures all sensor data and movements</small></div>
                        </div>
                        
                        <div class="chart-container" id="chartContainer" style="display: none;">
                            <h4>Dual Sensor Acceleration vs Time</h4>
                            
                            <div class="sensor-chart-section">
                                <h5>Sensor 4A (Primary)</h5>
                                <div class="max-min-display">
                                    <div class="max-min-item max-accel">
                                        <div>MAX X-ACCEL</div>
                                        <div id="maxAccelDisplay4A">0.0 m/s²</div>
                                    </div>
                                    <div class="max-min-item min-accel">
                                        <div>MIN X-ACCEL</div>
                                        <div id="minAccelDisplay4A">0.0 m/s²</div>
                                    </div>
                                </div>
                                
                                <canvas class="chart-canvas" id="accelChart4A" width="800" height="300"></canvas>
                                
                                <div class="hover-label" id="hoverLabel4A">Hover over the chart to see details</div>
                                
                                <div class="chart-stats">
                                    <div>Max X-Accel: <span id="maxAccel4A">0.0</span> m/s²</div>
                                    <div>Min X-Accel: <span id="minAccel4A">0.0</span> m/s²</div>
                                    <div>Avg X-Accel: <span id="avgAccel4A">0.0</span> m/s²</div>
                                    <div>Current X-Accel: <span id="currentAccel4A">0.0</span> m/s²</div>
                                </div>
                            </div>
                            
                            <div class="sensor-chart-section" id="chart4BSection" style="margin-top: 20px;">
                                <h5>Sensor 4B (Secondary)</h5>
                                <div class="max-min-display">
                                    <div class="max-min-item max-accel">
                                        <div>MAX X-ACCEL</div>
                                        <div id="maxAccelDisplay4B">0.0 m/s²</div>
                                    </div>
                                    <div class="max-min-item min-accel">
                                        <div>MIN X-ACCEL</div>
                                        <div id="minAccelDisplay4B">0.0 m/s²</div>
                                    </div>
                                </div>
                                
                                <canvas class="chart-canvas" id="accelChart4B" width="800" height="300"></canvas>
                                
                                <div class="hover-label" id="hoverLabel4B">Hover over the chart to see details</div>
                                
                                <div class="chart-stats">
                                    <div>Max X-Accel: <span id="maxAccel4B">0.0</span> m/s²</div>
                                    <div>Min X-Accel: <span id="minAccel4B">0.0</span> m/s²</div>
                                    <div>Avg X-Accel: <span id="avgAccel4B">0.0</span> m/s²</div>
                                    <div>Current X-Accel: <span id="currentAccel4B">0.0</span> m/s²</div>
                                </div>
                            </div>
                            
                            <div class="sync-time-display" id="syncTimeDisplay" style="display: none; margin-top: 15px; padding: 10px; background: #e8f4f8; border: 1px solid #b8daec; border-radius: 5px;">
                                <div style="text-align: center; font-weight: bold;">
                                    <div>Synchronized Time: <span id="syncTime">0.0s</span></div>
                                    <div style="display: flex; justify-content: space-around; margin-top: 5px;">
                                        <div>4A Accel: <span id="sync4AAccel">0.0 m/s²</span></div>
                                        <div>4B Accel: <span id="sync4BAccel">0.0 m/s²</span></div>
                                    </div>
                                </div>
                            </div>
                            
                            <div class="chart-controls">
                                <div style="margin-bottom: 10px;">
                                    <strong>Dual Sensor X-Axis Acceleration Charts</strong>
                                </div>
                                <div class="zoom-controls">
                                    <button class="zoom-btn" onclick="zoomInDual()">Zoom In</button>
                                    <button class="zoom-btn" onclick="zoomOutDual()">Zoom Out</button>
                                    <button class="zoom-btn" onclick="zoomHorizontalDual()">H-Zoom</button>
                                    <button class="zoom-btn" onclick="zoomVerticalDual()">V-Zoom</button>
                                    <button class="zoom-btn" onclick="resetZoomDual()">Reset Zoom</button>
                                    <button class="zoom-btn" onclick="autoScaleDual()">Auto Scale</button>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                <div class="data-container">
                    <h2>Live IMU Data</h2>
                    <pre id="data">Loading...</pre>
                </div>
            </div>
            
            <script>
                let quaternionOffset = {x: 0, y: 0, z: 0, w: 1};
                let axisConfig = {primary_axis: 'x', invert: false};
                let calibrationData = {
                    zeroDeg: null,
                    ninetyDeg: null,
                    minusNinetyDeg: null,
                    isCalibrated: false
                };
                let isRecording = false;
                let isPlayingBack = false;
                let recordingStartTime = null;
                let recordedData = [];
                let playbackData = [];
                let playbackIndex = 0;
                let playbackStartTime = null;
                
                let chartData4A = {
                    timestamps: [],
                    x: [],
                    maxAccel: -Infinity, minAccel: Infinity, avgAccel: 0,
                    maxPoint: null, minPoint: null
                };
                let chartData4B = {
                    timestamps: [],
                    x: [],
                    maxAccel: -Infinity, minAccel: Infinity, avgAccel: 0,
                    maxPoint: null, minPoint: null
                };
                let chart4A = null;
                let chart4B = null;
                let zoomLevel = 1;
                let panOffsetX = 0;
                let panOffsetY = 0;
                let horizontalZoom = 1;
                let verticalZoom = 1;
                let autoScaleEnabled = true;
                let syncedTimeValue = null;
                let sensor4BAvailable = false;
                
                let sensorStatus = {
                    sensor_4a: { connected: false, error_count: 0, last_error: null },
                    sensor_4b: { connected: false, error_count: 0, last_error: null }
                };
                let reconnectInProgress = false;
                
                function updateSensorStatus(statusData) {
                    if (statusData && statusData.sensor_status) {
                        sensorStatus = statusData.sensor_status;
                        
                        updateSensorStatusDisplay('4A', sensorStatus.sensor_4a);
                        
                        if (sensorStatus.sensor_4b) {
                            sensor4BAvailable = true;
                            document.getElementById('sensor4BStatus').style.display = 'block';
                            updateSensorStatusDisplay('4B', sensorStatus.sensor_4b);
                        } else {
                            sensor4BAvailable = false;
                            document.getElementById('sensor4BStatus').style.display = 'none';
                        }
                    }
                }
                
                function updateSensorStatusDisplay(sensorId, status) {
                    const statusElement = document.getElementById(`sensor${sensorId}Status`);
                    const indicatorElement = document.getElementById(`sensor${sensorId}Indicator`);
                    const textElement = document.getElementById(`sensor${sensorId}Text`);
                    
                    if (!status) return;
                    
                    if (status.connected) {
                        statusElement.className = 'sensor-status-item sensor-connected';
                        indicatorElement.className = 'status-indicator status-connected';
                        textElement.textContent = 'Connected';
                    } else if (status.error_count > 0 && status.error_count < 5) {
                        statusElement.className = 'sensor-status-item sensor-warning';
                        indicatorElement.className = 'status-indicator status-warning';
                        textElement.textContent = `Warning (${status.error_count} errors)`;
                    } else {
                        statusElement.className = 'sensor-status-item sensor-disconnected';
                        indicatorElement.className = 'status-indicator status-disconnected';
                        textElement.textContent = status.last_error ? `Disconnected: ${status.last_error}` : 'Disconnected';
                    }
                }
                
                function reconnectSensors() {
                    if (reconnectInProgress) return;
                    
                    reconnectInProgress = true;
                    const reconnectBtn = document.getElementById('reconnectBtn');
                    reconnectBtn.disabled = true;
                    reconnectBtn.textContent = 'Reconnecting...';
                    
                    fetch('/reconnect_sensors', {method: 'POST'})
                        .then(response => response.json())
                        .then(data => {
                            console.log('Reconnection result:', data);
                            
                            if (data.sensor_status) {
                                updateSensorStatus({ sensor_status: data.sensor_status });
                            }
                            
                            let message = '';
                            if (data.status === 'success') {
                                message = 'All sensors reconnected successfully!';
                            } else if (data.status === 'partial_success') {
                                message = 'Some sensors reconnected. Check status above.';
                            } else {
                                message = `Reconnection failed: ${data.message}`;
                            }
                            
                            reconnectBtn.textContent = message;
                            setTimeout(() => {
                                reconnectBtn.textContent = 'Reconnect Sensors';
                                reconnectBtn.disabled = false;
                                reconnectInProgress = false;
                            }, 3000);
                        })
                        .catch(error => {
                            console.error('Error reconnecting sensors:', error);
                            reconnectBtn.textContent = 'Reconnection Failed';
                            setTimeout(() => {
                                reconnectBtn.textContent = 'Reconnect Sensors';
                                reconnectBtn.disabled = false;
                                reconnectInProgress = false;
                            }, 3000);
                        });
                }
                
                function resetQuaternion() {
                    fetch('/reset_quaternion', {method: 'POST'})
                        .then(response => {
                            if (!response.ok) {
                                return response.json().then(err => Promise.reject(err));
                            }
                            return response.json();
                        })
                        .then(data => {
                            quaternionOffset = data.offset;
                            console.log('Quaternion reset - new offset:', quaternionOffset);
                        })
                        .catch(error => {
                            console.error('Error resetting quaternion:', error);
                            if (error.error && error.error.includes('not connected')) {
                                alert('Cannot reset quaternion: Primary sensor is not connected. Try reconnecting sensors first.');
                            } else {
                                alert(`Error resetting quaternion: ${error.error || error.message || 'Unknown error'}`);
                            }
                        });
                }
                
                function loadAxisConfig() {
                    fetch('/get_axis_config')
                        .then(response => response.json())
                        .then(data => {
                            axisConfig = data;
                            document.getElementById('axisSelect').value = data.primary_axis;
                            document.getElementById('invertAxis').checked = data.invert;
                            updateAxisLabels();
                            console.log('Loaded axis config:', axisConfig);
                        })
                        .catch(error => {
                            console.error('Error loading axis config:', error);
                        });
                }
                
                function updateAxisConfig() {
                    const primaryAxis = document.getElementById('axisSelect').value;
                    const invert = document.getElementById('invertAxis').checked;
                    
                    axisConfig = {primary_axis: primaryAxis, invert: invert};
                    
                    fetch('/set_axis_config', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify(axisConfig)
                    })
                    .then(response => response.json())
                    .then(data => {
                        console.log('Updated axis config:', data);
                        updateAxisLabels();
                    })
                    .catch(error => {
                        console.error('Error updating axis config:', error);
                    });
                }
                
                function updateAxisLabels() {
                    const axisName = axisConfig.primary_axis.toUpperCase();
                    const inversionText = axisConfig.invert ? ' (Inverted)' : '';
                    
                    document.getElementById('rotationLabel').textContent = `${axisName} Rotation${inversionText}`;
                    document.getElementById('rawAxisLabel').textContent = axisName;
                    document.getElementById('quaternionLabel').textContent = axisName;
                }
                
                function getAxisValue(quaternion, axisConfig) {
                    let value;
                    switch(axisConfig.primary_axis) {
                        case 'x': value = quaternion.x; break;
                        case 'y': value = quaternion.y; break;
                        case 'z': value = quaternion.z; break;
                        default: value = quaternion.x; break;
                    }
                    return axisConfig.invert ? -value : value;
                }
                
                function calibrateZero() {
                    fetch('/calibrate', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({point: 'zero'})
                    })
                    .then(response => {
                        if (!response.ok) {
                            return response.json().then(err => Promise.reject(err));
                        }
                        return response.json();
                    })
                    .then(data => {
                        calibrationData = data.calibration;
                        updateCalibrationStatus();
                        console.log('Zero point calibrated');
                    })
                    .catch(error => {
                        console.error('Error calibrating zero point:', error);
                        if (error.error && error.error.includes('not connected')) {
                            alert('Cannot calibrate: Primary sensor is not connected. Try reconnecting sensors first.');
                        } else {
                            alert(`Error calibrating zero point: ${error.error || error.message || 'Unknown error'}`);
                        }
                    });
                }
                
                function calibrateNinety() {
                    fetch('/calibrate', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({point: 'ninety'})
                    })
                    .then(response => {
                        if (!response.ok) {
                            return response.json().then(err => Promise.reject(err));
                        }
                        return response.json();
                    })
                    .then(data => {
                        calibrationData = data.calibration;
                        updateCalibrationStatus();
                        console.log('Ninety point calibrated');
                    })
                    .catch(error => {
                        console.error('Error calibrating ninety point:', error);
                        if (error.error && error.error.includes('not connected')) {
                            alert('Cannot calibrate: Primary sensor is not connected. Try reconnecting sensors first.');
                        } else {
                            alert(`Error calibrating ninety point: ${error.error || error.message || 'Unknown error'}`);
                        }
                    });
                }
                
                function calibrateMinusNinety() {
                    fetch('/calibrate', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({point: 'minus_ninety'})
                    })
                    .then(response => {
                        if (!response.ok) {
                            return response.json().then(err => Promise.reject(err));
                        }
                        return response.json();
                    })
                    .then(data => {
                        calibrationData = data.calibration;
                        updateCalibrationStatus();
                        console.log('Minus ninety point calibrated');
                    })
                    .catch(error => {
                        console.error('Error calibrating minus ninety point:', error);
                        if (error.error && error.error.includes('not connected')) {
                            alert('Cannot calibrate: Primary sensor is not connected. Try reconnecting sensors first.');
                        } else {
                            alert(`Error calibrating minus ninety point: ${error.error || error.message || 'Unknown error'}`);
                        }
                    });
                }
                
                function clearCalibration() {
                    fetch('/calibrate', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({point: 'clear'})
                    })
                    .then(response => response.json())
                    .then(data => {
                        calibrationData = data.calibration;
                        updateCalibrationStatus();
                        console.log('Calibration cleared');
                    });
                }
                
                function updateCalibrationStatus() {
                    const zero = calibrationData.zeroDeg !== null;
                    const ninety = calibrationData.ninetyDeg !== null;
                    const minusNinety = calibrationData.minusNinetyDeg !== null;
                    
                    document.getElementById('zeroStatus').textContent = 
                        zero ? 'Set (' + calibrationData.zeroDeg.toFixed(3) + ')' : 'Not Set';
                    document.getElementById('ninetyStatus').textContent = 
                        ninety ? 'Set (' + calibrationData.ninetyDeg.toFixed(3) + ')' : 'Not Set';
                    document.getElementById('minusNinetyStatus').textContent = 
                        minusNinety ? 'Set (' + calibrationData.minusNinetyDeg.toFixed(3) + ')' : 'Not Set';
                    
                    let statusText = 'Not Calibrated';
                    if (calibrationData.isCalibrated) {
                        if (zero && ninety && minusNinety) {
                            statusText = 'Full 3-Point (Best Accuracy)';
                        } else if (zero && ninety) {
                            statusText = '2-Point (0° to 90°)';
                        } else if (zero && minusNinety) {
                            statusText = '2-Point (0° to -90°)';
                        } else if (zero) {
                            statusText = '1-Point Offset Only';
                        }
                    }
                    
                    document.getElementById('calibrationStatus').textContent = statusText;
                }
                
                function toggleRecording() {
                    if (isRecording) {
                        stopRecording();
                    } else {
                        startRecording();
                    }
                }
                
                function startRecording() {
                    fetch('/start_recording', {method: 'POST'})
                        .then(response => response.json())
                        .then(data => {
                            if (data.status === 'success') {
                                isRecording = true;
                                recordingStartTime = Date.now();
                                recordedData = [];
                                
                                initChart();
                                document.getElementById('chartContainer').style.display = 'block';
                                
                                const recordBtn = document.getElementById('recordBtn');
                                recordBtn.textContent = 'Stop Recording';
                                recordBtn.classList.add('recording');
                                
                                document.getElementById('recordingStatus').textContent = 'Recording...';
                                document.getElementById('playBtn').disabled = true;
                                
                                console.log('Recording started');
                            }
                        });
                }
                
                function stopRecording() {
                    fetch('/stop_recording', {method: 'POST'})
                        .then(response => response.json())
                        .then(data => {
                            if (data.status === 'success') {
                                isRecording = false;
                                
                                const recordBtn = document.getElementById('recordBtn');
                                recordBtn.textContent = 'Start Recording';
                                recordBtn.classList.remove('recording');
                                
                                document.getElementById('recordingStatus').textContent = 'Recording Saved';
                                document.getElementById('playBtn').disabled = false;
                                
                                console.log('Recording stopped. Duration:', data.duration, 'Data points:', data.dataPoints);
                            }
                        });
                }
                
                function playbackRecording() {
                    if (isPlayingBack) {
                        stopPlayback();
                        return;
                    }
                    
                    fetch('/get_recording')
                        .then(response => response.json())
                        .then(data => {
                            if (data.recording && data.recording.length > 0) {
                                playbackData = data.recording;
                                isPlayingBack = true;
                                playbackIndex = 0;
                                playbackStartTime = Date.now();
                                
                                const playBtn = document.getElementById('playBtn');
                                playBtn.textContent = 'Stop Playback';
                                playBtn.classList.add('playing');
                                
                                document.getElementById('recordingStatus').textContent = 'Playing Back...';
                                document.getElementById('recordBtn').disabled = true;
                                
                                console.log('Playback started. Data points:', playbackData.length);
                            }
                        });
                }
                
                function stopPlayback() {
                    isPlayingBack = false;
                    
                    const playBtn = document.getElementById('playBtn');
                    playBtn.textContent = 'Playback';
                    playBtn.classList.remove('playing');
                    
                    document.getElementById('recordingStatus').textContent = 'Playback Stopped';
                    document.getElementById('recordBtn').disabled = false;
                }
                
                function clearRecording() {
                    fetch('/clear_recording', {method: 'POST'})
                        .then(response => response.json())
                        .then(data => {
                            if (data.status === 'success') {
                                isRecording = false;
                                isPlayingBack = false;
                                recordedData = [];
                                playbackData = [];
                                
                                clearChart();
                                document.getElementById('chartContainer').style.display = 'none';
                                
                                const recordBtn = document.getElementById('recordBtn');
                                const playBtn = document.getElementById('playBtn');
                                
                                recordBtn.textContent = 'Start Recording';
                                recordBtn.classList.remove('recording');
                                recordBtn.disabled = false;
                                
                                playBtn.textContent = 'Playback';
                                playBtn.classList.remove('playing');
                                playBtn.disabled = true;
                                
                                document.getElementById('recordingStatus').textContent = 'Ready';
                                document.getElementById('recordingDuration').textContent = '0.0s';
                                document.getElementById('dataPointCount').textContent = '0';
                                
                                console.log('Recording cleared');
                            }
                        });
                }
                fetch('/get_calibration')
                    .then(response => response.json())
                    .then(data => {
                        calibrationData = data.calibration;
                        updateCalibrationStatus();
                    });
                
                loadAxisConfig();
                
                fetch('/sensor_status')
                    .then(response => response.json())
                    .then(data => {
                        updateSensorStatus(data);
                    })
                    .catch(error => {
                        console.error('Error loading sensor status:', error);
                    });
                
                function initChart() {
                    const canvas4A = document.getElementById('accelChart4A');
                    if (canvas4A) {
                        chart4A = canvas4A.getContext('2d');
                        setupChartEventListeners(canvas4A, '4A');
                    }
                    
                    const canvas4B = document.getElementById('accelChart4B');
                    if (canvas4B) {
                        chart4B = canvas4B.getContext('2d');
                        setupChartEventListeners(canvas4B, '4B');
                    }
                    
                    chartData4A = {
                        timestamps: [],
                        x: [],
                        maxAccel: -Infinity, minAccel: Infinity, avgAccel: 0,
                        maxPoint: null, minPoint: null
                    };
                    
                    chartData4B = {
                        timestamps: [],
                        x: [],
                        maxAccel: -Infinity, minAccel: Infinity, avgAccel: 0,
                        maxPoint: null, minPoint: null
                    };
                    
                    zoomLevel = 1;
                    panOffsetX = 0;
                    panOffsetY = 0;
                    horizontalZoom = 1;
                    verticalZoom = 1;
                    autoScaleEnabled = true;
                    syncedTimeValue = null;
                }
                
                function setupChartEventListeners(canvas, sensorId) {
                    canvas.addEventListener('mousemove', (e) => handleChartHoverDual(e, sensorId));
                    canvas.addEventListener('mouseleave', () => hideHoverLabelDual(sensorId));
                    canvas.addEventListener('click', (e) => handleChartClickDual(e, sensorId));
                    canvas.addEventListener('wheel', handleWheelDual);
                    
                    let isDragging = false;
                    let lastMouseX = 0;
                    let lastMouseY = 0;
                    
                    canvas.addEventListener('mousedown', (e) => {
                        isDragging = true;
                        lastMouseX = e.clientX;
                        lastMouseY = e.clientY;
                        canvas.style.cursor = 'grabbing';
                    });
                    
                    canvas.addEventListener('mousemove', (e) => {
                        if (isDragging && (horizontalZoom > 1 || verticalZoom > 1)) {
                            const deltaX = e.clientX - lastMouseX;
                            const deltaY = e.clientY - lastMouseY;
                            
                            const timeRange = chartData4A.timestamps.length > 0 ? 
                                (Math.max(...chartData4A.timestamps) - Math.min(...chartData4A.timestamps)) : 1000;
                            panOffsetX -= (deltaX / canvas.width) * (timeRange / horizontalZoom);
                            panOffsetY += (deltaY / canvas.height) * 10; 
                            
                            lastMouseX = e.clientX;
                            lastMouseY = e.clientY;
                            
                            drawChartDual();
                        }
                    });
                    
                    canvas.addEventListener('mouseup', () => {
                        isDragging = false;
                        canvas.style.cursor = 'crosshair';
                    });
                    
                    canvas.addEventListener('mouseleave', () => {
                        isDragging = false;
                        canvas.style.cursor = 'crosshair';
                    });
                }
                
                function clearChart() {
                    chartData4A = {
                        timestamps: [],
                        x: [],
                        maxAccel: -Infinity, minAccel: Infinity, avgAccel: 0,
                        maxPoint: null, minPoint: null
                    };
                    
                    chartData4B = {
                        timestamps: [],
                        x: [],
                        maxAccel: -Infinity, minAccel: Infinity, avgAccel: 0,
                        maxPoint: null, minPoint: null
                    };
                    
                    zoomLevel = 1;
                    panOffsetX = 0;
                    panOffsetY = 0;
                    horizontalZoom = 1;
                    verticalZoom = 1;
                    autoScaleEnabled = true;
                    syncedTimeValue = null;
                    
                    const canvas4A = document.getElementById('accelChart4A');
                    const canvas4B = document.getElementById('accelChart4B');
                    
                    if (chart4A && canvas4A) {
                        chart4A.clearRect(0, 0, canvas4A.width, canvas4A.height);
                    }
                    if (chart4B && canvas4B) {
                        chart4B.clearRect(0, 0, canvas4B.width, canvas4B.height);
                    }
                    
                    document.getElementById('maxAccelDisplay4A').textContent = '0.0 m/s²';
                    document.getElementById('minAccelDisplay4A').textContent = '0.0 m/s²';
                    document.getElementById('hoverLabel4A').innerHTML = 'Hover over the chart to see details';
                    
                    if (sensor4BAvailable) {
                        document.getElementById('maxAccelDisplay4B').textContent = '0.0 m/s²';
                        document.getElementById('minAccelDisplay4B').textContent = '0.0 m/s²';
                        document.getElementById('hoverLabel4B').innerHTML = 'Hover over the chart to see details';
                    }
                    
                    document.getElementById('syncTimeDisplay').style.display = 'none';
                    
                    const buttons = document.querySelectorAll('.zoom-btn');
                    buttons.forEach(btn => {
                        if (btn.textContent.includes('Scale')) {
                            btn.textContent = 'Manual Scale';
                            btn.classList.add('auto-scale-active');
                        }
                    });
                    
                    updateChartStatsDual();
                }
                
                function addChartData(timestamp, data) {
                    if (!data) return;
                    
                    if (data.sensor_4a && data.sensor_4a.acceleration) {
                        const x4A = data.sensor_4a.acceleration[0] || 0;
                        
                        chartData4A.timestamps.push(timestamp);
                        chartData4A.x.push(x4A);
                        
                        if (x4A > chartData4A.maxAccel) {
                            chartData4A.maxAccel = x4A;
                            chartData4A.maxPoint = {timestamp, magnitude: x4A, x: x4A};
                        }
                        if (x4A < chartData4A.minAccel) {
                            chartData4A.minAccel = x4A;
                            chartData4A.minPoint = {timestamp, magnitude: x4A, x: x4A};
                        }
                        
                        const sum4A = chartData4A.x.reduce((a, b) => a + b, 0);
                        chartData4A.avgAccel = sum4A / chartData4A.x.length;
                    }
                    
                    if (sensor4BAvailable && data.sensor_4b && data.sensor_4b.acceleration) {
                        const x4B = data.sensor_4b.acceleration[0] || 0;
                        
                        chartData4B.timestamps.push(timestamp);
                        chartData4B.x.push(x4B);
                        
                        if (x4B > chartData4B.maxAccel) {
                            chartData4B.maxAccel = x4B;
                            chartData4B.maxPoint = {timestamp, magnitude: x4B, x: x4B};
                        }
                        if (x4B < chartData4B.minAccel) {
                            chartData4B.minAccel = x4B;
                            chartData4B.minPoint = {timestamp, magnitude: x4B, x: x4B};
                        }
                        
                        const sum4B = chartData4B.x.reduce((a, b) => a + b, 0);
                        chartData4B.avgAccel = sum4B / chartData4B.x.length;
                    }
                    
                    drawChartDual();
                    updateChartStatsDual();
                }
                
                function drawChartDual() {
                    drawSingleChart(chart4A, chartData4A, 'accelChart4A', 'Sensor 4A X-Axis Acceleration vs Time');
                    
                    if (sensor4BAvailable && chart4B) {
                        drawSingleChart(chart4B, chartData4B, 'accelChart4B', 'Sensor 4B X-Axis Acceleration vs Time');
                    }
                }
                
                function drawSingleChart(chartContext, chartData, canvasId, title) {
                    if (!chartContext || chartData.timestamps.length === 0) return;
                    
                    const canvas = document.getElementById(canvasId);
                    const width = canvas.width;
                    const height = canvas.height;
                    
                    chartContext.clearRect(0, 0, width, height);
                    
                    const timeMin = Math.min(...chartData.timestamps);
                    const timeMax = Math.max(...chartData.timestamps);
                    const timeRange = (timeMax - timeMin) || 1;
                    
                    const visibleTimeRange = timeRange / horizontalZoom;
                    const timeStart = timeMin + panOffsetX;
                    const timeEnd = timeStart + visibleTimeRange;
                    
                    let dataMin, dataMax;
                    if (autoScaleEnabled) {
                        const visibleData = chartData.x.filter((_, i) => 
                            chartData.timestamps[i] >= timeStart && chartData.timestamps[i] <= timeEnd
                        );
                        if (visibleData.length > 0) {
                            dataMin = Math.min(...visibleData);
                            dataMax = Math.max(...visibleData);
                        } else {
                            dataMin = Math.min(...chartData.x);
                            dataMax = Math.max(...chartData.x);
                        }
                    } else {
                        dataMin = Math.min(...chartData.x);
                        dataMax = Math.max(...chartData.x);
                    }
                    
                    const dataRange = (dataMax - dataMin) || 1;
                    const dataCenter = (dataMin + dataMax) / 2;
                    
                    const visibleDataRange = dataRange / verticalZoom;
                    const visibleDataMin = dataCenter - visibleDataRange / 2 + panOffsetY;
                    const visibleDataMax = dataCenter + visibleDataRange / 2 + panOffsetY;
                    
                    const padding = 50;
                    
                    chartContext.strokeStyle = '#e0e0e0';
                    chartContext.lineWidth = 1;
                    for (let i = 0; i <= 10; i++) {
                        const x = padding + (i / 10) * (width - 2 * padding);
                        chartContext.beginPath();
                        chartContext.moveTo(x, padding);
                        chartContext.lineTo(x, height - padding);
                        chartContext.stroke();
                        
        
                        const timeValue = timeStart + (i / 10) * visibleTimeRange;
                        chartContext.fillStyle = '#666';
                        chartContext.font = '10px Arial';
                        chartContext.textAlign = 'center';
                        chartContext.fillText((timeValue / 1000).toFixed(1) + 's', x, height - padding + 15);
                    }
                    
                    const zeroY = height - padding - ((0 - visibleDataMin) / (visibleDataMax - visibleDataMin)) * (height - 2 * padding);
                    if (zeroY >= padding && zeroY <= height - padding) {
                        chartContext.strokeStyle = '#ccc';
                        chartContext.lineWidth = 1;
                        chartContext.setLineDash([5, 5]);
                        chartContext.beginPath();
                        chartContext.moveTo(padding, zeroY);
                        chartContext.lineTo(width - padding, zeroY);
                        chartContext.stroke();
                        chartContext.setLineDash([]);
                    }
                    
                    chartContext.strokeStyle = '#333';
                    chartContext.lineWidth = 2;
                    chartContext.beginPath();
                    chartContext.moveTo(padding, height - padding);
                    chartContext.lineTo(width - padding, height - padding);
                    chartContext.stroke();
                    
                    chartContext.fillStyle = '#666';
                    chartContext.font = '10px Arial';
                    chartContext.textAlign = 'right';
                    for (let i = 0; i <= 5; i++) {
                        const y = padding + (i / 5) * (height - 2 * padding);
                        const accelValue = visibleDataMax - (i / 5) * (visibleDataMax - visibleDataMin);
                        chartContext.fillText(accelValue.toFixed(1), padding - 5, y + 3);
                    }
                    
                    const lineColor = canvasId.includes('4A') ? '#ff4444' : '#4444ff';
                    chartContext.strokeStyle = lineColor;
                    chartContext.lineWidth = 2;
                    chartContext.beginPath();
                    
                    let firstPoint = true;
                    chartData.x.forEach((value, i) => {
                        const timestamp = chartData.timestamps[i];
                        
                        if (timestamp >= timeStart && timestamp <= timeEnd) {
                            const x = padding + ((timestamp - timeStart) / visibleTimeRange) * (width - 2 * padding);
                            const y = height - padding - ((value - visibleDataMin) / (visibleDataMax - visibleDataMin)) * (height - 2 * padding);
                            
                            if (firstPoint) {
                                chartContext.moveTo(x, y);
                                firstPoint = false;
                            } else {
                                chartContext.lineTo(x, y);
                            }
                        }
                    });
                    
                    chartContext.stroke();
                    
                    if (chartData.maxPoint && chartData.maxPoint.timestamp >= timeStart && chartData.maxPoint.timestamp <= timeEnd) {
                        drawMarkerDual(chartContext, chartData.maxPoint, 'MAX', '#ff0000', timeStart, visibleTimeRange, visibleDataMin, visibleDataMax - visibleDataMin, width, height, padding);
                    }
                    if (chartData.minPoint && chartData.minPoint.timestamp >= timeStart && chartData.minPoint.timestamp <= timeEnd) {
                        drawMarkerDual(chartContext, chartData.minPoint, 'MIN', '#0000ff', timeStart, visibleTimeRange, visibleDataMin, visibleDataMax - visibleDataMin, width, height, padding);
                    }
                    
                    if (syncedTimeValue !== null && syncedTimeValue >= timeStart && syncedTimeValue <= timeEnd) {
                        const syncX = padding + ((syncedTimeValue - timeStart) / visibleTimeRange) * (width - 2 * padding);
                        chartContext.strokeStyle = '#007bff';
                        chartContext.lineWidth = 2;
                        chartContext.setLineDash([10, 5]);
                        chartContext.beginPath();
                        chartContext.moveTo(syncX, padding);
                        chartContext.lineTo(syncX, height - padding);
                        chartContext.stroke();
                        chartContext.setLineDash([]);
                        
                        canvas.classList.add('synchronized');
                    } else {
                        canvas.classList.remove('synchronized');
                    }
                    
                    chartContext.fillStyle = '#333';
                    chartContext.font = 'bold 14px Arial';
                    chartContext.textAlign = 'center';
                    chartContext.fillText(title, width / 2, 25);
                    
                    chartContext.save();
                    chartContext.translate(15, height / 2);
                    chartContext.rotate(-Math.PI / 2);
                    chartContext.font = '12px Arial';
                    chartContext.fillText('Acceleration (m/s²)', 0, 0);
                    chartContext.restore();
                    
                    chartContext.font = '12px Arial';
                    chartContext.textAlign = 'center';
                    chartContext.fillText('Time (seconds)', width / 2, height - 10);
                }
                
                function drawMarkerDual(chartContext, point, label, color, timeMin, timeRange, dataMin, dataRange, width, height, padding) {
                    const x = padding + ((point.timestamp - timeMin) / timeRange) * (width - 2 * padding);
                    const y = height - padding - ((point.x - dataMin) / dataRange) * (height - 2 * padding);
                    
                    chartContext.fillStyle = color;
                    chartContext.beginPath();
                    chartContext.arc(x, y, 4, 0, 2 * Math.PI);
                    chartContext.fill();
                    
                    chartContext.fillStyle = '#000';
                    chartContext.font = '10px Arial';
                    chartContext.textAlign = 'left';
                    chartContext.fillText(label, x + 6, y - 6);
                }
                
                function handleChartHoverDual(event, sensorId) {
                    const chartData = sensorId === '4A' ? chartData4A : chartData4B;
                    
                    if (chartData.timestamps.length === 0) return;
                    
                    const canvas = document.getElementById(`accelChart${sensorId}`);
                    const rect = canvas.getBoundingClientRect();
                    const mouseX = event.clientX - rect.left;
                    const mouseY = event.clientY - rect.top;
                    
                    const padding = 50;
                    const width = canvas.width;
                    const height = canvas.height;
                    
                    if (mouseX < padding || mouseX > width - padding || mouseY < padding || mouseY > height - padding) {
                        hideHoverLabelDual(sensorId);
                        return;
                    }
                    
                    const timeMin = Math.min(...chartData.timestamps);
                    const timeMax = Math.max(...chartData.timestamps);
                    const timeRange = (timeMax - timeMin) || 1;
                    const visibleTimeRange = timeRange / horizontalZoom;
                    const timeStart = timeMin + panOffsetX;
                    
                    const relativeX = (mouseX - padding) / (width - 2 * padding);
                    const targetTime = timeStart + relativeX * visibleTimeRange;
                    
                    let closestIndex = 0;
                    let closestDistance = Math.abs(chartData.timestamps[0] - targetTime);
                    
                    for (let i = 1; i < chartData.timestamps.length; i++) {
                        const distance = Math.abs(chartData.timestamps[i] - targetTime);
                        if (distance < closestDistance) {
                            closestDistance = distance;
                            closestIndex = i;
                        }
                    }
                    
                    const hoverLabel = document.getElementById(`hoverLabel${sensorId}`);
                    const time = (chartData.timestamps[closestIndex] / 1000).toFixed(2);
                    const acceleration = chartData.x[closestIndex].toFixed(2);
                    
                    hoverLabel.innerHTML = `Time: ${time}s | Acceleration: ${acceleration} m/s²`;
                    
                    if (sensor4BAvailable) {
                        syncedTimeValue = chartData.timestamps[closestIndex];
                        
                        const otherSensorId = sensorId === '4A' ? '4B' : '4A';
                        const otherChartData = sensorId === '4A' ? chartData4B : chartData4A;
                        
                        if (otherChartData.timestamps.length > 0) {
                            let closestOtherIndex = 0;
                            let closestOtherDistance = Math.abs(otherChartData.timestamps[0] - syncedTimeValue);
                            
                            for (let i = 1; i < otherChartData.timestamps.length; i++) {
                                const distance = Math.abs(otherChartData.timestamps[i] - syncedTimeValue);
                                if (distance < closestOtherDistance) {
                                    closestOtherDistance = distance;
                                    closestOtherIndex = i;
                                }
                            }
                            
                            document.getElementById('syncTime').textContent = (syncedTimeValue / 1000).toFixed(2) + 's';
                            document.getElementById('sync4AAccel').textContent = (sensorId === '4A' ? 
                                chartData.x[closestIndex] : 
                                chartData4A.x[closestOtherIndex] || 0).toFixed(2) + ' m/s²';
                            document.getElementById('sync4BAccel').textContent = (sensorId === '4B' ? 
                                chartData.x[closestIndex] : 
                                chartData4B.x[closestOtherIndex] || 0).toFixed(2) + ' m/s²';
                            
                            document.getElementById('syncTimeDisplay').style.display = 'block';
                        }
                        
                        drawChartDual();
                    }
                }
                
                function hideHoverLabelDual(sensorId) {
                    document.getElementById(`hoverLabel${sensorId}`).innerHTML = 'Hover over the chart to see details';
                    
                    if (syncedTimeValue === null) {
                        document.getElementById('syncTimeDisplay').style.display = 'none';
                    }
                }
                
                function handleChartClickDual(event, sensorId) {
                    const chartData = sensorId === '4A' ? chartData4A : chartData4B;
                    
                    if (chartData.timestamps.length === 0) return;
                    
                    const canvas = document.getElementById(`accelChart${sensorId}`);
                    const rect = canvas.getBoundingClientRect();
                    const mouseX = event.clientX - rect.left;
                    const mouseY = event.clientY - rect.top;
                    
                    const padding = 50;
                    const width = canvas.width;
                    const height = canvas.height;
                    
                    if (mouseX < padding || mouseX > width - padding || mouseY < padding || mouseY > height - padding) {
                        syncedTimeValue = null;
                        document.getElementById('syncTimeDisplay').style.display = 'none';
                        drawChartDual();
                        return;
                    }
                    
                    const timeMin = Math.min(...chartData.timestamps);
                    const timeMax = Math.max(...chartData.timestamps);
                    const timeRange = (timeMax - timeMin) || 1;
                    const visibleTimeRange = timeRange / horizontalZoom;
                    const timeStart = timeMin + panOffsetX;
                    
                    const relativeX = (mouseX - padding) / (width - 2 * padding);
                    const targetTime = timeStart + relativeX * visibleTimeRange;
                    
                    let closestIndex = 0;
                    let closestDistance = Math.abs(chartData.timestamps[0] - targetTime);
                    
                    for (let i = 1; i < chartData.timestamps.length; i++) {
                        const distance = Math.abs(chartData.timestamps[i] - targetTime);
                        if (distance < closestDistance) {
                            closestDistance = distance;
                            closestIndex = i;
                        }
                    }
                    
                    syncedTimeValue = chartData.timestamps[closestIndex];
                    
                    if (sensor4BAvailable) {
                        const otherChartData = sensorId === '4A' ? chartData4B : chartData4A;
                        
                        if (otherChartData.timestamps.length > 0) {
                            let closestOtherIndex = 0;
                            let closestOtherDistance = Math.abs(otherChartData.timestamps[0] - syncedTimeValue);
                            
                            for (let i = 1; i < otherChartData.timestamps.length; i++) {
                                const distance = Math.abs(otherChartData.timestamps[i] - syncedTimeValue);
                                if (distance < closestOtherDistance) {
                                    closestOtherDistance = distance;
                                    closestOtherIndex = i;
                                }
                            }
                            
                            document.getElementById('syncTime').textContent = (syncedTimeValue / 1000).toFixed(2) + 's';
                            document.getElementById('sync4AAccel').textContent = (sensorId === '4A' ? 
                                chartData.x[closestIndex] : 
                                chartData4A.x[closestOtherIndex] || 0).toFixed(2) + ' m/s²';
                            document.getElementById('sync4BAccel').textContent = (sensorId === '4B' ? 
                                chartData.x[closestIndex] : 
                                chartData4B.x[closestOtherIndex] || 0).toFixed(2) + ' m/s²';
                            
                            document.getElementById('syncTimeDisplay').style.display = 'block';
                        }
                    }
                    
                    drawChartDual();
                }
                
                function handleWheelDual(event) {
                    event.preventDefault();
                    
                    if (event.deltaY < 0) {
                        zoomInDual();
                    } else {
                        zoomOutDual();
                    }
                }
                
                function zoomInDual() {
                    horizontalZoom *= 1.2;
                    verticalZoom *= 1.2;
                    drawChartDual();
                }
                
                function zoomOutDual() {
                    horizontalZoom /= 1.2;
                    verticalZoom /= 1.2;
                    
                    if (horizontalZoom < 1) horizontalZoom = 1;
                    if (verticalZoom < 1) verticalZoom = 1;
                    
                    drawChartDual();
                }
                
                function zoomHorizontalDual() {
                    horizontalZoom *= 1.5;
                    drawChartDual();
                }
                
                function zoomVerticalDual() {
                    verticalZoom *= 1.5;
                    drawChartDual();
                }
                
                function resetZoomDual() {
                    zoomLevel = 1;
                    panOffsetX = 0;
                    panOffsetY = 0;
                    horizontalZoom = 1;
                    verticalZoom = 1;
                    autoScaleEnabled = true;
                    drawChartDual();
                }
                
                function autoScaleDual() {
                    autoScaleEnabled = !autoScaleEnabled;
                    
                    const buttons = document.querySelectorAll('.zoom-btn');
                    let autoScaleButton = null;
                    
                    buttons.forEach(btn => {
                        if (btn.textContent.includes('Scale')) {
                            autoScaleButton = btn;
                        }
                    });
                    
                    if (autoScaleButton) {
                        if (autoScaleEnabled) {
                            autoScaleButton.textContent = 'Manual Scale';
                            autoScaleButton.classList.add('auto-scale-active');
                        } else {
                            autoScaleButton.textContent = 'Auto Scale';
                            autoScaleButton.classList.remove('auto-scale-active');
                        }
                    }
                    
                    drawChartDual();
                }
                
                function updateChartStatsDual() {
                    document.getElementById('maxAccel4A').textContent = chartData4A.maxAccel.toFixed(2);
                    document.getElementById('minAccel4A').textContent = chartData4A.minAccel.toFixed(2);
                    document.getElementById('avgAccel4A').textContent = chartData4A.avgAccel.toFixed(2);
                    
                    document.getElementById('maxAccelDisplay4A').textContent = chartData4A.maxAccel.toFixed(2) + ' m/s²';
                    document.getElementById('minAccelDisplay4A').textContent = chartData4A.minAccel.toFixed(2) + ' m/s²';
                    
                    if (chartData4A.x.length > 0) {
                        const current4A = chartData4A.x[chartData4A.x.length - 1];
                        document.getElementById('currentAccel4A').textContent = current4A.toFixed(2);
                    }
                    
                    if (sensor4BAvailable) {
                        document.getElementById('maxAccel4B').textContent = chartData4B.maxAccel.toFixed(2);
                        document.getElementById('minAccel4B').textContent = chartData4B.minAccel.toFixed(2);
                        document.getElementById('avgAccel4B').textContent = chartData4B.avgAccel.toFixed(2);
                        
                        document.getElementById('maxAccelDisplay4B').textContent = chartData4B.maxAccel.toFixed(2) + ' m/s²';
                        document.getElementById('minAccelDisplay4B').textContent = chartData4B.minAccel.toFixed(2) + ' m/s²';
                        
                        if (chartData4B.x.length > 0) {
                            const current4B = chartData4B.x[chartData4B.x.length - 1];
                            document.getElementById('currentAccel4B').textContent = current4B.toFixed(2);
                        }
                    }
                }
                
                function lerp(value, fromMin, fromMax, toMin, toMax) {
                    const ratio = (value - fromMin) / (fromMax - fromMin);
                    return toMin + ratio * (toMax - toMin);
                }
                
                function calculateRotation(axisValue) {
                    if (!calibrationData.isCalibrated) {
                        const offsetValue = getOffsetForAxis();
                        return (axisValue - offsetValue) * 180;
                    }
                    
                    const points = [];
                    if (calibrationData.zeroDeg !== null) {
                        points.push({ sensor: calibrationData.zeroDeg, angle: 0 });
                    }
                    if (calibrationData.ninetyDeg !== null) {
                        points.push({ sensor: calibrationData.ninetyDeg, angle: 90 });
                    }
                    if (calibrationData.minusNinetyDeg !== null) {
                        points.push({ sensor: calibrationData.minusNinetyDeg, angle: -90 });
                    }
                    
                    points.sort((a, b) => a.sensor - b.sensor);
                    
                    if (points.length === 1) {
                        const offsetValue = axisValue - points[0].sensor;
                        return offsetValue * 180 + points[0].angle;
                    }
                    
                    if (points.length >= 2) {
                        if (axisValue <= points[0].sensor) {
                            return lerp(axisValue, points[0].sensor, points[1].sensor, points[0].angle, points[1].angle);
                        } else if (axisValue >= points[points.length - 1].sensor) {
                            const p1 = points[points.length - 2];
                            const p2 = points[points.length - 1];
                            return lerp(axisValue, p1.sensor, p2.sensor, p1.angle, p2.angle);
                        } else {
                            for (let i = 0; i < points.length - 1; i++) {
                                if (axisValue >= points[i].sensor && axisValue <= points[i + 1].sensor) {
                                    return lerp(axisValue, points[i].sensor, points[i + 1].sensor, points[i].angle, points[i + 1].angle);
                                }
                            }
                        }
                    }
                    
                    return axisValue * 180;
                }
                
                function getOffsetForAxis() {
                    switch(axisConfig.primary_axis) {
                        case 'x': return quaternionOffset.x;
                        case 'y': return quaternionOffset.y;
                        case 'z': return quaternionOffset.z;
                        default: return quaternionOffset.x;
                    }
                }
                
                function updateAxisLabels() {
                    const axisName = axisConfig.primary_axis.toUpperCase();
                    const invertText = axisConfig.invert ? ' (Inverted)' : '';
                    
                    document.getElementById('rotationLabel').textContent = `${axisName} Rotation${invertText}`;
                    document.getElementById('rawAxisLabel').textContent = axisName;
                    document.getElementById('quaternionLabel').textContent = axisName;
                }
                
                setInterval(async () => {
                    try {
                        let json;
                        
                        if (isPlayingBack && playbackData.length > 0) {
                            const currentTime = Date.now() - playbackStartTime;
                            
                            while (playbackIndex < playbackData.length - 1 && 
                                   playbackData[playbackIndex + 1].timestamp <= currentTime) {
                                playbackIndex++;
                            }
                            
                            if (playbackIndex >= playbackData.length - 1) {
                                stopPlayback();
                                return;
                            }
                            
                            json = playbackData[playbackIndex].data;
                            
                            const progress = ((playbackIndex / playbackData.length) * 100).toFixed(1);
                            document.getElementById('recordingStatus').textContent = `Playing Back... ${progress}%`;
                        } else {
                            const res = await fetch('/data');
                            json = await res.json();
                            
                            if (json.sensor_status) {
                                updateSensorStatus(json);
                            }
                            
                            sensor4BAvailable = json.sensor_4b !== null;
                            
                            const chart4BSection = document.getElementById('chart4BSection');
                            if (chart4BSection) {
                                chart4BSection.style.display = sensor4BAvailable ? 'block' : 'none';
                            }
                            
                            if (isRecording) {
                                const timestamp = Date.now() - recordingStartTime;
                                recordedData.push({
                                    timestamp: timestamp,
                                    data: json
                                });
                                
                                addChartData(timestamp, json);
                                
                                const duration = (timestamp / 1000).toFixed(1);
                                document.getElementById('recordingDuration').textContent = duration + 's';
                                document.getElementById('dataPointCount').textContent = recordedData.length;
                            }
                        }
                        
                        document.getElementById('data').textContent = JSON.stringify(json, null, 2);
                        
                        const primaryQuaternion = json.quaternion || (json.sensor_4a && json.sensor_4a.quaternion);
                        
                        if (primaryQuaternion && primaryQuaternion.w !== null) {
                            const q = primaryQuaternion;
                            
                            const axisValue = getAxisValue(q, axisConfig);
                            
                  
                            const rotationDegrees = calculateRotation(axisValue);
                            
                           
                            const axisName = axisConfig.primary_axis.toUpperCase();
                            document.getElementById('xRotation').textContent = rotationDegrees.toFixed(1) + '°';
                            document.getElementById('xValue').textContent = axisValue.toFixed(3);
                            document.getElementById('quatX').textContent = axisValue.toFixed(3);
                            
                       
                            let modeText;
                            if (isPlayingBack) {
                                modeText = 'Playback Mode';
                            } else if (calibrationData.isCalibrated) {
                                const pointCount = [calibrationData.zeroDeg, calibrationData.ninetyDeg, calibrationData.minusNinetyDeg]
                                    .filter(p => p !== null).length;
                                modeText = `${pointCount}-Point Calibrated`;
                            } else {
                                modeText = 'Reset Offset';
                            }
                            document.getElementById('calculationMode').textContent = modeText;
                            
                        
                            const dummyHead = document.getElementById('dummyHead');
                            dummyHead.style.transform = `rotate(${-rotationDegrees}deg)`;
                            
                           
                            const seg1Bend = -rotationDegrees * 0.85; 
                            document.getElementById('neckSeg1').style.transform = `rotate(${seg1Bend}deg)`;
                            
                       
                            const seg2Bend = -rotationDegrees * 0.7; 
                            document.getElementById('neckSeg2').style.transform = `rotate(${seg2Bend}deg)`;
                            
                     
                            const maxBendFactor = -rotationDegrees * 0.4; 
                            document.getElementById('neckSeg3').style.transform = `rotate(${maxBendFactor}deg)`;
                            
                        
                            const seg4Bend = maxBendFactor * 0.3; 
                            document.getElementById('neckSeg4').style.transform = `rotate(${seg4Bend}deg)`;
                            
                           
                            document.getElementById('neckSeg5').style.transform = `rotate(0deg)`;
                        } else {
                           
                            document.getElementById('xRotation').textContent = 'No Data';
                            document.getElementById('xValue').textContent = 'N/A';
                            document.getElementById('quatX').textContent = 'N/A';
                            document.getElementById('calculationMode').textContent = 'Sensor Disconnected';
                        }
                    } catch (error) {
                        console.error('Error fetching data:', error);
                        
                
                        document.getElementById('data').textContent = `Connection Error: ${error.message}\nTry using the "Reconnect Sensors" button.`;
                
                        document.getElementById('sensor4AText').textContent = 'Connection Error';
                        document.getElementById('sensor4AStatus').className = 'sensor-status-item sensor-disconnected';
                        document.getElementById('sensor4AIndicator').className = 'status-indicator status-disconnected';
                    }
                }, 10)
                
             
                window.addEventListener('DOMContentLoaded', function() {
                    loadAxisConfig();
                });
            </script>
        </body>
        </html>
    ''')

@app.route('/data')
def data():

    if is_playing_back:
        return jsonify({'error': 'In playback mode'}), 400
    

    sensor_data_4a = safe_read_sensor_data('sensor_4a', sensor_4a)
    sensor_data_4b = safe_read_sensor_data('sensor_4b', sensor_4b) if sensor_4b_available else None
   
    if not sensor_data_4a and sensor_status['sensor_4a']['error_count'] >= MAX_ERROR_COUNT:
        print("Primary sensor failed, attempting auto-reconnection...")
        if attempt_sensor_reconnection('sensor_4a'):
        
            sensor_data_4a = safe_read_sensor_data('sensor_4a', sensor_4a)
    
   
    if sensor_4b_available and not sensor_data_4b and sensor_status['sensor_4b']['error_count'] >= MAX_ERROR_COUNT:
        print("Secondary sensor failed, attempting auto-reconnection...")
        if attempt_sensor_reconnection('sensor_4b'):
            sensor_data_4b = safe_read_sensor_data('sensor_4b', sensor_4b)
    
   
    response_data = {
     
        'acceleration': sensor_data_4a['acceleration'] if sensor_data_4a else None,
        'gyroscope': sensor_data_4a['gyroscope'] if sensor_data_4a else None,
        'magnetometer': sensor_data_4a['magnetometer'] if sensor_data_4a else None,
        'quaternion': sensor_data_4a['quaternion'] if sensor_data_4a else None,
        
   
        'sensor_4a': sensor_data_4a,
        'sensor_4b': sensor_data_4b,
        
    
        'sensor_status': {
            'sensor_4a': {
                'connected': sensor_status['sensor_4a']['connected'],
                'error_count': sensor_status['sensor_4a']['error_count'],
                'last_error': sensor_status['sensor_4a']['last_error']
            },
            'sensor_4b': {
                'connected': sensor_status['sensor_4b']['connected'],
                'error_count': sensor_status['sensor_4b']['error_count'],
                'last_error': sensor_status['sensor_4b']['last_error']
            } if sensor_4b_available else None
        }
    }
    

    if is_recording:
        timestamp = (time.time() * 1000) - (recording_start_time * 1000) if recording_start_time else 0
        recording_data.append({
            'timestamp': timestamp,
            'data': response_data
        })
    
    return jsonify(response_data)

@app.route('/reset_quaternion', methods=['POST'])
def reset_quaternion():
    global quaternion_offset
    

    if not sensor_4a or not sensor_status['sensor_4a']['connected']:
        return jsonify({'error': 'Primary sensor not connected'}), 400
    

    try:
        current_quat = sensor_4a.quaternion
        if current_quat:
         
            if axis_config['primary_axis'] == 'x':
                axis_value = current_quat[0]
            elif axis_config['primary_axis'] == 'y':
                axis_value = current_quat[1]
            else:  # 'z'
                axis_value = current_quat[2]
            
          
            if axis_config['invert']:
                axis_value = -axis_value
                
        
            quaternion_offset = {
                'x': axis_value,  
                'y': 0, 
                'z': 0,
                'w': 1
            }
        else:
            return jsonify({'error': 'No quaternion data available'}), 400
    except Exception as e:
        print(f"Error reading sensor for reset: {e}")
        return jsonify({'error': 'Failed to read sensor data'}), 500
        
    return jsonify({'status': 'reset', 'offset': quaternion_offset})

@app.route('/reconnect_sensors', methods=['POST'])
def reconnect_sensors():
    try:
        success = reconnect_all_sensors()
        if success:
            return jsonify({
                'status': 'success',
                'message': 'Sensors reconnected successfully',
                'sensor_status': {
                    'sensor_4a': sensor_status['sensor_4a'],
                    'sensor_4b': sensor_status['sensor_4b'] if sensor_4b_available else None
                }
            })
        else:
            return jsonify({
                'status': 'partial_success',
                'message': 'Some sensors failed to reconnect',
                'sensor_status': {
                    'sensor_4a': sensor_status['sensor_4a'],
                    'sensor_4b': sensor_status['sensor_4b'] if sensor_4b_available else None
                }
            })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Reconnection failed: {str(e)}',
            'sensor_status': {
                'sensor_4a': sensor_status['sensor_4a'],
                'sensor_4b': sensor_status['sensor_4b'] if sensor_4b_available else None
            }
        }), 500

@app.route('/sensor_status', methods=['GET'])
def get_sensor_status():
    return jsonify({
        'sensor_status': {
            'sensor_4a': sensor_status['sensor_4a'],
            'sensor_4b': sensor_status['sensor_4b'] if sensor_4b_available else None
        }
    })

@app.route('/calibrate', methods=['POST'])
def calibrate():
    global calibration_points
    data = request.get_json()
    point_type = data.get('point')
    
    if not sensor_4a or not sensor_status['sensor_4a']['connected']:
        return jsonify({'error': 'Primary sensor not connected'}), 400
    
    try:
        current_quat = sensor_4a.quaternion
        if not current_quat:
            return jsonify({'error': 'No sensor data available'}), 400
        
       
        if axis_config['primary_axis'] == 'x':
            current_axis_value = current_quat[0]
        elif axis_config['primary_axis'] == 'y':
            current_axis_value = current_quat[1]
        else:  # 'z'
            current_axis_value = current_quat[2]
        
     
        if axis_config['invert']:
            current_axis_value = -current_axis_value
        
        
        if point_type == 'zero':
            calibration_points['zero_deg'] = current_axis_value
        elif point_type == 'ninety':
            calibration_points['ninety_deg'] = current_axis_value
        elif point_type == 'minus_ninety':
            calibration_points['minus_ninety_deg'] = current_axis_value
        elif point_type == 'clear':
            calibration_points['zero_deg'] = None
            calibration_points['ninety_deg'] = None
            calibration_points['minus_ninety_deg'] = None
            calibration_points['is_calibrated'] = False
            return jsonify({
                'status': 'success',
                'calibration': {
                    'zeroDeg': None,
                    'ninetyDeg': None,
                    'minusNinetyDeg': None,
                    'isCalibrated': False
                }
            })
        
     
        point_count = sum(1 for point in [calibration_points['zero_deg'], 
                                         calibration_points['ninety_deg'], 
                                         calibration_points['minus_ninety_deg']] 
                         if point is not None)
        
     
        calibration_points['is_calibrated'] = point_count >= 1
        
        return jsonify({
            'status': 'success',
            'calibration': {
                'zeroDeg': calibration_points['zero_deg'],
                'ninetyDeg': calibration_points['ninety_deg'],
                'minusNinetyDeg': calibration_points['minus_ninety_deg'],
                'isCalibrated': calibration_points['is_calibrated']
            }
        })
        
    except Exception as e:
        print(f"Error during calibration: {e}")
        return jsonify({'error': 'Failed to read sensor data for calibration'}), 500

@app.route('/get_calibration', methods=['GET'])
def get_calibration():
    return jsonify({
        'calibration': {
            'zeroDeg': calibration_points['zero_deg'],
            'ninetyDeg': calibration_points['ninety_deg'],
            'minusNinetyDeg': calibration_points['minus_ninety_deg'],
            'isCalibrated': calibration_points['is_calibrated']
        }
    })

@app.route('/set_axis_config', methods=['POST'])
def set_axis_config():
    global axis_config
    data = request.get_json()
    
    if 'primary_axis' in data and data['primary_axis'] in ['x', 'y', 'z']:
        axis_config['primary_axis'] = data['primary_axis']
    
    if 'invert' in data and isinstance(data['invert'], bool):
        axis_config['invert'] = data['invert']
    
    return jsonify({
        'status': 'success',
        'axis_config': axis_config
    })

@app.route('/get_axis_config', methods=['GET'])
def get_axis_config():
    return jsonify(axis_config)

@app.route('/start_recording', methods=['POST'])
def start_recording():
    global is_recording, recording_data, recording_start_time
    
    if is_playing_back:
        return jsonify({'error': 'Cannot record during playback'}), 400
    
    is_recording = True
    recording_data = []
    recording_start_time = time.time()
    
    return jsonify({'status': 'success', 'message': 'Recording started'})

@app.route('/stop_recording', methods=['POST'])
def stop_recording():
    global is_recording, recording_start_time
    
    if not is_recording:
        return jsonify({'error': 'Not currently recording'}), 400
    
    is_recording = False
    duration = time.time() - recording_start_time if recording_start_time else 0
    data_points = len(recording_data)
    
    return jsonify({
        'status': 'success',
        'duration': round(duration, 2),
        'dataPoints': data_points
    })

@app.route('/get_recording', methods=['GET'])
def get_recording():
    return jsonify({
        'recording': recording_data,
        'duration': recording_data[-1]['timestamp'] / 1000 if recording_data else 0,
        'dataPoints': len(recording_data)
    })

@app.route('/clear_recording', methods=['POST'])
def clear_recording():
    global recording_data, is_recording, is_playing_back, recording_start_time
    
    recording_data = []
    is_recording = False
    is_playing_back = False
    recording_start_time = None
    
    return jsonify({'status': 'success', 'message': 'Recording cleared'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
