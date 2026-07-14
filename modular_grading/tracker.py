import numpy as np
import cv2
from config import PIXEL_TO_MM_RATIO

class ObjectTracker:
    """
    Tracks multiple cashew objects independently within a zone
    - Assigns unique IDs
    - Collects size measurements (mm)
    - Stores largest mm per object
    - Detects when objects exit ROI
    - Handles flickering/missing frames
    """
    
    def __init__(self, zone_name, max_distance=250, max_disappeared=20):
        self.zone_name = zone_name
        self.next_id = 1
        self.objects = {}  # {id: {'centroid': (x,y), 'latest_contour': None, 'is_good': True, ...}}
        self.max_distance = max_distance
        self.max_disappeared = max_disappeared
        
    def update(self, contours, is_good_flags, grades, crops):
        """
        Update tracked objects with new contours and their quality assessment
        """
        current_centroids = []
        current_sizes = []
        
        for i, c in enumerate(contours):
            M = cv2.moments(c)
            if M["m00"] != 0:
                cx = int(M["m10"] / M["m00"])
                cy = int(M["m01"] / M["m00"])
                
                rect = cv2.minAreaRect(c)
                w, h = rect[1]
                mm_size = max(w, h) * PIXEL_TO_MM_RATIO
                
                current_centroids.append((cx, cy))
                current_sizes.append(mm_size)
        
        # Match current detections to existing objects
        object_ids = list(self.objects.keys())
        matched_objects = set()
        matched_detections = set()
        
        for i, curr_centroid in enumerate(current_centroids):
            min_dist = float('inf')
            min_id = None
            for obj_id in object_ids:
                if obj_id in matched_objects: continue
                obj_centroid = self.objects[obj_id]['centroid']
                dist = np.sqrt((curr_centroid[0]-obj_centroid[0])**2 + (curr_centroid[1]-obj_centroid[1])**2)
                if dist < min_dist:
                    min_dist = dist; min_id = obj_id
            
            if min_dist < self.max_distance and min_id is not None:
                self.objects[min_id]['centroid'] = curr_centroid
                self.objects[min_id]['measurements'].append(current_sizes[i])
                self.objects[min_id]['max_mm'] = max(self.objects[min_id]['max_mm'], current_sizes[i])
                
                self.objects[min_id]['grade_history'].append(grades[i])
                
                if current_sizes[i] >= self.objects[min_id]['max_mm']:
                    self.objects[min_id]['last_crop'] = crops[i].copy()
                self.objects[min_id]['latest_contour'] = contours[i] 
                self.objects[min_id]['is_good'] = is_good_flags[i]   
                self.objects[min_id]['current_grade'] = grades[i]    
                
                self.objects[min_id]['disappeared_count'] = 0
                matched_objects.add(min_id)
                matched_detections.add(i)
        
        # New objects
        for i in range(len(current_centroids)):
            if i not in matched_detections:
                self.objects[self.next_id] = {
                    'centroid': current_centroids[i],
                    'measurements': [current_sizes[i]],
                    'max_mm': current_sizes[i],
                    'grade_history': [grades[i]],
                    'last_crop': crops[i].copy(),
                    'latest_contour': contours[i],
                    'is_good': is_good_flags[i],
                    'current_grade': grades[i],
                    'disappeared_count': 0
                }
                self.next_id += 1
        
        disappeared = []
        for obj_id in object_ids:
            if obj_id not in matched_objects:
                self.objects[obj_id]['disappeared_count'] += 1
                if self.objects[obj_id]['disappeared_count'] > self.max_disappeared:
                    disappeared.append(obj_id)
        
        return disappeared
    
    def get_object_info(self, obj_id):
        return self.objects.get(obj_id, None)
    
    def remove_object(self, obj_id):
        if obj_id in self.objects:
            del self.objects[obj_id]
