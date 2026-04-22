"""
Mosaic: 개별 프레임들을 아틀라스로 재구성
"""
from PIL import Image
from typing import List, Tuple


def mosaic(
    frames: List[Image.Image],
    rows: int,
    cols: int,
    background_color: Tuple[int, int, int, int] = (0, 0, 0, 0)
) -> Image.Image:
    """
    프레임들을 아틀라스로 재구성

    Args:
        frames: 프레임 이미지 리스트 (왼쪽 상단부터 순서대로)
        rows: 행 개수
        cols: 열 개수
        background_color: 배경색 (RGBA)

    Returns:
        재구성된 아틀라스 이미지
    """
    if not frames:
        raise ValueError("프레임 리스트가 비어있습니다")

    expected_count = rows * cols
    if len(frames) != expected_count:
        raise ValueError(f"프레임 개수({len(frames)})가 rows*cols({expected_count})와 일치하지 않습니다")

    # 모든 프레임이 같은 크기인지 확인
    frame_width, frame_height = frames[0].size
    for i, frame in enumerate(frames):
        if frame.size != (frame_width, frame_height):
            raise ValueError(f"프레임 {i}의 크기가 일치하지 않습니다: {frame.size} != ({frame_width}, {frame_height})")

    # 아틀라스 생성
    atlas_width = frame_width * cols
    atlas_height = frame_height * rows
    atlas = Image.new('RGBA', (atlas_width, atlas_height), background_color)

    # 프레임 배치
    for idx, frame in enumerate(frames):
        row = idx // cols
        col = idx % cols

        x = col * frame_width
        y = row * frame_height

        # RGBA 모드로 변환
        if frame.mode != 'RGBA':
            frame = frame.convert('RGBA')

        atlas.paste(frame, (x, y))

    return atlas


def calculate_atlas_size(
    frame_size: Tuple[int, int],
    rows: int,
    cols: int
) -> Tuple[int, int]:
    """
    아틀라스 크기 계산

    Args:
        frame_size: (width, height) 프레임 크기
        rows: 행 개수
        cols: 열 개수

    Returns:
        (atlas_width, atlas_height)
    """
    return (frame_size[0] * cols, frame_size[1] * rows)
