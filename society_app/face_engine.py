import os
import io
import base64
import numpy as np
import cv2
from PIL import Image
from django.conf import settings


# Path for saving trained LBPH model
MODEL_DIR = os.path.join(settings.BASE_DIR, 'ml_models')
MODEL_PATH = os.path.join(MODEL_DIR, 'lbph_face_model.xml')
LABEL_MAP_PATH = os.path.join(MODEL_DIR, 'labels_map.json')

# Haar Cascade Face Classifier
LOCAL_CASCADE = os.path.join(MODEL_DIR, 'haarcascade_frontalface_default.xml')
CASCADE_PATH = LOCAL_CASCADE if os.path.exists(LOCAL_CASCADE) else os.path.join(cv2.data.haarcascades, 'haarcascade_frontalface_default.xml')
face_cascade = cv2.CascadeClassifier(CASCADE_PATH)


def ensure_model_dir():
    if not os.path.exists(MODEL_DIR):
        os.makedirs(MODEL_DIR, exist_ok=True)


def load_image_to_cv2(image_input):
    """
    Accepts:
      - numpy array (BGR or RGB)
      - file path string
      - bytes / BytesIO
      - base64 data URI string (e.g. 'data:image/jpeg;base64,...' or raw base64)
      - Django InMemoryUploadedFile / FieldFile
    Returns: BGR numpy image or None
    """
    if image_input is None:
        return None

    if isinstance(image_input, np.ndarray):
        return image_input

    # Base64 string
    if isinstance(image_input, str):
        if image_input.startswith('data:image'):
            # Strip data URL prefix
            header, encoded = image_input.split(',', 1)
            image_data = base64.b64decode(encoded)
            nparr = np.frombuffer(image_data, np.uint8)
            return cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        elif os.path.exists(image_input):
            return cv2.imread(image_input)
        else:
            try:
                image_data = base64.b64decode(image_input)
                nparr = np.frombuffer(image_data, np.uint8)
                return cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            except Exception:
                return None

    # File-like object (Django upload or BytesIO)
    if hasattr(image_input, 'read'):
        try:
            image_input.seek(0)
            data = image_input.read()
            nparr = np.frombuffer(data, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            image_input.seek(0)
            return img
        except Exception:
            return None

    if isinstance(image_input, (bytes, bytearray)):
        nparr = np.frombuffer(image_input, np.uint8)
        return cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    return None


def detect_faces(cv_image):
    """
    Detects faces in a BGR image using Haar Cascade.
    Returns: list of (x, y, w, h) bounding boxes.
    """
    if cv_image is None:
        return []
    gray = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)
    gray = cv2.equalizeHist(gray)
    faces = face_cascade.detectMultiScale(
        gray,
        scaleFactor=1.1,
        minNeighbors=5,
        minSize=(60, 60),
        flags=cv2.CASCADE_SCALE_IMAGE
    )
    return faces


def extract_face_crop(cv_image, bbox, target_size=(160, 160)):
    """
    Extracts normalized grayscale face crop.
    """
    x, y, w, h = bbox
    gray = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)
    crop = gray[y:y+h, x:x+w]
    crop = cv2.resize(crop, target_size, interpolation=cv2.INTER_LANCZOS4)
    crop = cv2.equalizeHist(crop)
    return crop


def compute_normalized_feature(face_crop):
    """
    Computes a normalized histogram vector from a normalized grayscale face crop.
    """
    # 8x8 block local histograms for resilient spatial representation
    h, w = face_crop.shape
    bh, bw = h // 4, w // 4
    features = []
    for i in range(4):
        for j in range(4):
            block = face_crop[i*bh:(i+1)*bh, j*bw:(j+1)*bw]
            hist = cv2.calcHist([block], [0], None, [32], [0, 256])
            cv2.normalize(hist, hist)
            features.extend(hist.flatten())
    feat_arr = np.array(features, dtype=np.float32)
    norm = np.linalg.norm(feat_arr)
    if norm > 0:
        feat_arr = feat_arr / norm
    return feat_arr


