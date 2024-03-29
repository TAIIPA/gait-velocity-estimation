# Ultralytics YOLO 🚀, GPL-3.0 license
# model="./last_106.pt" source="../../../../input_video/short_7818.avi"
import hydra
import math
import cv2
import torch
from shapely.geometry import Polygon
from ultralytics.yolo.engine.predictor import BasePredictor
from ultralytics.yolo.utils import DEFAULT_CONFIG, ROOT, ops
from ultralytics.yolo.utils.checks import check_imgsz
from ultralytics.yolo.utils.plotting import Annotator
import cv2
from deep_sort_pytorch.utils.parser import get_config
from deep_sort_pytorch.deep_sort import DeepSort
from collections import deque
import numpy as np

palette = (2 ** 11 - 1, 2 ** 15 - 1, 2 ** 20 - 1)
data_deque = {}
ss_deque = {}
ar_que = {}
ar_que30 = {}
ar_start = {}
deepsort = None
ss = 0
object_counter = {}
s_list = {}
object_counter1 = {}

line = [(100, 500), (1050, 500)]
speed_line_queue = {}


def degree(start, end):
    x1, y1 = start
    x2, y2 = end

    dx = x2 - x1
    dy = y2 - y1

    # 방향 각도 계산 (라디안)
    angle_rad = math.atan2(dy, dx)

    # 라디안을 도(degree)로 변환
    angle_deg = math.degrees(angle_rad)

    return angle_deg

def get_point(filename):
    # bottom left, top left, top right, bottom right
    if "cam1" in filename:
        point = np.array([[640, 1080], [640, 0], [1280, 0], [1280, 1080]], np.int32)
    elif "cam2" in filename:
        point = np.array([[720, 1080], [480, 720], [900, 360], [920, 400]], np.int32)
    elif "cam3" in filename:
        point = np.array([[480, 920], [480, 360], [1800, 360], [1800, 900]], np.int32)
    
    # 좌표를 정점들로 변환합니다.
    point = point.reshape((-1, 1, 2))
    return point

def check_intersect(box, filename):
    point = get_point(filename)

    # 객체의 bbox 좌표로 다각형 객체 생성
    bx1, by1, w, h = box
    rectangle_coords = (bx1, by1), (w, by1), (w, h), (bx1, h)
    rectangle = Polygon(rectangle_coords)

    # 왼쪽 인식존 다각형 객체 생성
    parallelogram_coords = point[1][0], point[2][0], point[3][0], point[0][0]
    parallelogram = Polygon(parallelogram_coords)

    rectangle = Polygon(rectangle_coords)
    # 두 다각형이 교차하는지 확인
    return parallelogram.intersects(rectangle)

def draw_rec(img, filename):
    point = get_point(filename)

    # Draw polygon
    cv2.polylines(img, [point], isClosed=True, color=(226, 43, 138), thickness=8)

def get_distance(bcenter, filename, angle):
    point = get_point(filename)
    cx, cy = bcenter

    # 아래로 내려갈때 (수직거리)
    if angle <= 0 and angle >= -180:
        return point[0][0][1] - cy

    return None

def ETS(speed, lr, filename, angle):
    ppm = 0.012
    distance = get_distance(lr, filename, angle)

    if distance is None:
        return None
    else:
        if distance > 0:
            d_meters = distance * ppm
            t = (d_meters/ speed)
        else:
            t = 0

    return round(t, 2)

def estimatespeed(location1, location2, filename):
    # Euclidean Distance
    d_pixel = math.sqrt(math.pow(location2[0] - location1[0], 2) + math.pow(location2[1] - location1[1], 2))
    # defining thr pixels per meter
    if filename == "7806":
        ppm = 0.006
    else:
        # ppm = 0.0138333 # cam1
        ppm = 0.0045 # cam3
    # 실제 거리 meter 로
    d_meters = d_pixel * ppm
    # 30fps
    time_constant = 60
    speed = d_meters * time_constant
    print(speed, d_pixel, ppm)
    return speed

