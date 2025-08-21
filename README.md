# 🎥 Object Detection in Videos using SSD  

## 📌 Overview  
A Python application that applies **Single Shot Multibox Detector (SSD)** to detect objects in video frames in real time.  
Using a lightweight SSD model (e.g., SSD with MobileNet backbone), the project reads video inputs and generates an annotated output video with detected objects.  

---

## ✨ Features  
- ⚡ Real-time **object detection** on video streams using SSD  
- 🧠 Supports **pre-trained SSD models** for quick deployment  
- 🖼️ Annotates frames with bounding boxes & class labels  
- 🔄 Works with live camera feeds or offline videos  

---

## 📂 Project Structure  
```
object-detection-in-videos-using-SSD/
├── 📁 ssd_files/                # SSD model files (weights, configs)
├── 🎞️ testing videos/           # Sample test videos
├── 🐍 ssd_object_detection.py   # Main implementation script
└── 📄 README.md                 # Project documentation
```

---

## 🚀 Getting Started  

### 1️⃣ Clone the Repo  
```bash
git clone https://github.com/Akhilbendi/object-detection-in-videos-using-SSD.git
cd object-detection-in-videos-using-SSD
```

### 2️⃣ Install Requirements  
```bash
pip install opencv-python tensorflow
```

### 3️⃣ Place SSD Model Files  
Add your SSD model files (e.g., `ssd_mobilenet_v2.pb`) into the `ssd_files/` directory.  

### 4️⃣ Run Detection  
```bash
python ssd_object_detection.py --input input_video.mp4 --output output_detected.mp4
```
💡 You can also modify the script for live camera input.  

---

## 🎯 Example Workflow  
```bash
python ssd_object_detection.py --input sample_video.mp4 --output detected_video.mp4
```
➡️ The output video will have bounding boxes & labels drawn on every frame.  

---

## 📖 Key Takeaways  
SSD is a **single-pass object detector** that balances ⚡ **speed** and 🎯 **accuracy**.  
Unlike region-proposal-based methods (e.g., Faster R-CNN), SSD detects objects in **one forward pass**, making it ideal for video applications.  
It uses **multiple anchor boxes** across feature maps to capture objects of different scales and aspect ratios.  

---

## 🔮 Future Improvements  
- 🛠️ Support for custom-trained SSD models  
- 📊 Real-time FPS overlay on videos  
- 🖥️ GUI or Web Interface for easier usage  
- 🤖 Integration with modern detectors like **YOLOv8** or **Faster R-CNN**  