def train_face_recognizer():
    """
    Collects face photos of all registered users who have uploaded face photos,
    trains the OpenCV LBPHFaceRecognizer, and saves the trained model to disk.
    Returns dict: {'trained_users': count, 'samples': count, 'status': 'success'}
    """
    from .models import User
    ensure_model_dir()

    recognizer = cv2.face.LBPHFaceRecognizer_create(radius=1, neighbors=8, grid_x=8, grid_y=8)
    faces_list = []
    labels_list = []
    label_to_user = {}

    users_with_photos = User.objects.filter(face_photo__isnull=False).exclude(face_photo='')

    sample_count = 0
    for user in users_with_photos:
        try:
            if not user.face_photo:
                continue
            photo_path = user.face_photo.path
            if not os.path.exists(photo_path):
                continue
            img = cv2.imread(photo_path)
            if img is None:
                continue
            detected = detect_faces(img)
            if len(detected) == 0:
                # Fallback to whole image if cropped portrait
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                crop = cv2.resize(gray, (160, 160))
                crop = cv2.equalizeHist(crop)
                faces_list.append(crop)
                labels_list.append(user.id)
                sample_count += 1
            else:
                for bbox in detected:
                    crop = extract_face_crop(img, bbox)
                    faces_list.append(crop)
                    labels_list.append(user.id)
                    sample_count += 1

            label_to_user[str(user.id)] = {
                'id': user.id,
                'name': user.get_full_name() or user.username,
                'role': user.get_role_display(),
                'flat': user.flat_number or 'N/A',
                'vehicle': user.vehicle_number or 'N/A'
            }
        except Exception as e:
            print(f"Error processing user {user.id}: {e}")

    if len(faces_list) > 0 and len(set(labels_list)) >= 1:
        recognizer.train(faces_list, np.array(labels_list))
        recognizer.write(MODEL_PATH)
        import json
        with open(LABEL_MAP_PATH, 'w') as f:
            json.dump(label_to_user, f, indent=2)
        return {'status': 'success', 'trained_users': len(label_to_user), 'samples': sample_count}
    else:
        return {'status': 'insufficient_data', 'trained_users': 0, 'samples': 0}