def init_tracker():
    global deepsort
    cfg_deep = get_config()
    cfg_deep.merge_from_file("deep_sort_pytorch/configs/deep_sort.yaml")

    deepsort= DeepSort(cfg_deep.DEEPSORT.REID_CKPT,
                            max_dist=cfg_deep.DEEPSORT.MAX_DIST, min_confidence=cfg_deep.DEEPSORT.MIN_CONFIDENCE,
                            nms_max_overlap=cfg_deep.DEEPSORT.NMS_MAX_OVERLAP, max_iou_distance=cfg_deep.DEEPSORT.MAX_IOU_DISTANCE,
                            max_age=cfg_deep.DEEPSORT.MAX_AGE, n_init=cfg_deep.DEEPSORT.N_INIT, nn_budget=cfg_deep.DEEPSORT.NN_BUDGET,
                            use_cuda=True)
##########################################################################################
def xyxy_to_xywh(*xyxy):
    """" Calculates the relative bounding box from absolute pixel values. """
    bbox_left = min([xyxy[0].item(), xyxy[2].item()])
    bbox_top = min([xyxy[1].item(), xyxy[3].item()])
    bbox_w = abs(xyxy[0].item() - xyxy[2].item())
    bbox_h = abs(xyxy[1].item() - xyxy[3].item())
    x_c = (bbox_left + bbox_w / 2)
    y_c = (bbox_top + bbox_h / 2)
    w = bbox_w
    h = bbox_h
    return x_c, y_c, w, h

def compute_color_for_labels(speed):
    """
    Simple function that adds fixed color depending on the class
    """
    # (b, g, r) 순서
    if speed > 0.85: #green
        color = (82, 209, 23)
        return tuple(color)
    if 0.8 <= speed and speed <= 0.85 : # yellow
        color = (8, 236, 252)
        return tuple(color)
    if speed <= 0.45 : # blue
        color = (255, 0, 0)
        return tuple(color)
    if speed > 0.45 and speed < 0.8 : # red
        color = (0, 0, 255)
        return tuple(color)

def UI_box(x, img, ang, speed, color=None, label=None, line_thickness=None):
    # Plots one bounding box on image img
    tl = line_thickness or round(0.002 * (img.shape[0] + img.shape[1]) / 2) + 1  # line/font thickness
    color = color
    c1, c2 = (int(x[0]), int(x[1])), (int(x[2]), int(x[3]))
    cv2.rectangle(img, c1, c2, color, thickness=tl, lineType=cv2.LINE_AA)
    if label != "":
        ## labeling 부분
        # 파란색, 즉 보행자 대기의 경우 객체이름만 나오기 때문에 라벨링 영역 사각형 크기 줄이기
        if color == (255, 0, 0):
            pass
            # cv2.rectangle(img, (int(x[2]), int(x[1])), (int(x[2]) +200, int(x[1])+130), color, -1)
        else:
            cv2.rectangle(img, (int(x[2]), int(x[1])), (int(x[2]) + 300, int(x[1])+130), color, -1)

        # 객체 이름, 속도, ETS 각각 줄바꿈하여 화면에 나타나도록 하기
        y0 = int(x[1]) + 40
        for i, line in enumerate(label.split('\n')):
            y = y0 + i * 45  # dy
            cv2.putText(img, line, (int(x[2]), y), 0, tl / 2, [255, 255, 255], thickness=3, lineType=cv2.LINE_AA)

        ## 화살표, 움직임 없을땐 그리지 않도록 조건
        if speed > 0.45 and ang is not None:

            # 화살표의 시작점과 길이, 방향 각도 (도)
            start_x = int((int(x[0]) + int(x[2]) ) / 2)
            start_y = int(x[3]) # 시작점 좌표
            arrow_length = 50  # 화살표의 길이
            angle_deg = ang  # 방향 각도 (도)

            # 방향 각도를 라디안으로 변환
            angle_rad = math.radians(angle_deg)
            # 화살표의 끝점 좌표 계산
            end_x = int(start_x + arrow_length * math.cos(angle_rad))
            end_y = int(start_y + arrow_length * math.sin(angle_rad))

            # 화살표 그리기
            start_point = (start_x, start_y)  # 화살표 시작점
            end_point = (end_x, end_y)  # 화살표 끝점
            color = (0,0,255)  # 화살표 색상 (빨간색)
            thickness = 5  # 선 두께

            cv2.arrowedLine(img, end_point, start_point, color, thickness, tipLength=0.3)


