import cv2

def safe_resize(image):
    max_dim = 1400
    h, w = image.shape[:2]
    original_size = f"{w}x{h}"
    scale = max_dim / max(h, w)
    
    if scale < 1:
        image = cv2.resize(image, None, fx=scale, fy=scale)
        
    new_h, new_w = image.shape[:2]
    resized_size = f"{new_w}x{new_h}"
    return image, original_size, resized_size