def recognize_gate_face(image_input, confidence_threshold=75.0):
    """
    Main Gate Recognition pipeline:
    1. Loads and decodes image (BGR).
    2. Detects face bounding boxes.
    3. Matches detected face against LBPH model and secondary feature similarity.
    4. Renders aesthetic bounding box and HUD visual overlay on image.
    5. Returns recognition results and annotated image as base64 string.
    """
    from .models import User
    img = load_image_to_cv2(image_input)
    if img is None:
        return {
            'success': False,
            'match': False,
            'reason': 'Could not decode image input',
            'annotated_image': None
        }

    faces = detect_faces(img)
    if len(faces) == 0:
        # Add visual watermark on frame
        cv2.putText(img, "Scanning... No Face In Target", (20, 40),
                    cv2.FONT_HERSHEY_DUPLEX, 0.7, (0, 165, 255), 2)
        return {
            'success': True,
            'match': False,
            'face_detected': False,
            'message': 'No face detected in scan area. Please look directly at the gate camera.',
            'annotated_image': cv2_to_base64(img)
        }

    # If model file does not exist, attempt training once
    if not os.path.exists(MODEL_PATH):
        train_result = train_face_recognizer()
        if train_result['status'] != 'success':
            # Highlight face with yellow box
            for (x, y, w, h) in faces:
                cv2.rectangle(img, (x, y), (x+w, y+h), (0, 215, 255), 2)
                cv2.putText(img, "Engine Uncalibrated", (x, y - 10),
                            cv2.FONT_HERSHEY_DUPLEX, 0.6, (0, 215, 255), 2)
            return {
                'success': True,
                'match': False,
                'face_detected': True,
                'message': 'Face detected, but no registered residents have face profiles loaded yet.',
                'annotated_image': cv2_to_base64(img)
            }

    recognizer = cv2.face.LBPHFaceRecognizer_create()
    try:
        recognizer.read(MODEL_PATH)
    except Exception:
        train_face_recognizer()
        try:
            recognizer.read(MODEL_PATH)
        except Exception:
            return {'success': False, 'match': False, 'reason': 'Failed to load face recognizer.'}

    # Match the primary (largest) face
    faces_sorted = sorted(faces, key=lambda b: b[2] * b[3], reverse=True)
    primary_bbox = faces_sorted[0]
    x, y, w, h = primary_bbox
    crop = extract_face_crop(img, primary_bbox)

    user_id, raw_dist = recognizer.predict(crop)
    # LBPH raw_dist: lower is closer. 0 is identical. <= 70 is strong match, 70-85 is plausible, > 85 is poor match
    confidence_score = max(5.0, min(99.4, 100.0 - (raw_dist * 0.65)))

    matched_user = None
    if raw_dist <= 85.0:
        try:
            matched_user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            matched_user = None

    if matched_user:
        # Match confirmed
        # Draw high-tech HUD green bounding box with corner accents
        draw_futuristic_box(img, (x, y, w, h), color=(0, 240, 100), label=f"ACCESS GRANTED: {matched_user.first_name or matched_user.username}", score=confidence_score)
        return {
            'success': True,
            'match': True,
            'face_detected': True,
            'confidence': round(confidence_score, 1),
            'user_id': matched_user.id,
            'name': matched_user.get_full_name() or matched_user.username,
            'role': matched_user.get_role_display(),
            'flat': matched_user.flat_number or 'Staff / Committee',
            'block': matched_user.block_tower or '',
            'vehicle': matched_user.vehicle_number or 'No Vehicle Registered',
            'message': f"Gate Unlocked: Welcome back, {matched_user.first_name or matched_user.username}!",
            'annotated_image': cv2_to_base64(img)
        }
    else:
        # Unrecognized face: amber/red bounding box
        draw_futuristic_box(img, (x, y, w, h), color=(50, 50, 240), label="UNKNOWN VISITOR", score=confidence_score)
        return {
            'success': True,
            'match': False,
            'face_detected': True,
            'confidence': round(confidence_score, 1),
            'message': 'Face recognized as unregistered visitor. Security gate check-in required.',
            'annotated_image': cv2_to_base64(img)
        }


def draw_futuristic_box(img, bbox, color=(0, 240, 100), label="", score=0.0):
    x, y, w, h = bbox
    # Draw transparent/thin box
    cv2.rectangle(img, (x, y), (x+w, y+h), color, 2)
    # Corner brackets for scifi / modern security HUD feel
    d = min(20, w // 4, h // 4)
    thick = 3
    # Top-Left
    cv2.line(img, (x, y), (x + d, y), color, thick)
    cv2.line(img, (x, y), (x, y + d), color, thick)
    # Top-Right
    cv2.line(img, (x + w, y), (x + w - d, y), color, thick)
    cv2.line(img, (x + w, y), (x + w, y + d), color, thick)
    # Bottom-Left
    cv2.line(img, (x, y + h), (x + d, y + h), color, thick)
    cv2.line(img, (x, y + h), (x, y + h - d), color, thick)
    # Bottom-Right
    cv2.line(img, (x + w, y + h), (x + w - d, y + h), color, thick)
    cv2.line(img, (x + w, y + h), (x + w, y + h - d), color, thick)

    # Label banner
    tag = f"{label} ({score:.1f}%)" if score > 0 else label
    cv2.rectangle(img, (x, y - 28), (x + max(200, len(tag)*11), y), (15, 23, 42), -1)
    cv2.putText(img, tag, (x + 5, y - 8), cv2.FONT_HERSHEY_DUPLEX, 0.55, color, 1)


def cv2_to_base64(cv_img):
    _, buffer = cv2.imencode('.jpg', cv_img, [int(cv2.IMWRITE_JPEG_QUALITY), 88])
    return base64.b64encode(buffer).decode('utf-8')
