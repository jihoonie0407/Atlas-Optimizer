"""
BBox: 프레임들의 공통 최대 바운딩 박스 계산
"""
from PIL import Image
import numpy as np
from typing import List, Tuple, Optional


def get_alpha_bbox(image: Image.Image, threshold: int = 0) -> Optional[Tuple[int, int, int, int]]:
    """
    알파 채널 기준으로 바운딩 박스 계산

    Args:
        image: RGBA 이미지
        threshold: 알파 threshold (이 값 초과 픽셀만 유효)

    Returns:
        (left, top, right, bottom) 또는 유효 픽셀이 없으면 None
    """
    if image.mode != 'RGBA':
        image = image.convert('RGBA')

    # 알파 채널 추출
    alpha = np.array(image.split()[3])

    # threshold 초과 픽셀 찾기
    valid_pixels = alpha > threshold

    if not np.any(valid_pixels):
        return None

    # 유효 픽셀의 경계 찾기
    rows = np.any(valid_pixels, axis=1)
    cols = np.any(valid_pixels, axis=0)

    top = np.argmax(rows)
    bottom = len(rows) - np.argmax(rows[::-1])
    left = np.argmax(cols)
    right = len(cols) - np.argmax(cols[::-1])

    return (left, top, right, bottom)


def calculate_global_bbox(
    frames: List[Image.Image],
    threshold: int = 0,
    padding: int = 0
) -> Tuple[int, int, int, int]:
    """
    모든 프레임의 합집합 바운딩 박스 계산

    Args:
        frames: 프레임 이미지 리스트
        threshold: 알파 threshold (0~255)
        padding: bbox 확장 패딩 (픽셀)

    Returns:
        (left, top, right, bottom) - 모든 프레임에 적용할 공통 bbox
    """
    if not frames:
        raise ValueError("프레임 리스트가 비어있습니다")

    frame_width, frame_height = frames[0].size

    # 초기값: 이미지 전체 반대로 설정 (최소/최대 찾기 위해)
    global_left = frame_width
    global_top = frame_height
    global_right = 0
    global_bottom = 0

    valid_frame_count = 0

    for frame in frames:
        bbox = get_alpha_bbox(frame, threshold)
        if bbox is not None:
            left, top, right, bottom = bbox
            global_left = min(global_left, left)
            global_top = min(global_top, top)
            global_right = max(global_right, right)
            global_bottom = max(global_bottom, bottom)
            valid_frame_count += 1

    # 유효한 프레임이 없으면 전체 영역 반환
    if valid_frame_count == 0:
        return (0, 0, frame_width, frame_height)

    # 패딩 적용
    global_left = max(0, global_left - padding)
    global_top = max(0, global_top - padding)
    global_right = min(frame_width, global_right + padding)
    global_bottom = min(frame_height, global_bottom + padding)

    return (global_left, global_top, global_right, global_bottom)


def get_bbox_info(bbox: Tuple[int, int, int, int], original_size: Tuple[int, int]) -> dict:
    """
    바운딩 박스 정보 반환 (디버그/UI용)

    Args:
        bbox: (left, top, right, bottom)
        original_size: (width, height) 원본 프레임 크기

    Returns:
        bbox 정보 딕셔너리
    """
    left, top, right, bottom = bbox
    orig_w, orig_h = original_size

    crop_w = right - left
    crop_h = bottom - top

    original_area = orig_w * orig_h
    crop_area = crop_w * crop_h

    return {
        'bbox': bbox,
        'original_size': original_size,
        'crop_size': (crop_w, crop_h),
        'reduction_ratio': 1 - (crop_area / original_area) if original_area > 0 else 0,
        'crop_offset': (left, top),
    }