def intersect(A,B,C,D):
    return ccw(A,C,D) != ccw(B,C,D) and ccw(A,B,C) != ccw(A,B,D)

def ccw(A,B,C):
    return (C[1]-A[1]) * (B[0]-A[0]) > (B[1]-A[1]) * (C[0]-A[0])


def draw_boxes(img, bbox, names, object_id, filename, identities=None, offset=(0, 0)):
    height, width, _ = img.shape
    # remove tracked point from buffer if object is lost
    for key in list(data_deque):
      if key not in identities:
        data_deque.pop(key)

    for i, box in enumerate(bbox):
        if not check_intersect(box, filename):
            continue
        x1, y1, x2, y2 = [int(i) for i in box]
        x1 += offset[0]
        x2 += offset[0]
        y1 += offset[1]
        y2 += offset[1]
        
        
        # BBox: (center_x, center_y, width, height)
        # center coordinate of object
        center = (int((x2 + x1) / 2), int((y1 + y2) / 2))
        # bottom center point
        #center = (int((x2+x1)/ 2), int((y2+y2)/2))

        # get ID of object
        id = int(identities[i]) if identities is not None else 0

        # create new buffer for new object
        if id not in data_deque:
            data_deque[id] = deque(maxlen=64)
            speed_line_queue[id] = []
            s_list[id] = []
            ar_start[id] = []
            ar_que[id] = []
            ar_que30[id] = []

        label = "Person"
        # 객체의 센터포인트를 데크에 저장해서 사용하도록 하기
        data_deque[id].appendleft(center)
        #img_deque.append(img)
        if len(data_deque[id]) >= 2:
            ## calculate speed
            object_speed = estimatespeed(data_deque[id][1], data_deque[id][0], filename)
            speed_line_queue[id].append(object_speed)

            # add degree to buffer
            angle = degree(data_deque[id][0], data_deque[id][1])
            ar_start[id].append(data_deque[id][0])
            ar_que[id].append(angle)

            ss = sum(speed_line_queue[id]) / len(speed_line_queue[id])

            if len(speed_line_queue[id])%60 == 0:
                # 이 전에 쌓인 값 초기화
                s_list[id].clear()
                ar_que30[id].clear()
                # min.max 값 없애고 이번 30 주기의 값 append
                speed_line_queue[id].pop(speed_line_queue[id].index(min(speed_line_queue[id])))
                speed_line_queue[id].pop(speed_line_queue[id].index(max(speed_line_queue[id])))
                ss = sum(speed_line_queue[id]) / len(speed_line_queue[id])
                # 30 프레임 중 가장 첫 프레임의 객체의 좌표값과 마지막 프레임의 객체의 좌표값 을 넘겨주어 각도를 구해준다
                angle = degree(ar_start[id][-1], ar_start[id][0])

                s_list[id].append(ss)
                ar_que30[id].append(angle)
                speed_line_queue[id] = []
                ar_start[id] = []

            obs = round(ss, 2)
            data_deque[id].pop()

        print(id)
        # 30fps 주기 안에 있다면
        if s_list[id]:
            print("here")
            ss = s_list[id][0]
            color = compute_color_for_labels(ss)
            obs = round(ss, 2)

            # 30 프레임 동안 angle 도 고정
            ang = ar_que30[id][0]
            # ets 는 평균 말고 계속 실시간으로 업데이트 해줌
            ets = ETS(obs, data_deque[id][0], filename, ang)
            try:
                if obs <= 0.45:
                    label = label
                else:
                    label = label + "\n" + "Gait Vel.:" + str(obs) + "m/s" + "\n"
                    # if ets and obs >= 0.43:
                        # label = label + "ETS: " + str(ets) + " (" + str(obs) + "m/s)" # , ang:"+ str(ang)
                # if obs < 5:
                    UI_box(box, img, ang, obs, label=label, color=color, line_thickness=2)
            except:
                pass
        # 처음 부터 29까지의 프레임의 객체인식은 bbox 만 그려주고, 보행자 대기의 경우 bbox 와 함께 객체이름까지 라벨링 해준다.
        else:
            print("else")
            try:
                if obs < 3 and obs > 0.45:
                    label = ""
                    ang = None
                    color = compute_color_for_labels(obs)
                    UI_box(box, img, ang, obs, label=label, color=color, line_thickness=2)

                if obs <= 0.45:
                    color = (255, 0, 0)
                    label = label
                    ang = None
                    UI_box(box, img, ang, obs, label=label, color=color, line_thickness=2)
            except:
                pass

    return img


