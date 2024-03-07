<H1 align="center">
Gait Velocity (or Speed) Estimation with YOLOv8 Object Detection + DeepSORT Tracking </H1>

https://github.com/TAIIPA/gait-velocity-estimation/assets/19821289/1aae39eb-0c72-4c21-9397-2a49d10548ba

## Steps to run Code

- Clone the repository
```
git clone https://github.com/MuhammadMoinFaisal/YOLOv8-DeepSORT-Object-Tracking.git
```
- Goto the cloned folder.
```
cd YOLOv8-DeepSORT-Object-Tracking
```
- Install the dependecies
```
pip install -e '.[dev]'
```

- Setting the Directory.
```
cd ultralytics/yolo/v8/detect
```
- Estimate gait velocity on gait video.

```
# yolov8 object detection + tracking
python estimate_velo.py model="yolov8n.pt" source="[YOUR GAIT VIDEO FILE]"
```

### References
[1] https://github.com/ultralytics/ultralytics

[2] https://github.com/MuhammadMoinFaisal/YOLOv8-DeepSORT-Object-Tracking

[3] https://github.com/chaelin0722/Estimate_pedestrian_speed

### Todos
- [] refactor "estimate_velo.py"
- [] add description about setting "ppm"
