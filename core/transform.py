"""
Transform: 프레임 crop 및 스케일 변환
"""
from PIL import Image
from typing import List, Tuple


def crop_frames(
    frames: List[Image.Image],
    bbox: Tuple[int, int, int, int]
) -> List[Image.Image]:
    """
    모든 프레임에 동일한 bbox 적용하여 crop

    Args:
        frames: 프레임 이미지 리스트
        bbox: (left, top, right, bottom) 공통 bbox

    Returns:
        crop된 프레임 리스트
    """
    cropped_frames = []
    for frame in frames:
        cropped = frame.crop(bbox)
        cropped_frames.append(cropped)
    return cropped_frames


def scale_image(
    image: Image.Image,
    target_size: Tuple[int, int],
    resample: int = Image.Resampling.LANCZOS
) -> Image.Image:
    """
    이미지 스케일링

    Args:
        image: 원본 이미지
        target_size: (width, height) 목표 크기
        resample: 리샘플링 방식 (기본 LANCZOS)

    Returns:
        스케일된 이미지
    """
    return image.resize(target_size, resample=resample)


def scale_frames(
    frames: List[Image.Image],
    target_frame_size: Tuple[int, int],
    resample: int = Image.Resampling.LANCZOS
) -> List[Image.Image]:
    """
    모든 프레임을 동일 크기로 스케일링

    Args:
        frames: 프레임 리스트
        target_frame_size: (width, height) 목표 프레임 크기
        resample: 리샘플링 방식

    Returns:
        스케일된 프레임 리스트
    """
    return [frame.resize(target_frame_size, resample=resample) for frame in frames]