class DetectionPredictor(BasePredictor):

    def get_annotator(self, img):
        return Annotator(img, line_width=self.args.line_thickness, example=str(self.model.names))

    def preprocess(self, img):
        img = torch.from_numpy(img).to(self.model.device)
        img = img.half() if self.model.fp16 else img.float()  # uint8 to fp16/32
        img /= 255  # 0 - 255 to 0.0 - 1.0
        return img

    def postprocess(self, preds, img, orig_img):
        preds = ops.non_max_suppression(preds,
                                        self.args.conf,
                                        self.args.iou,
                                        agnostic=self.args.agnostic_nms,
                                        max_det=self.args.max_det)

        for i, pred in enumerate(preds):
            shape = orig_img[i].shape if self.webcam else orig_img.shape
            pred[:, :4] = ops.scale_boxes(img.shape[2:], pred[:, :4], shape).round()

        return preds

    def write_results(self, idx, preds, batch):
        p, im, im0 = batch

        all_outputs = []
        log_string = ""
        if len(im.shape) == 3:
            im = im[None]  # expand for batch dim
        self.seen += 1

        
        filename = self.args.source.split("/")[-1].split(".")[0].split("_")[-1]
        im0 = im0.copy()
        # Draw a polgon at the region of interest 
        draw_rec(im0, filename)
        
        if self.webcam:  # batch_size >= 1
            log_string += f'{idx}: '
            frame = self.dataset.count
        else:
            frame = getattr(self.dataset, 'frame', 0)

        self.data_path = p
        save_path = str(self.save_dir / p.name)  # im.jpg
        self.txt_path = str(self.save_dir / 'labels' / p.stem) + ('' if self.dataset.mode == 'image' else f'_{frame}')
        log_string += '%gx%g ' % im.shape[2:]  # print string
        self.annotator = self.get_annotator(im0)

        det = preds[idx]
        # print("det:", det)
        all_outputs.append(det)
        if len(det) == 0:
            return log_string
        for c in det[:, 5].unique():
            n = (det[:, 5] == c).sum()  # detections per class
            log_string += f"{n} {self.model.names[0]}{'s' * (n > 1)}, "
        # write
        gn = torch.tensor(im0.shape)[[1, 0, 1, 0]]  # normalization gain whwh
        xywh_bboxs = []
        confs = []
        oids = []
        outputs = []
        for *xyxy, conf, cls in reversed(det):
            if int(cls) != 0:
                continue
            x_c, y_c, bbox_w, bbox_h = xyxy_to_xywh(*xyxy)
            xywh_obj = [x_c, y_c, bbox_w, bbox_h]
            xywh_bboxs.append(xywh_obj)
            confs.append([conf.item()])
            oids.append(int(cls))
        xywhs = torch.Tensor(xywh_bboxs)
        confss = torch.Tensor(confs)

        outputs = deepsort.update(xywhs, confss, oids, im0)
        # print("outputs:", outputs)
        if len(outputs) > 0:
            bbox_xyxy = outputs[:, :4]
            identities = outputs[:, -2]
            object_id = outputs[:, -1]

            draw_boxes(im0, bbox_xyxy, self.model.names, object_id, filename, identities)
        return log_string


@hydra.main(version_base=None, config_path=str(DEFAULT_CONFIG.parent), config_name=DEFAULT_CONFIG.name)
def predict(cfg):
    init_tracker()
    cfg.model = cfg.model or "yolov8n.pt"
    cfg.imgsz = check_imgsz(cfg.imgsz, min_dim=2)  # check image size
    print(cfg.imgsz)
    cfg.source = cfg.source if cfg.source is not None else ROOT / "assets"
    predictor = DetectionPredictor(cfg)
    predictor()


if __name__ == "__main__":
    predict()
