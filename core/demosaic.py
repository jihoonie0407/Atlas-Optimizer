"""
Demosaic: 아틀라스 이미지를 개별 프레임으로 분리
"""
from PIL import Image
from typing import List, Tuple


def demosaic(atlas: Image.Image, rows: int, cols: int) -> List[Image.Image]:
    """
    아틀라스를 개별 프레임으로 분리

    Args:
        atlas: 아틀라스 이미지 (PIL Image)
        rows: 행 개수
        cols: 열 개수

    Returns:
        프레임 리스트 (왼쪽 상단부터 오른쪽으로, 위에서 아래로 순서)
    """
    if atlas.mode != 'RGBA':
        atlas = atlas.convert('RGBA')

    width, height = atlas.size
    frame_width = width // cols
    frame_height = height // rows

    frames = []
    for row in range(rows):
        for col in range(cols):
            left = col * frame_width
            top = row * frame_height
            right = left + frame_width
            bottom = top + frame_height

            frame = atlas.crop((left, top, right, bottom))
            frames.append(frame)

    return frames


def auto_detect_grid(atlas: Image.Image) -> Tuple[int, int]:
    """
    아틀라스의 그리드 구조 자동 감지 (정사각형 그리드 가정)

    Args:
        atlas: 아틀라스 이미지

    Returns:
        (rows, cols) 튜플
    """
    width, height = atlas.size

    # 정사각형 아틀라스 + 정사각형 프레임 가정
    # 일반적인 그리드: 2x2, 4x4, 8x8, 4x8, 8x4 등
    common_grids = [
        (2, 2), (4, 4), (8, 8), (16, 16),
        (4, 2), (2, 4), (8, 4), (4, 8),
        (8, 2), (2, 8), (16, 8), (8, 16),
        (3, 3), (6, 6), (4, 3), (3, 4),
    ]

    # 정사각형 프레임이 되는 그리드 찾기
    for rows, cols in common_grids:
        frame_w = width / cols
        frame_h = height / rows
        if frame_w == frame_h and frame_w == int(frame_w):
            return (rows, cols)

    # 찾지 못하면 정사각형 아틀라스 기준으로 추정
    if width == height:
        # 4x4가 가장 일반적
        return (4, 4)
    elif width > height:
        ratio = width // height
        return (1, ratio)
    else:
        ratio = height // width
        return (ratio, 1)
