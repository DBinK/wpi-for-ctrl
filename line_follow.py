#!/usr/bin/env python3

import cv2
import numpy as np
import time
from loguru import logger
import camera

cam = camera.Camera(1000, 80)

class LineFollower:
    def __init__(self):
        """
        初始化巡线计算类，设置摄像头设备。
        :param camera_device: 摄像头设备ID，默认为0。
        """
        self.src_frame = None
        self.hsv_frame = None
        self.masked_frame = None
        self.drawed_frame = None
        self.height = None
        self.width  = None

        self.center_h = None
        self.center_l = None

        self.line_color = [( 0,  0, 0), ( 180,  255,  46)] # 巡线颜色范围  
        self.site_color = [( 0,  0, 200), (180,  30, 255)] # 场地颜色范围
        self.sample_line_pos_h = 0.2
        self.sample_line_pos_l = 0.6


    def thresh_process(self, frame):
        """
        二值化方式预处理
        """
        self.src_frame = frame
        self.height, self.width = frame.shape[:2]

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        ret, dst = cv2.threshold(gray, 0, 255, cv2.THRESH_OTSU)
        dst = cv2.dilate(dst, None, iterations=2)
        dst = cv2.erode(dst, None, iterations=6)

        inverted_dst = cv2.bitwise_not(dst)

        cv2.namedWindow('dst', cv2.WINDOW_NORMAL)
        cv2.imshow('dst', inverted_dst)

        self.masked_frame = inverted_dst

        return inverted_dst


    def hsv_process(self, frame):
        """
        阈值方式预处理
        """

        self.src_frame = frame
        self.height, self.width = frame.shape[:2]

        # 将BGR图像转换为HSV图像
        self.hsv_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        # 定义一个内部函数create_mask，用于根据颜色范围创建蒙版
        def create_mask(image, color_range):
            lower_bound = np.array(color_range[0])
            upper_bound = np.array(color_range[1])
            mask = cv2.inRange(image, lower_bound, upper_bound)
            return mask
        
        # 根据线路颜色范围创建蒙版
        site_mask = create_mask(self.hsv_frame, self.site_color)
        line_mask = create_mask(self.hsv_frame, self.line_color)

        cv2.imshow('site_mask', site_mask)
        cv2.imshow('line_mask', line_mask)
        
        # 对场地蒙版进行位运算取反，以突出显示场地外的区域
        inverted_site_mask = cv2.bitwise_not(site_mask)
        
        # 通过位或运算结合线路蒙版和取反的场地蒙版，得到最终的蒙版
        final_mask = cv2.bitwise_or(line_mask, inverted_site_mask)
        
        self.masked_frame = final_mask

        return final_mask
    
    def detect_line(self, masked_frame):
        def find_center(sample_line_pos):
            color = masked_frame[sample_line_pos]
            try:
                # 找到白色的像素点个数，如寻黑色，则改为0
                white_count = np.sum(color == 255)
                # 找到白色的像素点索引，如寻黑色，则改为0
                white_index = np.where(color == 255)
                # 防止white_count=0的报错
                if white_count == 0:
                    white_count = 1
                # 计算方法应该是边缘检测，计算白色边缘的位置和/2，即是白色的中央位置。
                left_pos  = white_index[0][white_count - 1]
                right_pos = white_index[0][0]

                center = int((left_pos + right_pos) / 2)
                
                # 计算出center与标准中心点的偏移量
                direction = center - int(self.width / 2)

            except:
                direction = -1

            return direction
        
        center_h = find_center(int(self.sample_line_pos_h * self.height))
        center_l = find_center(int(self.sample_line_pos_l * self.height))

        self.center_h = center_h
        self.center_l = center_l

        logger.debug(f"center_h: {center_h}, center_l: {center_l}")

        return center_h, center_l
    
    def detect(self, frame):
        masked_frame = self.thresh_process(frame)
        center_h, center_l =self.detect_line(masked_frame)

        return center_h, center_l
    
    def draw(self, frame, center_h, center_l):
        drawed_frame = frame.copy()

        sample_height_h = int(self.sample_line_pos_h * self.height)
        sample_height_l = int(self.sample_line_pos_l * self.height)

        pt1_1 = (self.width, sample_height_h)
        pt1_2 = (         0, sample_height_h)
        
        pt2_1 = (self.width, sample_height_l)
        pt2_2 = (         0, sample_height_l)

        cv2.line(drawed_frame, pt1_1, pt1_2, (0, 0, 255), 2)
        cv2.line(drawed_frame, pt2_1, pt2_2, (0, 0, 255), 2)

        if center_h != -1:
            cv2.circle(drawed_frame, (int(center_h + self.width/2), sample_height_h), 5, (0, 0, 255), -1)
        if center_l != -1:
            cv2.circle(drawed_frame, (int(center_l + self.width/2), sample_height_l), 5, (0, 0, 255), -1)

        self.drawed_frame = drawed_frame

        return drawed_frame

    def get_color(self, event, x, y, flags, param):
        """
        获取 src_frame 鼠标点击位置的颜色值。
        """
        if event == cv2.EVENT_LBUTTONDOWN:
            # 获取当前帧的颜色值
            b, g, r = self.src_frame[y, x]
            rgb = np.array((r, g, b))  # 转换为NumPy数组
            hsv = cv2.cvtColor(np.uint8([[rgb]]), cv2.COLOR_RGB2HSV)[0][0]
            hsv = np.array(hsv)  # 确保hsv也是NumPy数组
            logger.info(f"RGB: {rgb.tolist()}, HSV: {hsv.tolist()}")
    
    def test(self):
        """
        连续读取摄像头帧并处理，用于实时巡线。
        """
        cap = cam.VideoCapture()

        logger.info(f"exposure: {cap.get(cv2.CAP_PROP_EXPOSURE)}") 

        while True:
            ret, frame = cap.read()
            if ret:
                center_h, center_l = self.detect(frame)
                drawed_frame = self.draw(frame, center_h, center_l)

                cv2.namedWindow("src_frame", cv2.WINDOW_NORMAL)
                cv2.setMouseCallback("src_frame", self.get_color)
                cv2.imshow("src_frame", self.src_frame)

                cv2.namedWindow("drawed_frame", cv2.WINDOW_NORMAL)
                cv2.imshow("drawed_frame", drawed_frame)

                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break

        cv2.destroyAllWindows()
        cap.release()


if __name__ == "__main__":
    line_follower = LineFollower()
    line_follower.test()